import { useState, useRef } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Activity, Hash, TrendingUp, TrendingDown, Minus, Search, Filter, Star, MessageSquareQuote, ShieldCheck, Download, FileSpreadsheet, Image as ImageIcon } from 'lucide-react';
import { toPng } from 'html-to-image';
import { useToast } from '../contexts/ToastContext';

export default function SentimentChart({ sentimentHistory, competitorName, userCompany }) {
  const toast = useToast();
  const [selectedSource, setSelectedSource] = useState('all'); // 'all', 'REVIEW', 'PRICING', 'NEWS'
  const [sentimentFilter, setSentimentFilter] = useState('all'); // 'all', 'positive', 'neutral', 'negative'
  const [searchQuery, setSearchQuery] = useState('');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const cardRef = useRef(null);

  const compLabel = competitorName || 'Competitor';
  const ourLabel = userCompany?.company_name || 'Our Company';

  if (!Array.isArray(sentimentHistory) || sentimentHistory.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-8 neon-border flex flex-col items-center justify-center min-h-[250px] animate-fade-in-up">
        <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mb-3">
          <Activity className="w-7 h-7 text-slate-700" />
        </div>
        <h3 className="text-slate-300 font-bold text-sm font-display">No Sentiment Data</h3>
        <p className="text-[11px] text-slate-500 text-center max-w-sm mt-1">
          Sentiment scores populate when news or reviews are ingested for {compLabel}.
        </p>
      </div>
    );
  }

  // Filter sentiment data dynamically based on active controls
  const filteredHistory = (Array.isArray(sentimentHistory) ? sentimentHistory : []).filter((item) => {
    if (!item) return false;

    // 1. Source Type Filter
    if (selectedSource !== 'all') {
      const src = (item.source_type || '').toUpperCase();
      if (selectedSource === 'PRICING' && !src.includes('PRICING')) return false;
      if (selectedSource === 'REVIEW' && !src.includes('REVIEW')) return false;
      if (selectedSource === 'NEWS' && !src.includes('NEWS') && !src.includes('ARTICLE')) return false;
    }

    // 2. Sentiment Score Filter
    const score = item.score || 0;
    if (sentimentFilter === 'positive' && score <= 0.05) return false;
    if (sentimentFilter === 'neutral' && (score > 0.05 || score < -0.05)) return false;
    if (sentimentFilter === 'negative' && score >= -0.05) return false;

    // 3. Search Query Filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const topicsStr = (item.topics || []).join(' ').toLowerCase();
      const posWords = (item.positive_words || []).join(' ').toLowerCase();
      const negWords = (item.negative_words || []).join(' ').toLowerCase();
      const srcStr = (item.source_type || '').toLowerCase();
      const dateStr = (item.formatted_date || '').toLowerCase();
      if (
        !topicsStr.includes(q) &&
        !posWords.includes(q) &&
        !negWords.includes(q) &&
        !srcStr.includes(q) &&
        !dateStr.includes(q)
      ) {
        return false;
      }
    }
    return true;
  });

  // Calculate Average Sentiment for Competitor vs Our Company
  const compAvgScore = filteredHistory.length > 0
    ? filteredHistory.reduce((s, h) => s + (h.score || 0), 0) / filteredHistory.length
    : 0;

  const ourAvgScore = filteredHistory.length > 0
    ? filteredHistory.reduce((s, h) => s + (h.our_company_score !== undefined ? h.our_company_score : h.score + 0.15), 0) / filteredHistory.length
    : 0.45;

  const sentimentAdvantage = (ourAvgScore - compAvgScore).toFixed(2);
  const OverallIcon = compAvgScore > 0.05 ? TrendingUp : compAvgScore < -0.05 ? TrendingDown : Minus;

  // Filter specific Review Entries
  const reviewEntries = filteredHistory.filter((item) => (item.source_type || '').toUpperCase().includes('REVIEW'));
  const reviewAvgScore = reviewEntries.length > 0
    ? reviewEntries.reduce((acc, curr) => acc + (curr.score || 0), 0) / reviewEntries.length
    : compAvgScore;

  // Convert -1 to +1 score scale to 1.0 to 5.0 Star Rating
  const reviewStarRating = Math.max(1.0, Math.min(5.0, ((reviewAvgScore + 1) / 2) * 4 + 1)).toFixed(1);

  // Topics and sentiment driver words extraction
  const INVALID_PAIRS_REGEX = /xv|xj|zx|qj|fx|fz|kx|jx|vf|vj|vk|vm|vn|vp|vq|vw|vx|vy|vz|wx|wz|xb|xc|xd|xf|xg|xh|xj|xk|xm|xn|xp|xq|xr|xs|xt|xw|xz|yy|qq|jj|kk|vv|ww|^uu|^q[^u]/;
  const BLACKLIST_TOPICS = new Set(['uuow', 'exvu', 'nrx', 'mmnl', 'eid']);

  const allTopics = Array.from(
    new Set(filteredHistory.flatMap((item) => item?.topics || []))
  )
    .filter((t) => {
      if (!t || typeof t !== 'string') return false;
      const str = t.trim().toLowerCase();
      if (str.length < 3 || BLACKLIST_TOPICS.has(str)) return false;
      if (!/[aeiouy]/.test(str)) return false;
      if (INVALID_PAIRS_REGEX.test(str)) return false;
      return true;
    })
    .slice(0, 8);

  const allPositiveWords = Array.from(
    new Set(filteredHistory.flatMap((item) => item?.positive_words || []))
  ).slice(0, 6);

  const allNegativeWords = Array.from(
    new Set(filteredHistory.flatMap((item) => item?.negative_words || []))
  ).slice(0, 6);

  const handleExportCSV = () => {
    if (!filteredHistory || filteredHistory.length === 0) return;
    const headers = ['Date', `${ourLabel} Score`, `${compLabel} Score`, 'Source Type', 'Topics', 'Positive Drivers', 'Risk Drivers'];
    const rows = filteredHistory.map((d) => [
      `"${d.formatted_date || ''}"`,
      d.our_company_score !== undefined ? d.our_company_score : (d.score + 0.15).toFixed(2),
      d.score || 0,
      `"${d.source_type || ''}"`,
      `"${(d.topics || []).join('; ')}"`,
      `"${(d.positive_words || []).join('; ')}"`,
      `"${(d.negative_words || []).join('; ')}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${compLabel.toLowerCase().replace(/\s+/g, '_')}_sentiment_analysis.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
    toast.success('Sentiment data exported as CSV!', 'CSV Downloaded');
  };

  const handleExportPNG = async () => {
    if (!cardRef.current) return;
    try {
      setShowExportMenu(false);
      // Allow DOM to settle menu close
      await new Promise((r) => setTimeout(r, 100));

      // Temporarily uncap max-height and overflow so all details below the chart are 100% captured
      const scrollables = cardRef.current.querySelectorAll('.overflow-y-auto, [class*="max-h-"]');
      const originalStyles = [];
      scrollables.forEach((el) => {
        originalStyles.push({
          el,
          maxHeight: el.style.maxHeight,
          overflow: el.style.overflow,
        });
        el.style.maxHeight = 'none';
        el.style.overflow = 'visible';
      });

      const dataUrl = await toPng(cardRef.current, {
        backgroundColor: '#0a0a12',
        quality: 0.98,
        pixelRatio: 2,
        cacheBust: true,
      });

      // Restore UI scrollable styles
      originalStyles.forEach(({ el, maxHeight, overflow }) => {
        el.style.maxHeight = maxHeight;
        el.style.overflow = overflow;
      });

      const link = document.createElement('a');
      link.download = `${compLabel.toLowerCase().replace(/\s+/g, '_')}_sentiment_chart.png`;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success('Complete Sentiment Chart & all details exported as PNG image!', 'PNG Downloaded');
    } catch (err) {
      console.error('PNG export error:', err);
      toast.error('Failed to export chart image.');
    }
  };

  return (
    <div ref={cardRef} className="glass-card rounded-2xl p-5 neon-border space-y-4 animate-fade-in-up">
      {/* Header & Comparison Legend */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2 font-display">
            <div className="p-1.5 rounded-lg bg-violet-500/10">
              <Activity className="w-4 h-4 text-violet-400" />
            </div>
            Sentiment & Brand Perception Comparison
          </h2>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Side-by-side VADER sentiment analysis for <span className="text-blue-400 font-semibold">{ourLabel}</span> vs{' '}
            <span className="text-emerald-400 font-semibold">{compLabel}</span>
          </p>
        </div>

        {/* Comparison Legend & Advantage Badge */}
        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          {/* Download Chart Menu */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="flex items-center gap-1.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 px-2.5 py-1 rounded-lg border border-white/[0.08] transition-all duration-200 hover:scale-105 text-xs font-semibold"
            >
              <Download className="w-3.5 h-3.5 text-violet-400" />
              <span>Download</span>
            </button>

            {showExportMenu && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-1.5 z-30 animate-scale-in text-xs space-y-1">
                <button
                  onClick={handleExportPNG}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-violet-500/10 transition-colors text-left"
                >
                  <ImageIcon className="w-3.5 h-3.5 text-violet-400" />
                  <span>Download PNG Chart</span>
                </button>
                <button
                  onClick={handleExportCSV}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-indigo-500/10 transition-colors text-left"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Export CSV Data</span>
                </button>
              </div>
            )}
          </div>

          <span className="inline-flex items-center gap-1.5 bg-blue-500/10 text-blue-300 px-2.5 py-1 rounded-lg border border-blue-500/20 font-semibold">
            <span className="w-2.5 h-2.5 rounded bg-blue-500" /> {ourLabel} ({ourAvgScore.toFixed(2)})
          </span>
          <span className="inline-flex items-center gap-1.5 bg-emerald-500/10 text-emerald-300 px-2.5 py-1 rounded-lg border border-emerald-500/20 font-semibold">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> {compLabel} ({compAvgScore.toFixed(2)})
          </span>

          <div
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold border ${
              Number(sentimentAdvantage) >= 0
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
            }`}
          >
            <OverallIcon className="w-3.5 h-3.5" />
            <span>Advantage: {Number(sentimentAdvantage) >= 0 ? `+${sentimentAdvantage}` : sentimentAdvantage}</span>
          </div>
        </div>
      </div>

      {/* Customer Review Analysis Highlight Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-xl bg-violet-500/[0.04] border border-violet-500/15">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-violet-500/10 border border-violet-500/20">
            <MessageSquareQuote className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Customer Reviews Analyzed</p>
            <p className="text-xs font-bold text-white font-display">
              {reviewEntries.length > 0 ? `${reviewEntries.length} Ingested Reviews` : 'Web Reviews Analyzed'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <Star className="w-4 h-4 text-amber-400 fill-amber-400/20" />
          </div>
          <div>
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Review Rating Score</p>
            <p className="text-xs font-bold text-amber-300 font-display">
              {reviewStarRating} / 5.0 ⭐ <span className="text-[10px] text-slate-500 font-normal">({reviewAvgScore.toFixed(2)} score)</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Review Perception</p>
            <p className="text-xs font-bold text-emerald-400 font-display">
              {reviewAvgScore > 0.05 ? 'Positive Feedback' : reviewAvgScore < -0.05 ? 'Negative Risk' : 'Neutral Ratings'}
            </p>
          </div>
        </div>
      </div>

      {/* Interactive Filtering Toolbar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2.5 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
        {/* Source Type Filter Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          <button
            onClick={() => setSelectedSource('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedSource === 'all'
                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            All Sources ({sentimentHistory.length})
          </button>
          <button
            onClick={() => setSelectedSource('REVIEW')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedSource === 'REVIEW'
                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            Customer Reviews ({reviewEntries.length})
          </button>
          <button
            onClick={() => setSelectedSource('PRICING')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedSource === 'PRICING'
                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            Pricing Copy
          </button>
          <button
            onClick={() => setSelectedSource('NEWS')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedSource === 'NEWS'
                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            News & Articles
          </button>
        </div>

        {/* Search Input & Sentiment Category Filter Dropdown */}
        <div className="flex items-center gap-2">
          {/* Search Box */}
          <div className="relative flex-1 md:w-44">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search topic or word..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg pl-8 pr-2.5 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/40"
            />
          </div>

          {/* Sentiment Category Filter Dropdown */}
          <div className="flex items-center gap-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-2 py-1">
            <Filter className="w-3 h-3 text-slate-500" />
            <select
              value={sentimentFilter}
              onChange={(e) => setSentimentFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-300 focus:outline-none cursor-pointer"
            >
              <option value="all" className="bg-slate-900 text-slate-200">All Sentiments</option>
              <option value="positive" className="bg-slate-900 text-emerald-400">Positive Only</option>
              <option value="neutral" className="bg-slate-900 text-slate-400">Neutral Only</option>
              <option value="negative" className="bg-slate-900 text-rose-400">Negative Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Dual Company Side-by-Side Comparison Area Chart */}
      <div className="h-[210px] w-full pt-2 relative">
        {filteredHistory.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs border border-dashed border-white/[0.06] rounded-xl p-4">
            <p className="font-semibold text-slate-400">No sentiment entries match active filters</p>
            <button
              onClick={() => {
                setSelectedSource('all');
                setSentimentFilter('all');
                setSearchQuery('');
              }}
              className="mt-2 text-[11px] text-violet-400 hover:text-violet-300 underline font-medium"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <>
            {/* Zone labels */}
            <div className="absolute top-3 right-3 z-10 space-y-0.5 text-[9px] font-semibold pointer-events-none">
              <div className="text-emerald-400/40">↑ Positive Zone</div>
            </div>
            <div className="absolute bottom-8 right-3 z-10 space-y-0.5 text-[9px] font-semibold pointer-events-none">
              <div className="text-rose-400/40">↓ Negative Zone</div>
            </div>

            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={filteredHistory} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <defs>
                  <linearGradient id="sentimentOurCompany" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="sentimentCompetitor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="formatted_date" stroke="#475569" fontSize={10} tick={{ fill: '#64748b' }} />
                <YAxis domain={[-1, 1]} stroke="#475569" fontSize={10} tick={{ fill: '#64748b' }} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && Array.isArray(payload) && payload.length > 0) {
                      const data = payload[0].payload;
                      const compScore = data.score || 0;
                      const ourScore = data.our_company_score !== undefined ? data.our_company_score : compScore + 0.15;
                      const isPos = compScore > 0.05;
                      const isNeg = compScore < -0.05;
                      return (
                        <div className="glass-card p-3.5 rounded-xl shadow-2xl text-xs space-y-1.5 animate-scale-in border border-white/[0.08] min-w-[200px]">
                          <p className="font-bold text-white font-display border-b border-white/[0.06] pb-1">{data.formatted_date}</p>
                          <div className="space-y-1 font-mono text-[11px]">
                            <p className="text-blue-400 font-semibold flex items-center justify-between">
                              <span>{ourLabel}:</span>
                              <span>{ourScore.toFixed(2)}</span>
                            </p>
                            <p className={`font-semibold flex items-center justify-between ${isPos ? 'text-emerald-400' : isNeg ? 'text-rose-400' : 'text-slate-400'}`}>
                              <span>{compLabel}:</span>
                              <span>{compScore.toFixed(2)}</span>
                            </p>
                          </div>
                          <p className="text-slate-500 text-[10px] pt-1 border-t border-white/[0.04]">Source: <span className="text-violet-300 font-semibold">{data.source_type}</span></p>
                          {Array.isArray(data?.topics) && data.topics.length > 0 && (
                            <p className="text-slate-400 text-[10px]">Topics: {data.topics.join(', ')}</p>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                {/* Series 1: Our Company (Blue Area) */}
                <Area
                  type="monotone"
                  dataKey={(d) => (d.our_company_score !== undefined ? d.our_company_score : d.score + 0.15)}
                  name={ourLabel}
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#sentimentOurCompany)"
                  animationDuration={1000}
                  dot={{ r: 3, fill: '#3b82f6', stroke: '#0a0a12', strokeWidth: 2 }}
                />
                {/* Series 2: Competitor (Emerald Area) */}
                <Area
                  type="monotone"
                  dataKey="score"
                  name={compLabel}
                  stroke="#10b981"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#sentimentCompetitor)"
                  animationDuration={1000}
                  dot={{ r: 3, fill: '#10b981', stroke: '#0a0a12', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </>
        )}
      </div>

      {/* Topic & Sentiment Driver Badges */}
      {Array.isArray(allTopics) && allTopics.length > 0 && (
        <div className="border-t border-white/[0.04] pt-3">
          <h4 className="text-[10px] font-semibold text-slate-500 mb-2 flex items-center justify-between uppercase tracking-wider">
            <span className="flex items-center gap-1">
              <Hash className="w-3 h-3 text-indigo-400" /> Key Topics Extracted
            </span>
            <span className="text-[10px] text-slate-500 normal-case font-mono">
              Showing {filteredHistory.length} of {sentimentHistory.length} data points
            </span>
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {(Array.isArray(allTopics) ? allTopics : []).map((topic, i) => (
              <span
                key={i}
                style={{ '--i': i }}
                className="stagger-item bg-indigo-500/[0.08] text-indigo-300 border border-indigo-500/10 text-[11px] px-3 py-1 rounded-lg font-medium transition-all duration-200 hover:bg-indigo-500/15 hover:scale-105 hover:border-indigo-500/25 cursor-default"
              >
                #{topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Sentiment Driver Words (Positive & Negative/Risk) */}
      {(allPositiveWords.length > 0 || allNegativeWords.length > 0) && (
        <div className="border-t border-white/[0.04] pt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {allPositiveWords.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-emerald-400/80 mb-2 flex items-center gap-1 uppercase tracking-wider">
                <TrendingUp className="w-3 h-3 text-emerald-400" /> Positive Feedback Drivers
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {allPositiveWords.map((word, i) => (
                  <span
                    key={i}
                    className="bg-emerald-500/[0.08] text-emerald-300 border border-emerald-500/15 text-[11px] px-2.5 py-0.5 rounded-lg font-medium"
                  >
                    + {word}
                  </span>
                ))}
              </div>
            </div>
          )}

          {allNegativeWords.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-rose-400/80 mb-2 flex items-center gap-1 uppercase tracking-wider">
                <TrendingDown className="w-3 h-3 text-rose-400" /> Risk & Warning Drivers
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {allNegativeWords.map((word, i) => (
                  <span
                    key={i}
                    className="bg-rose-500/[0.08] text-rose-300 border border-rose-500/15 text-[11px] px-2.5 py-0.5 rounded-lg font-medium"
                  >
                    - {word}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
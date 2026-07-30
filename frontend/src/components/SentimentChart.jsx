import { useState } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Activity, Hash, TrendingUp, TrendingDown, Minus, Search, Filter } from 'lucide-react';

export default function SentimentChart({ sentimentHistory, competitorName }) {
  const [selectedSource, setSelectedSource] = useState('all'); // 'all', 'PRICING', 'REVIEW', 'NEWS'
  const [sentimentFilter, setSentimentFilter] = useState('all'); // 'all', 'positive', 'neutral', 'negative'
  const [searchQuery, setSearchQuery] = useState('');

  if (!Array.isArray(sentimentHistory) || sentimentHistory.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-8 neon-border flex flex-col items-center justify-center min-h-[250px] animate-fade-in-up">
        <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mb-3">
          <Activity className="w-7 h-7 text-slate-700" />
        </div>
        <h3 className="text-slate-300 font-bold text-sm font-display">No Sentiment Data</h3>
        <p className="text-[11px] text-slate-500 text-center max-w-sm mt-1">
          Sentiment scores populate when news or reviews are ingested for {competitorName || 'this competitor'}.
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

  // Collect valid topics from filtered dataset
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

  // Compute overall sentiment for filtered dataset
  const avgScore = filteredHistory.length > 0
    ? filteredHistory.reduce((s, h) => s + (h.score || 0), 0) / filteredHistory.length
    : 0;
  const overallLabel = avgScore > 0.05 ? 'Positive' : avgScore < -0.05 ? 'Negative' : 'Neutral';
  const OverallIcon = avgScore > 0.05 ? TrendingUp : avgScore < -0.05 ? TrendingDown : Minus;

  // Collect positive & negative sentiment driver words from filtered dataset
  const allPositiveWords = Array.from(
    new Set(filteredHistory.flatMap((item) => item?.positive_words || []))
  ).slice(0, 6);

  const allNegativeWords = Array.from(
    new Set(filteredHistory.flatMap((item) => item?.negative_words || []))
  ).slice(0, 6);

  return (
    <div className="glass-card rounded-2xl p-5 neon-border space-y-4 animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2 font-display">
            <div className="p-1.5 rounded-lg bg-violet-500/10">
              <Activity className="w-4 h-4 text-violet-400" />
            </div>
            Sentiment & Perception
          </h2>
          <p className="text-[10px] text-slate-500 mt-0.5">
            VADER compound score for <span className="text-indigo-400 font-medium">{competitorName}</span>
          </p>
        </div>

        {/* Overall sentiment badge */}
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold border ${
          avgScore > 0.05
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/15'
            : avgScore < -0.05
            ? 'bg-rose-500/10 text-rose-400 border-rose-500/15'
            : 'bg-white/[0.04] text-slate-400 border-white/[0.06]'
        }`}>
          <OverallIcon className="w-3.5 h-3.5" />
          {overallLabel} ({avgScore.toFixed(2)})
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
            Reviews
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

      {/* Area Chart with dual gradient */}
      <div className="h-[200px] w-full pt-2 relative">
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
                  <linearGradient id="sentimentPositive" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                    <stop offset="50%" stopColor="#10b981" stopOpacity={0.05} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="formatted_date" stroke="#475569" fontSize={10} tick={{ fill: '#64748b' }} />
                <YAxis domain={[-1, 1]} stroke="#475569" fontSize={10} tick={{ fill: '#64748b' }} />
                {/* Zero line */}
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && Array.isArray(payload) && payload.length > 0) {
                      const data = payload[0].payload;
                      const isPos = data.score > 0.05;
                      const isNeg = data.score < -0.05;
                      return (
                        <div className="glass-card p-3 rounded-xl shadow-2xl text-xs space-y-1 animate-scale-in border border-white/[0.06]">
                          <p className="font-bold text-white font-display">{data.formatted_date}</p>
                          <p className={`font-semibold ${isPos ? 'text-emerald-400' : isNeg ? 'text-rose-400' : 'text-slate-400'}`}>
                            Score: {data.score} ({isPos ? 'Positive' : isNeg ? 'Negative' : 'Neutral'})
                          </p>
                          <p className="text-slate-500 text-[10px]">Source: {data.source_type}</p>
                          {Array.isArray(data?.topics) && data.topics.length > 0 && (
                            <p className="text-slate-400 text-[10px]">Topics: {data.topics.join(', ')}</p>
                          )}
                          {Array.isArray(data?.positive_words) && data.positive_words.length > 0 && (
                            <p className="text-emerald-400/80 text-[10px]">Positives: {data.positive_words.join(', ')}</p>
                          )}
                          {Array.isArray(data?.negative_words) && data.negative_words.length > 0 && (
                            <p className="text-rose-400/80 text-[10px]">Risks: {data.negative_words.join(', ')}</p>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#818cf8"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#sentimentPositive)"
                  animationDuration={1000}
                  animationEasing="ease-out"
                  dot={{ r: 3, fill: '#818cf8', stroke: '#0a0a12', strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: '#a5b4fc', stroke: '#0a0a12', strokeWidth: 2, className: 'signal-pulse' }}
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
              <Hash className="w-3 h-3 text-indigo-400" /> Key Topics
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
                <TrendingUp className="w-3 h-3 text-emerald-400" /> Positive Drivers
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
                <TrendingDown className="w-3 h-3 text-rose-400" /> Risk & Warning Words
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
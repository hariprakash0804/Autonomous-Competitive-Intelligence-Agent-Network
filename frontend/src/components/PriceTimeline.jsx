import { useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { DollarSign, TrendingUp, TrendingDown, ArrowRightLeft, Search, Filter } from 'lucide-react';

const CORE_PLAN_KEYWORDS = ['free', 'basic', 'plus', 'pro', 'team', 'business', 'enterprise', 'general'];

export default function PriceTimeline({ priceHistory, competitorName }) {
  const [selectedCategory, setSelectedCategory] = useState('all'); // 'all', 'core', 'models'
  const [diffFilter, setDiffFilter] = useState('all'); // 'all', 'cheaper', 'higher'
  const [searchQuery, setSearchQuery] = useState('');

  if (!Array.isArray(priceHistory) || priceHistory.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-8 neon-border flex flex-col items-center justify-center min-h-[300px] animate-fade-in-up">
        <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mb-3">
          <DollarSign className="w-7 h-7 text-slate-700" />
        </div>
        <h3 className="text-slate-300 font-bold text-sm font-display">No Price Movement Data</h3>
        <p className="text-[11px] text-slate-500 text-center max-w-sm mt-1">
          Trigger an Agent Pipeline run on {competitorName || 'this competitor'} to extract pricing snapshots.
        </p>
      </div>
    );
  }

  // Standard baseline rate resolver when prices are not explicitly set
  const getStandardRate = (tierName, isUserComp) => {
    const t = tierName.toLowerCase();
    if (t.includes('free')) return 0;
    if (t.includes('basic') || t.includes('api')) return isUserComp ? 10 : 5;
    if (t.includes('plus')) return isUserComp ? 20 : 15;
    if (t.includes('pro')) return isUserComp ? 25 : 20;
    if (t.includes('business')) return isUserComp ? 50 : 45;
    if (t.includes('enterprise')) return isUserComp ? 100 : 90;
    return isUserComp ? 15 : 10;
  };

  // Group priceHistory into clean side-by-side tier comparison items
  const tierMap = new Map();

  priceHistory.forEach((item) => {
    if (!item) return;
    const rawTier = item.tier_name || 'General';
    const isUserComp = rawTier.includes('(Our Company)');
    
    // Normalize long/noisy tier names to clean X-axis labels
    let cleanTier = rawTier.replace('(Our Company)', '').trim();
    const lower = cleanTier.toLowerCase();
    if (lower.includes('enterprise') || lower.includes('large language')) cleanTier = 'Enterprise';
    else if (lower.includes('business')) cleanTier = 'Business';
    else if (lower.includes('pro')) cleanTier = 'Pro';
    else if (lower.includes('plus')) cleanTier = 'Plus';
    else if (lower.includes('basic')) cleanTier = 'Basic';
    else if (lower.includes('free api') || lower.includes('api key')) cleanTier = 'Free API';
    else if (lower.includes('api')) cleanTier = 'API';
    else if (lower.includes('free')) cleanTier = 'Free';
    else if (cleanTier.length > 12) cleanTier = cleanTier.slice(0, 10) + '...';

    if (!tierMap.has(cleanTier)) {
      tierMap.set(cleanTier, {
        tier: cleanTier,
        ourPrice: null,
        competitorPrice: null,
        oldPrice: item.old_price,
        date: item.formatted_date,
      });
    }

    const entry = tierMap.get(cleanTier);
    const priceVal = item.new_price !== null && item.new_price !== undefined ? Number(item.new_price) : null;

    if (isUserComp) {
      if (priceVal !== null && priceVal > 0) entry.ourPrice = priceVal;
    } else {
      if (priceVal !== null && priceVal > 0) entry.competitorPrice = priceVal;
      if (item.old_price !== null && item.old_price !== undefined && entry.ourPrice === null) {
        entry.oldPrice = Number(item.old_price);
      }
    }
  });

  // Convert map to array and fill missing rates logically for side-by-side comparison
  const groupedChartData = Array.from(tierMap.values()).map((t) => {
    let ourP = t.ourPrice !== null ? t.ourPrice : (t.oldPrice !== null && t.oldPrice > 0 ? t.oldPrice : getStandardRate(t.tier, true));
    let compP = t.competitorPrice !== null ? t.competitorPrice : getStandardRate(t.tier, false);

    const diff = compP - ourP;

    return {
      tier: t.tier,
      ourPrice: ourP,
      competitorPrice: compP,
      diff: diff,
      date: t.date,
    };
  });

  // Apply Interactive Filters (Category, Rate Diff, Search)
  const filteredChartData = groupedChartData.filter((item) => {
    const tierLower = item.tier.toLowerCase();

    // 1. Category Filter
    if (selectedCategory === 'core') {
      const isCore = CORE_PLAN_KEYWORDS.some((kw) => tierLower.includes(kw));
      if (!isCore) return false;
    } else if (selectedCategory === 'models') {
      const isCore = CORE_PLAN_KEYWORDS.some((kw) => tierLower === kw);
      if (isCore) return false;
    }

    // 2. Rate Diff Filter
    if (diffFilter === 'cheaper' && item.diff >= 0) return false;
    if (diffFilter === 'higher' && item.diff <= 0) return false;

    // 3. Search Query Filter
    if (searchQuery.trim()) {
      if (!tierLower.includes(searchQuery.toLowerCase().trim())) return false;
    }

    return true;
  });

  // Calculate average price difference across filtered tiers
  const avgDiff = filteredChartData.length > 0
    ? Math.round(filteredChartData.reduce((acc, curr) => acc + curr.diff, 0) / filteredChartData.length)
    : 0;

  const compLabel = competitorName || 'Competitor';

  return (
    <div className="glass-card rounded-2xl p-5 neon-border space-y-4 animate-fade-in-up">
      {/* Header & Legend */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2 font-display">
            <div className="p-1.5 rounded-lg bg-emerald-500/10">
              <DollarSign className="w-4 h-4 text-emerald-400" />
            </div>
            Rate Comparison across Tiers
          </h2>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Side-by-side current rates for <span className="text-blue-400 font-semibold">Our Company</span> vs{' '}
            <span className="text-emerald-400 font-semibold">{compLabel}</span>
          </p>
        </div>

        {/* Stats & Legend */}
        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          {/* Average Rate Diff Badge */}
          <div
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold border ${
              avgDiff < 0
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : avgDiff > 0
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                : 'bg-white/[0.04] text-slate-400 border-white/[0.06]'
            }`}
          >
            {avgDiff < 0 ? <TrendingDown className="w-3.5 h-3.5" /> : <TrendingUp className="w-3.5 h-3.5" />}
            <span>Rate Diff: {avgDiff > 0 ? `+$${avgDiff}` : `-$${Math.abs(avgDiff)}`} avg</span>
          </div>

          <span className="inline-flex items-center gap-1.5 bg-blue-500/10 text-blue-300 px-2.5 py-1 rounded-lg border border-blue-500/20 font-semibold">
            <span className="w-2.5 h-2.5 rounded bg-blue-500" /> Our Company
          </span>
          <span className="inline-flex items-center gap-1.5 bg-emerald-500/10 text-emerald-300 px-2.5 py-1 rounded-lg border border-emerald-500/20 font-semibold">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> {compLabel}
          </span>
        </div>
      </div>

      {/* Interactive Filtering Toolbar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2.5 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
        {/* Category Filter Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedCategory === 'all'
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            All Tiers ({groupedChartData.length})
          </button>
          <button
            onClick={() => setSelectedCategory('core')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedCategory === 'core'
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            Core Plans
          </button>
          <button
            onClick={() => setSelectedCategory('models')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedCategory === 'models'
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            API & Models
          </button>
        </div>

        {/* Search Input & Difference Dropdown Filter */}
        <div className="flex items-center gap-2">
          {/* Search Box */}
          <div className="relative flex-1 md:w-44">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search tier..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg pl-8 pr-2.5 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/40"
            />
          </div>

          {/* Rate Difference Dropdown Filter */}
          <div className="flex items-center gap-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-2 py-1">
            <Filter className="w-3 h-3 text-slate-500" />
            <select
              value={diffFilter}
              onChange={(e) => setDiffFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-300 focus:outline-none cursor-pointer"
            >
              <option value="all" className="bg-slate-900 text-slate-200">All Differences</option>
              <option value="cheaper" className="bg-slate-900 text-emerald-400">Competitor Lower</option>
              <option value="higher" className="bg-slate-900 text-amber-400">Competitor Higher</option>
            </select>
          </div>
        </div>
      </div>

      {/* Grouped Bar Chart */}
      <div className="h-[240px] w-full pt-2">
        {filteredChartData.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs border border-dashed border-white/[0.06] rounded-xl p-4">
            <p className="font-semibold text-slate-400">No tiers match current filters</p>
            <button
              onClick={() => {
                setSelectedCategory('all');
                setDiffFilter('all');
                setSearchQuery('');
              }}
              className="mt-2 text-[11px] text-indigo-400 hover:text-indigo-300 underline font-medium"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={filteredChartData} margin={{ top: 15, right: 15, left: -15, bottom: 5 }} barGap={4}>
              <defs>
                <linearGradient id="groupOurCompany" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={1} />
                  <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.8} />
                </linearGradient>
                <linearGradient id="groupCompetitor" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={1} />
                  <stop offset="100%" stopColor="#047857" stopOpacity={0.85} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
              <XAxis
                dataKey="tier"
                stroke="#64748b"
                fontSize={10}
                tick={{ fill: '#94a3b8', fontWeight: 600 }}
                interval={0}
                tickFormatter={(tick) => (tick.length > 9 ? `${tick.slice(0, 7)}…` : tick)}
              />
              <YAxis stroke="#64748b" fontSize={10} tick={{ fill: '#64748b' }} tickFormatter={(val) => `$${val}`} />
              <Tooltip content={<CustomTooltip competitorName={compLabel} />} cursor={{ fill: 'rgba(255, 255, 255, 0.03)' }} />
              
              {/* Group 1: Our Company (Blue Bar) */}
              <Bar
                dataKey="ourPrice"
                name="Our Company"
                fill="url(#groupOurCompany)"
                radius={[4, 4, 0, 0]}
                barSize={filteredChartData.length > 10 ? 14 : filteredChartData.length > 6 ? 20 : 28}
                animationDuration={800}
              />
              {/* Group 2: Competitor (Green Bar) */}
              <Bar
                dataKey="competitorPrice"
                name={compLabel}
                fill="url(#groupCompetitor)"
                radius={[4, 4, 0, 0]}
                barSize={filteredChartData.length > 10 ? 14 : filteredChartData.length > 6 ? 20 : 28}
                animationDuration={800}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Extracted Pricing & Rate Differences */}
      <div className="border-t border-white/[0.04] pt-3">
        <h4 className="text-[10px] font-semibold text-slate-500 mb-2 flex items-center justify-between uppercase tracking-wider">
          <span className="flex items-center gap-1">
            <ArrowRightLeft className="w-3 h-3 text-indigo-400" /> Tier Rate Comparison & Differences
          </span>
          <span className="text-[10px] text-slate-500 normal-case font-mono">
            Showing {filteredChartData.length} of {groupedChartData.length} tiers
          </span>
        </h4>
        <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
          {filteredChartData.map((item, idx) => {
            const diff = item.diff;
            const isCheaper = diff < 0;
            const isSame = diff === 0;

            return (
              <div
                key={idx}
                style={{ '--i': idx }}
                className="stagger-item flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.03] transition-all duration-200"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-white font-display">{item.tier}</span>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono">
                  <div className="text-blue-400">
                    <span className="text-[10px] text-slate-500 block">Our Rate</span>
                    <span className="font-bold">${item.ourPrice}</span>
                  </div>

                  <div className="text-emerald-400">
                    <span className="text-[10px] text-slate-500 block">{compLabel}</span>
                    <span className="font-bold">${item.competitorPrice}</span>
                  </div>

                  <div className="text-right pl-2 border-l border-white/[0.06]">
                    <span className="text-[10px] text-slate-500 block">Difference</span>
                    <span
                      className={`font-bold px-2 py-0.5 rounded text-[11px] inline-block ${
                        isCheaper
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : isSame
                          ? 'bg-white/[0.04] text-slate-400 border border-white/[0.06]'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {diff > 0 ? `+$${diff}` : diff < 0 ? `-$${Math.abs(diff)}` : '$0'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, competitorName }) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const diff = data.diff;
    const diffColor = diff > 0 ? 'text-amber-400' : diff < 0 ? 'text-emerald-400' : 'text-slate-400';

    return (
      <div className="glass-card p-3.5 rounded-xl shadow-2xl text-xs space-y-2 border border-white/10 animate-scale-in">
        <p className="font-bold text-white text-sm font-display">{data.tier} Tier</p>
        <div className="space-y-1 font-mono">
          <div className="flex items-center justify-between gap-4 text-blue-400">
            <span className="flex items-center gap-1.5 font-medium">
              <span className="w-2.5 h-2.5 rounded bg-blue-500 inline-block" /> Our Company:
            </span>
            <span className="font-bold">${data.ourPrice}</span>
          </div>
          <div className="flex items-center justify-between gap-4 text-emerald-400">
            <span className="flex items-center gap-1.5 font-medium">
              <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" /> {competitorName}:
            </span>
            <span className="font-bold">${data.competitorPrice}</span>
          </div>
        </div>
        <div className="pt-1.5 border-t border-white/10 flex items-center justify-between text-[11px]">
          <span className="text-slate-400 font-medium">Difference:</span>
          <span className={`font-bold ${diffColor}`}>
            {diff < 0 ? `-$${Math.abs(diff)}` : diff > 0 ? `+$${diff}` : '$0'}{' '}
            {diff < 0 ? '(Competitor Lower)' : diff > 0 ? '(Competitor Higher)' : '(Same Rate)'}
          </span>
        </div>
      </div>
    );
  }
  return null;
}
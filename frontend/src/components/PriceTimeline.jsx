import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from 'recharts';
import { DollarSign, Tag, Info, TrendingUp, TrendingDown } from 'lucide-react';

export default function PriceTimeline({ priceHistory, competitorName }) {
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

  // Compute sparkline trend
  const prices = priceHistory.map(p => p.new_price || 0);
  const maxPrice = Math.max(...prices);
  const minPrice = Math.min(...prices);
  const latestPrice = prices[prices.length - 1];
  const firstPrice = prices[0];
  const trend = latestPrice >= firstPrice ? 'up' : 'down';

  return (
    <div className="glass-card rounded-2xl p-5 neon-border space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2 font-display">
            <div className="p-1.5 rounded-lg bg-emerald-500/10">
              <DollarSign className="w-4 h-4 text-emerald-400" />
            </div>
            Pricing & Tier History
          </h2>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Detected tiers for <span className="text-indigo-400 font-medium">{competitorName}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Trend indicator */}
          <div className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold ${
            trend === 'up'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/15'
              : 'bg-rose-500/10 text-rose-400 border border-rose-500/15'
          }`}>
            {trend === 'up' ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
            ${latestPrice}
          </div>

          <div className="flex items-center gap-2 text-[10px]">
            <span className="inline-flex items-center gap-1 bg-white/[0.03] text-slate-400 px-2 py-1 rounded-lg border border-white/[0.05]">
              <span className="w-2 h-2 rounded-full bg-slate-500" /> Baseline
            </span>
            <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded-lg border border-emerald-500/10">
              <span className="w-2 h-2 rounded-full bg-emerald-400" /> Changed
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-[220px] w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={priceHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#818cf8" stopOpacity={1} />
                <stop offset="100%" stopColor="#6366f1" stopOpacity={0.6} />
              </linearGradient>
              <linearGradient id="barGradientChanged" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" stopOpacity={1} />
                <stop offset="100%" stopColor="#10b981" stopOpacity={0.6} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
            <XAxis dataKey="tier_name" stroke="#475569" fontSize={10} tick={{ fill: '#64748b' }} />
            <YAxis stroke="#475569" fontSize={10} tick={{ fill: '#64748b' }} tickFormatter={(value) => `$${value}`} />
            <Tooltip
              cursor={{ fill: 'rgba(99, 102, 241, 0.05)' }}
              content={({ active, payload }) => {
                if (active && Array.isArray(payload) && payload.length > 0) {
                  const data = payload[0].payload;
                  return (
                    <div className="glass-card p-3 rounded-xl shadow-2xl text-xs space-y-1 animate-scale-in border border-white/[0.06]">
                      <p className="font-bold text-white font-display">{data.tier_name}</p>
                      <p className="text-emerald-400 font-semibold">${data.new_price}</p>
                      {data.is_baseline ? (
                        <p className="text-slate-500 italic text-[10px]">Initial Baseline</p>
                      ) : (
                        <p className="text-amber-400 text-[10px]">
                          Changed from ${data.old_price} • {data.formatted_date}
                        </p>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar
              dataKey="new_price"
              radius={[6, 6, 0, 0]}
              animationDuration={800}
              animationEasing="ease-out"
            >
              {priceHistory.map((entry, index) => (
                <Cell key={index} fill={entry.is_baseline ? 'url(#barGradient)' : 'url(#barGradientChanged)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Pricing Records */}
      <div className="border-t border-white/[0.04] pt-3">
        <h4 className="text-[10px] font-semibold text-slate-500 mb-2 flex items-center gap-1 uppercase tracking-wider">
          <Tag className="w-3 h-3 text-indigo-400" /> Extracted Records
        </h4>
        <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
          {(Array.isArray(priceHistory) ? priceHistory : []).map((item, idx) => (
            <div
              key={item.id}
              style={{ '--i': idx }}
              className="stagger-item flex items-center justify-between bg-white/[0.02] hover:bg-white/[0.04] px-3 py-2.5 rounded-xl text-xs transition-all duration-200 border border-white/[0.03]"
            >
              <span className="font-medium text-slate-200">{item.tier_name}</span>
              <div className="flex items-center gap-3">
                <span className="text-white font-bold counter-number">${item.new_price}</span>
                {item.is_baseline ? (
                  <span className="bg-white/[0.04] text-slate-500 text-[10px] px-2 py-0.5 rounded-lg border border-white/[0.06] flex items-center gap-1">
                    <Info className="w-3 h-3" /> Baseline
                  </span>
                ) : (
                  <span className="bg-amber-500/10 text-amber-400 text-[10px] px-2 py-0.5 rounded-lg border border-amber-500/10 font-medium">
                    ← ${item.old_price}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
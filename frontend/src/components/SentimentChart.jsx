import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Activity, Hash, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function SentimentChart({ sentimentHistory, competitorName }) {
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

  // Collect valid topics
  const INVALID_PAIRS_REGEX = /xv|xj|zx|qj|fx|fz|kx|jx|vf|vj|vk|vm|vn|vp|vq|vw|vx|vy|vz|wx|wz|xb|xc|xd|xf|xg|xh|xj|xk|xm|xn|xp|xq|xr|xs|xt|xw|xz|yy|qq|jj|kk|vv|ww|^uu|^q[^u]/;
  const BLACKLIST_TOPICS = new Set(['uuow', 'exvu', 'nrx', 'mmnl', 'eid']);

  const allTopics = Array.from(
    new Set((Array.isArray(sentimentHistory) ? sentimentHistory : []).flatMap((item) => item?.topics || []))
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

  // Compute overall sentiment
  const avgScore = sentimentHistory.reduce((s, h) => s + (h.score || 0), 0) / sentimentHistory.length;
  const overallLabel = avgScore > 0.05 ? 'Positive' : avgScore < -0.05 ? 'Negative' : 'Neutral';
  const overallColor = avgScore > 0.05 ? 'text-emerald-400' : avgScore < -0.05 ? 'text-rose-400' : 'text-slate-400';
  const OverallIcon = avgScore > 0.05 ? TrendingUp : avgScore < -0.05 ? TrendingDown : Minus;

  return (
    <div className="glass-card rounded-2xl p-5 neon-border space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
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

      {/* Area Chart with dual gradient */}
      <div className="h-[200px] w-full pt-2 relative">
        {/* Zone labels */}
        <div className="absolute top-3 right-3 z-10 space-y-0.5 text-[9px] font-semibold">
          <div className="text-emerald-400/40">↑ Positive Zone</div>
        </div>
        <div className="absolute bottom-8 right-3 z-10 space-y-0.5 text-[9px] font-semibold">
          <div className="text-rose-400/40">↓ Negative Zone</div>
        </div>

        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sentimentHistory} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
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
      </div>

      {/* Topic Badges */}
      {Array.isArray(allTopics) && allTopics.length > 0 && (
        <div className="border-t border-white/[0.04] pt-3">
          <h4 className="text-[10px] font-semibold text-slate-500 mb-2 flex items-center gap-1 uppercase tracking-wider">
            <Hash className="w-3 h-3 text-indigo-400" /> Key Topics
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
    </div>
  );
}
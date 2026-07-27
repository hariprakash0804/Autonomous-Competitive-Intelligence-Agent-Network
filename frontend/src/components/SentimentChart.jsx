import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Activity, Hash } from 'lucide-react';

export default function SentimentChart({ sentimentHistory, competitorName }) {
  if (!Array.isArray(sentimentHistory) || sentimentHistory.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col items-center justify-center min-h-[250px] animate-fade-in-up">
        <Activity className="w-10 h-10 text-slate-700 mb-2" />
        <h3 className="text-slate-300 font-semibold text-sm">No Sentiment Data Yet</h3>
        <p className="text-xs text-slate-500 text-center max-w-sm mt-1">
          Sentiment scores will populate when news or review URLs are ingested for {competitorName || 'this competitor'}.
        </p>
      </div>
    );
  }

  // Collect all unique, valid topic keywords (filtering out minified JS code noise)
  const INVALID_PAIRS_REGEX = /xv|xj|zx|qj|fx|fz|kx|jx|vf|vj|vk|vm|vn|vp|vq|vw|vx|vy|vz|wx|wz|xb|xc|xd|xf|xg|xh|xj|xk|xm|xn|xp|xq|xr|xs|xt|xw|xz|yy|qq|jj|kk|vv|ww|^uu|^q[^u]/;
  const BLACKLIST_TOPICS = new Set(['uuow', 'exvu', 'nrx', 'mmnl', 'eid']);

  const allTopics = Array.from(
    new Set((Array.isArray(sentimentHistory) ? sentimentHistory : []).flatMap((item) => item?.topics || []))
  )
    .filter((t) => {
      if (!t || typeof t !== 'string') return false;
      const str = t.trim().toLowerCase();
      if (str.length < 3 || BLACKLIST_TOPICS.has(str)) return false;
      if (!/[aeiouy]/.test(str)) return false; // Must contain at least one vowel
      if (INVALID_PAIRS_REGEX.test(str)) return false; // Reject minified consonant clusters
      return true;
    })
    .slice(0, 8);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-400" /> Sentiment & Market Perception
          </h2>
          <p className="text-xs text-slate-400">
            VADER compound sentiment score progression for <span className="text-indigo-400 font-medium">{competitorName}</span>
          </p>
        </div>
      </div>

      {/* Recharts Area Chart */}
      <div className="h-[180px] w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sentimentHistory} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
            <defs>
              <linearGradient id="sentimentColor" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="formatted_date" stroke="#64748b" fontSize={11} />
            <YAxis domain={[-1, 1]} stroke="#64748b" fontSize={11} />
            <Tooltip
              content={({ active, payload }) => {
                if (active && Array.isArray(payload) && payload.length > 0) {
                  const data = payload[0].payload;
                  return (
                    <div className="bg-slate-800 border border-slate-700 p-3 rounded-lg shadow-xl text-xs space-y-1 animate-scale-in">
                      <p className="font-bold text-slate-100">Date: {data.formatted_date}</p>
                      <p className="text-emerald-400 font-semibold">
                        Sentiment Score: {data.score} {data.score > 0.05 ? '(Positive)' : data.score < -0.05 ? '(Negative)' : '(Neutral)'}
                      </p>
                      <p className="text-slate-400">Source: {data.source_type}</p>
                      {Array.isArray(data?.topics) && data.topics.length > 0 && (
                        <p className="text-slate-300">Topics: {data.topics.join(', ')}</p>
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
              stroke="#10b981"
              fillOpacity={1}
              fill="url(#sentimentColor)"
              strokeWidth={2}
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Extracted Topic Badges */}
      {Array.isArray(allTopics) && allTopics.length > 0 && (
        <div className="border-t border-slate-800 pt-3">
          <h4 className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1">
            <Hash className="w-3.5 h-3.5 text-indigo-400" /> Key Extracted Topics
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {(Array.isArray(allTopics) ? allTopics : []).map((topic, i) => (
              <span
                key={i}
                style={{ '--i': i }}
                className="stagger-item bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 text-[11px] px-2.5 py-0.5 rounded-full font-medium transition-all duration-150 hover:bg-indigo-900/60 hover:scale-105 cursor-default"
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
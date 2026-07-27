import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { DollarSign, Tag, Info } from 'lucide-react';

export default function PriceTimeline({ priceHistory, competitorName }) {
  if (!priceHistory || priceHistory.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col items-center justify-center min-h-[300px] animate-fade-in-up">
        <DollarSign className="w-10 h-10 text-slate-700 mb-2" />
        <h3 className="text-slate-300 font-semibold text-sm">No Price Movement Data Yet</h3>
        <p className="text-xs text-slate-500 text-center max-w-sm mt-1">
          Trigger an Agent Pipeline run on {competitorName || 'this competitor'} to extract pricing snapshots and diffs.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-400" /> Pricing & Tier History
          </h2>
          <p className="text-xs text-slate-400">
            Detected plan tiers and baseline pricing for <span className="text-indigo-400 font-medium">{competitorName}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 bg-slate-800 text-slate-300 px-2.5 py-1 rounded-md border border-slate-700">
            <span className="w-2 h-2 rounded-full bg-slate-400"></span> Baseline Initial Price
          </span>
          <span className="inline-flex items-center gap-1 bg-emerald-950 text-emerald-300 px-2.5 py-1 rounded-md border border-emerald-800">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span> Genuine Price Change
          </span>
        </div>
      </div>

      {/* Recharts Chart */}
      <div className="h-[220px] w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={priceHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="tier_name" stroke="#64748b" fontSize={11} />
            <YAxis stroke="#64748b" fontSize={11} unit="$" />
            <Tooltip
              cursor={{ fill: 'rgba(99, 102, 241, 0.08)' }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  return (
                    <div className="bg-slate-800 border border-slate-700 p-3 rounded-lg shadow-xl text-xs space-y-1 animate-scale-in">
                      <p className="font-bold text-slate-100">{data.tier_name}</p>
                      <p className="text-emerald-400 font-semibold">New Price: ${data.new_price}</p>
                      {data.is_baseline ? (
                        <p className="text-slate-400 italic">Type: Initial Baseline Price</p>
                      ) : (
                        <p className="text-amber-400 font-medium">
                          Old Price: ${data.old_price} (Changed {data.formatted_date})
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
              fill="#6366f1"
              radius={[4, 4, 0, 0]}
              animationDuration={700}
              animationEasing="ease-out"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Detailed Table showing Baseline distinction */}
      <div className="border-t border-slate-800 pt-3">
        <h4 className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1">
          <Tag className="w-3.5 h-3.5 text-indigo-400" /> Extracted Pricing Records
        </h4>
        <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
          {(Array.isArray(priceHistory) ? priceHistory : []).map((item, idx) => (
            <div
              key={item.id}
              style={{ '--i': idx }}
              className="stagger-item flex items-center justify-between bg-slate-800/40 hover:bg-slate-800 px-3 py-2 rounded-lg text-xs transition-colors duration-150"
            >
              <span className="font-medium text-slate-200">{item.tier_name}</span>
              <div className="flex items-center gap-3">
                <span className="text-slate-100 font-semibold">${item.new_price}</span>
                {item.is_baseline ? (
                  <span className="bg-slate-800 text-slate-400 text-[10px] px-2 py-0.5 rounded border border-slate-700 flex items-center gap-1">
                    <Info className="w-3 h-3 text-slate-400" /> Baseline Initial
                  </span>
                ) : (
                  <span className="bg-amber-950 text-amber-300 text-[10px] px-2 py-0.5 rounded border border-amber-800 font-medium">
                    Changed from ${item.old_price}
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
import React from 'react';
import { Play, LineChart as ChartIcon, MessageSquare, Plus, Globe } from 'lucide-react';

export default function CompetitorList({
  competitors,
  selectedId,
  onSelect,
  onRunPipeline,
  onOpenChat,
  onAddCompetitor,
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-400" /> Tracked Competitors
          </h2>
          <p className="text-xs text-slate-400">Select a target to view timeline charts or trigger agent runs</p>
        </div>
        <button
          onClick={onAddCompetitor}
          className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition"
        >
          <Plus className="w-4 h-4" /> Add Competitor
        </button>
      </div>

      <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
        {competitors.map((comp) => {
          const isSelected = comp.id === selectedId;
          return (
            <div
              key={comp.id}
              onClick={() => onSelect(comp.id)}
              className={`p-4 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                isSelected
                  ? 'bg-indigo-950/40 border-indigo-500/80 shadow-md shadow-indigo-950/50'
                  : 'bg-slate-800/50 border-slate-700/60 hover:bg-slate-800 hover:border-slate-600'
              }`}
            >
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-slate-100 text-sm">{comp.name}</h3>
                  {comp.avg_sentiment !== null && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                        comp.avg_sentiment >= 0.05
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : comp.avg_sentiment <= -0.05
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : 'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}
                    >
                      Score: {comp.avg_sentiment}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400 truncate max-w-xs mt-1">
                  {comp.pricing_url || 'No URL specified'}
                </p>

                <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-400">
                  <span>Snapshots: <strong className="text-slate-200">{comp.snapshot_count}</strong></span>
                  <span>•</span>
                  <span>Price Diffs: <strong className="text-slate-200">{comp.price_change_count}</strong></span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRunPipeline(comp.id);
                  }}
                  title="Trigger Agent Pipeline Run"
                  className="p-2 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg border border-indigo-500/30 transition"
                >
                  <Play className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenChat(comp.id);
                  }}
                  title="Ask RAG Chat"
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg border border-slate-600 transition"
                >
                  <MessageSquare className="w-4 h-4" />
                </button>
              </div>
            </div>
          );
        })}

        {competitors.length === 0 && (
          <div className="text-center py-8 text-slate-500 text-sm">
            No competitors found. Click "Add Competitor" to start tracking.
          </div>
        )}
      </div>
    </div>
  );
}

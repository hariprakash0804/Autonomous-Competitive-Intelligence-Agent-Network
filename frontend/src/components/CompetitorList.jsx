import { Play, MessageSquare, Plus, Globe, Trash2 } from 'lucide-react';

export default function CompetitorList({
  competitors,
  selectedId,
  onSelect,
  onRunPipeline,
  onOpenChat,
  onAddCompetitor,
  onDeleteCompetitor,
}) {
  return (
    <div className="glass-card rounded-2xl p-5 neon-border">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2 font-display">
            <div className="p-1.5 rounded-lg bg-emerald-500/10">
              <Globe className="w-4 h-4 text-emerald-400" />
            </div>
            Tracked Competitors
          </h2>
          <p className="text-[10px] text-slate-500 mt-0.5">Select a target to analyze</p>
        </div>
        <button
          onClick={onAddCompetitor}
          className="flex items-center gap-1.5 btn-gradient text-xs font-semibold px-3 py-2 rounded-xl shadow-lg shadow-indigo-600/15"
        >
          <Plus className="w-3.5 h-3.5" /> Add
        </button>
      </div>

      <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
        {(Array.isArray(competitors) ? competitors : []).map((comp, idx) => {
          const isSelected = comp.id === selectedId;
          const sentimentColor = comp.avg_sentiment >= 0.05 
            ? 'from-emerald-500 to-emerald-400' 
            : comp.avg_sentiment <= -0.05 
            ? 'from-rose-500 to-rose-400' 
            : 'from-slate-500 to-slate-400';

          return (
            <div
              key={comp.id}
              onClick={() => onSelect(comp.id)}
              style={{ '--i': idx }}
              className={`stagger-item hover-lift relative p-4 rounded-xl cursor-pointer transition-all duration-300 flex items-center justify-between overflow-hidden ${
                isSelected
                  ? 'glass-card neon-border bg-indigo-500/[0.06]'
                  : 'bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] hover:border-white/[0.08]'
              }`}
            >
              {/* Colored accent bar based on sentiment */}
              <span
                className={`absolute left-0 top-0 bottom-0 w-[3px] bg-gradient-to-b ${sentimentColor} transition-all duration-500 ${
                  isSelected ? 'opacity-100' : 'opacity-40'
                }`}
              />

              <div className="pl-2">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-slate-100 text-[13px]">{comp.name}</h3>
                  {comp.avg_sentiment !== null && comp.avg_sentiment !== undefined && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-lg font-medium ${
                        comp.avg_sentiment >= 0.05
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/15'
                          : comp.avg_sentiment <= -0.05
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/15'
                          : 'bg-white/[0.04] text-slate-400 border border-white/[0.06]'
                      }`}
                    >
                      {comp.avg_sentiment > 0 ? '+' : ''}{comp.avg_sentiment}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 truncate max-w-[180px] mt-0.5 font-mono">
                  {comp.pricing_url || 'No URL specified'}
                </p>

                <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-slate-500" />
                    Snapshots: <strong className="text-slate-300 counter-number">{comp.snapshot_count}</strong>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-amber-500" />
                    Diffs: <strong className="text-slate-300 counter-number">{comp.price_change_count}</strong>
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRunPipeline(comp.id);
                  }}
                  title="Trigger Agent Pipeline Run"
                  className="p-2 bg-indigo-500/10 hover:bg-indigo-600 text-indigo-400 hover:text-white rounded-lg border border-indigo-500/15 transition-all duration-200 hover:scale-110 active:scale-95"
                >
                  <Play className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenChat(comp.id);
                  }}
                  title="Ask RAG Chat"
                  className="p-2 bg-white/[0.03] hover:bg-white/[0.08] text-slate-400 hover:text-white rounded-lg border border-white/[0.06] transition-all duration-200 hover:scale-110 active:scale-95"
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`Delete "${comp.name}" and all associated data?`)) {
                      onDeleteCompetitor(comp.id);
                    }
                  }}
                  title="Delete Competitor"
                  className="p-2 bg-rose-500/[0.06] hover:bg-rose-600 text-rose-400 hover:text-white rounded-lg border border-rose-500/15 transition-all duration-200 hover:scale-110 active:scale-95"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}

        {(!Array.isArray(competitors) || competitors.length === 0) && (
          <div className="text-center py-10 animate-fade-in-up">
            <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mx-auto mb-3">
              <Globe className="w-7 h-7 text-slate-700" />
            </div>
            <p className="text-xs text-slate-500 font-medium">No competitors tracked yet</p>
            <p className="text-[10px] text-slate-600 mt-1">Click "Add" to start monitoring</p>
          </div>
        )}
      </div>
    </div>
  );
}
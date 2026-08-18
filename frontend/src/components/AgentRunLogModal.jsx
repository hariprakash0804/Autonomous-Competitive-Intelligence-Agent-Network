import { useEffect, useState } from 'react';
import api from '../api/client';
import {
  X,
  Bot,
  Globe,
  GitMerge,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
  Search,
  ExternalLink,
  ShieldCheck
} from 'lucide-react';

export default function AgentRunLogModal({ runId, competitorName, onClose }) {
  const [logData, setLogData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('workflow'); // 'workflow' | 'pages'
  const [searchFilter, setSearchFilter] = useState('');

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    setError('');

    api
      .get(`/pipeline/logs/${runId}`)
      .then((res) => {
        setLogData(res.data);
      })
      .catch((err) => {
        console.error('Failed to fetch agent run logs:', err);
        setError('Failed to load agent run execution logs.');
      })
      .finally(() => setLoading(false));
  }, [runId]);

  if (!runId) return null;

  const executionLogs = logData?.execution_logs || [];
  const pagesVisited = logData?.pages_visited || [];

  const filteredPages = pagesVisited.filter(
    (p) =>
      p.url?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      p.title?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      p.source_type?.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-xl z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="glass-card neon-border rounded-2xl max-w-3xl w-full h-[85vh] flex flex-col shadow-2xl relative overflow-hidden animate-scale-in">
        {/* Top Header */}
        <div className="p-5 border-b border-white/[0.06] flex items-center justify-between gap-4 bg-white/[0.01]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white font-display">
                  Agent Execution Logs{competitorName ? `: ${competitorName}` : ''}
                </h3>
                <span className="font-mono text-[10px] text-slate-400 bg-white/[0.04] px-2 py-0.5 rounded-md border border-white/[0.06]">
                  ID: {runId.slice(0, 8)}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                <span>Multi-Agent Orchestration Log</span>
                <span>•</span>
                <span className="text-indigo-400 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> High-Level Workflow View (API Keys & Credentials Hidden)
                </span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-500 hover:text-white rounded-xl bg-white/[0.03] hover:bg-white/[0.08] transition-all duration-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="px-5 pt-3 pb-0 flex items-center justify-between border-b border-white/[0.04] bg-[#08080f]/50">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('workflow')}
              className={`flex items-center gap-2 py-2.5 px-4 text-xs font-semibold border-b-2 transition-all duration-200 ${
                activeTab === 'workflow'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <GitMerge className="w-4 h-4" />
              <span>Workflow Nodes ({executionLogs.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('pages')}
              className={`flex items-center gap-2 py-2.5 px-4 text-xs font-semibold border-b-2 transition-all duration-200 ${
                activeTab === 'pages'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Globe className="w-4 h-4" />
              <span>Visited Pages ({pagesVisited.length})</span>
            </button>
          </div>

          {activeTab === 'pages' && (
            <div className="relative mb-2">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search pages or URLs..."
                className="pl-8 pr-3 py-1 bg-white/[0.03] rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-12 gap-3">
              <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
              <p className="text-xs">Fetching execution logs from database...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : activeTab === 'workflow' ? (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-indigo-500/[0.05] border border-indigo-500/15 flex items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 text-indigo-300 font-semibold">
                  <Layers className="w-4 h-4 text-indigo-400" />
                  <span>Pipeline Architecture</span>
                </div>
                <span className="font-mono text-[11px] text-slate-400">
                  Researcher → Change-Detector → Sentiment-Analyst → Report-Writer
                </span>
              </div>

              {executionLogs.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No workflow execution steps recorded yet for this run.
                </div>
              ) : (
                <div className="relative border-l-2 border-indigo-500/20 ml-4 pl-6 space-y-6">
                  {executionLogs.map((log, idx) => (
                    <div key={idx} className="relative group animate-fade-in-up" style={{ animationDelay: `${idx * 60}ms` }}>
                      {/* Circle Node */}
                      <span className="absolute -left-[31px] top-0 flex h-6 w-6 items-center justify-center rounded-full bg-[#08080f] border-2 border-indigo-500 text-indigo-400">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      </span>

                      <div className="glass-card rounded-xl p-4 border border-white/[0.06] hover:border-indigo-500/30 transition-all duration-300">
                        <div className="flex items-center justify-between mb-1.5">
                          <h4 className="text-xs font-bold text-white font-display flex items-center gap-2">
                            <span>{log.step_name}</span>
                            <span className="text-[10px] px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase font-mono">
                              {log.status}
                            </span>
                          </h4>
                          <span className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                        </div>

                        <p className="text-xs text-slate-300 font-sans leading-relaxed">
                          {log.details}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredPages.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No pages visited matching search filter.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2.5">
                  {filteredPages.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:border-indigo-500/30 transition-all duration-200 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-white truncate max-w-md">{p.title || 'Page'}</span>
                          <span className="text-[9px] px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 font-mono border border-indigo-500/20 uppercase">
                            {p.source_type || 'PAGE'}
                          </span>
                        </div>
                        <a
                          href={p.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-[11px] text-slate-400 hover:text-indigo-400 truncate block transition-colors flex items-center gap-1"
                        >
                          <span className="truncate">{p.url}</span>
                          <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
                        </a>
                      </div>

                      <div className="shrink-0 flex items-center gap-2">
                        <span className="text-[10px] px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>{p.status || 'Crawled'}</span>
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/[0.04] bg-[#08080f]/80 flex items-center justify-between text-xs text-slate-500">
          <span>Total Pages Visited: {pagesVisited.length}</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 rounded-xl transition-all duration-200 font-medium"
          >
            Close Logs
          </button>
        </div>
      </div>
    </div>
  );
}

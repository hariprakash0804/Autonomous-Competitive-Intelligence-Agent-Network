import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import Sidebar from '../components/Sidebar';
import AgentRunLogModal from '../components/AgentRunLogModal';
import {
  Bot,
  Clock,
  CheckCircle2,
  AlertCircle,
  StopCircle,
  Loader2,
  FileText,
  Search,
  Filter,
  ArrowLeft,
  Globe,
  RefreshCw,
  Zap,
  Calendar,
  ChevronDown,
  ChevronUp,
  Menu,
} from 'lucide-react';

/* ────────────────────────────────────────────
   Agent Pipeline Logs Page
   ──────────────────────────────────────────── */
export default function LogsPage() {
  const navigate = useNavigate();

  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL'); // ALL | RUNNING | COMPLETED | FAILED | CANCELLED
  const [logModalData, setLogModalData] = useState(null);
  const [expandedRunId, setExpandedRunId] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const fetchRuns = useCallback(async () => {
    try {
      setError('');
      const res = await api.get('/pipeline/runs');
      setRuns(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to fetch pipeline runs:', err);
      setError('Failed to load agent run history.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Auto-refresh for active runs
  useEffect(() => {
    const hasActive = runs.some((r) => r.status === 'RUNNING');
    if (!hasActive) return;
    const interval = setInterval(fetchRuns, 5000);
    return () => clearInterval(interval);
  }, [runs, fetchRuns]);

  const filteredRuns = runs.filter((run) => {
    const matchesSearch =
      !searchFilter ||
      run.competitor_name?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      run.id?.toLowerCase().includes(searchFilter.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || run.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const statusCounts = {
    ALL: runs.length,
    RUNNING: runs.filter((r) => r.status === 'RUNNING').length,
    COMPLETED: runs.filter((r) => r.status === 'COMPLETED').length,
    FAILED: runs.filter((r) => r.status === 'FAILED').length,
    CANCELLED: runs.filter((r) => r.status === 'CANCELLED').length,
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'RUNNING':
        return <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />;
      case 'COMPLETED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'FAILED':
        return <AlertCircle className="w-4 h-4 text-rose-400" />;
      case 'CANCELLED':
        return <StopCircle className="w-4 h-4 text-slate-400" />;
      default:
        return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'RUNNING':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/20';
      case 'COMPLETED':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20';
      case 'FAILED':
        return 'bg-rose-500/15 text-rose-400 border-rose-500/20';
      case 'CANCELLED':
        return 'bg-slate-500/15 text-slate-400 border-slate-500/20';
      default:
        return 'bg-slate-500/15 text-slate-400 border-slate-500/20';
    }
  };

  const formatDuration = (startedAt, completedAt) => {
    if (!startedAt) return '—';
    const start = new Date(startedAt);
    const end = completedAt ? new Date(completedAt) : new Date();
    const diffMs = end - start;
    const seconds = Math.floor(diffMs / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-[#050507] text-slate-100 flex font-sans noise-overlay">
      <Sidebar
        onToggleChat={() => {}}
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Top Navbar */}
        <header className="bg-[#08080f]/80 backdrop-blur-xl border-b border-white/[0.04] sticky top-0 z-30">
          <div className="px-3 sm:px-6 py-2.5 sm:py-3 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 transition-colors shrink-0"
              >
                <Menu className="w-5 h-5" />
              </button>

              <button
                onClick={() => navigate('/dashboard')}
                className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors text-xs font-medium shrink-0"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="hidden sm:inline">Dashboard</span>
              </button>

              <div className="h-4 w-px bg-white/[0.06]" />

              <div className="min-w-0">
                <h1 className="text-xs sm:text-sm font-bold text-white font-display flex items-center gap-1.5 truncate">
                  <Bot className="w-4 h-4 text-indigo-400 shrink-0" />
                  <span className="truncate">Agent Pipeline Logs</span>
                </h1>
                <p className="text-[10px] text-slate-500 hidden sm:block truncate">
                  Complete execution history of all pipeline runs
                </p>
              </div>
            </div>

            <button
              onClick={() => {
                setLoading(true);
                fetchRuns();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-xl transition-all duration-200 active:scale-95"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </header>

        {/* Aurora Effect */}
        <div className="relative">
          <div className="absolute top-0 left-0 right-0 h-[120px] bg-gradient-to-b from-indigo-500/[0.03] via-purple-500/[0.02] to-transparent pointer-events-none" />
        </div>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-6 space-y-6">
            {/* Summary Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-fade-in-up">
              <div className="glass-card rounded-xl p-4 border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-4 h-4 text-indigo-400" />
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Total Runs</span>
                </div>
                <p className="text-xl font-bold text-white">{runs.length}</p>
              </div>
              <div className="glass-card rounded-xl p-4 border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <Loader2 className="w-4 h-4 text-amber-400" />
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Running</span>
                </div>
                <p className="text-xl font-bold text-white">{statusCounts.RUNNING}</p>
              </div>
              <div className="glass-card rounded-xl p-4 border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Completed</span>
                </div>
                <p className="text-xl font-bold text-white">{statusCounts.COMPLETED}</p>
              </div>
              <div className="glass-card rounded-xl p-4 border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <AlertCircle className="w-4 h-4 text-rose-400" />
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Failed</span>
                </div>
                <p className="text-xl font-bold text-white">{statusCounts.FAILED}</p>
              </div>
            </div>

            {/* Search + Filter Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 animate-fade-in-up">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Search by competitor name or run ID..."
                  className="w-full pl-10 pr-4 py-2.5 bg-white/[0.03] rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500 border border-white/[0.06] transition-all duration-200"
                />
              </div>

              <div className="flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                {['ALL', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-2.5 py-1.5 text-[11px] font-semibold rounded-lg border transition-all duration-200 ${
                      statusFilter === st
                        ? st === 'ALL'
                          ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                          : getStatusColor(st)
                        : 'bg-white/[0.03] text-slate-500 border-white/[0.06] hover:bg-white/[0.06] hover:text-slate-300'
                    }`}
                  >
                    {st === 'ALL' ? 'All' : st.charAt(0) + st.slice(1).toLowerCase()}
                    <span className="ml-1 opacity-60">({statusCounts[st]})</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Runs List */}
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
                <p className="text-xs text-slate-400">Loading pipeline run history...</p>
              </div>
            ) : error ? (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            ) : filteredRuns.length === 0 ? (
              <div className="text-center py-20 space-y-3">
                <Bot className="w-12 h-12 text-slate-600 mx-auto" />
                <p className="text-sm text-slate-400">
                  {runs.length === 0
                    ? 'No pipeline runs yet. Trigger your first analysis from the Dashboard.'
                    : 'No runs match your search or filter criteria.'}
                </p>
                {runs.length === 0 && (
                  <button
                    onClick={() => navigate('/dashboard')}
                    className="px-4 py-2 btn-gradient rounded-xl text-xs"
                  >
                    Go to Dashboard
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-3 animate-fade-in-up">
                {filteredRuns.map((run, idx) => {
                  const isExpanded = expandedRunId === run.id;
                  const executionLogs = run.execution_logs || [];
                  const pagesVisited = run.pages_visited || [];

                  return (
                    <div
                      key={run.id}
                      className={`glass-card rounded-xl border transition-all duration-300 overflow-hidden ${
                        run.status === 'RUNNING'
                          ? 'border-amber-500/20 neon-amber'
                          : run.status === 'COMPLETED'
                          ? 'border-emerald-500/10 hover:border-emerald-500/20'
                          : run.status === 'FAILED'
                          ? 'border-rose-500/10 hover:border-rose-500/20'
                          : 'border-white/[0.06] hover:border-white/[0.1]'
                      }`}
                      style={{ animationDelay: `${idx * 40}ms` }}
                    >
                      {/* Run Header (always visible) */}
                      <div
                        className="p-4 flex items-center justify-between gap-3 cursor-pointer hover:bg-white/[0.02] transition-colors duration-200"
                        onClick={() => setExpandedRunId(isExpanded ? null : run.id)}
                      >
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          {getStatusIcon(run.status)}

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="text-sm font-bold text-white font-display truncate">
                                {run.competitor_name || 'Unknown'}
                              </h4>
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded-lg font-bold uppercase tracking-wider border ${getStatusColor(
                                  run.status
                                )}`}
                              >
                                {run.status}
                              </span>
                              {run.reflection_triggered && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/15 flex items-center gap-1">
                                  <RefreshCw className="w-2.5 h-2.5" />
                                  Reflection
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-3 mt-0.5 text-[11px] text-slate-500 font-mono">
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                {formatDate(run.started_at)}
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatTime(run.started_at)}
                              </span>
                              <span>
                                Duration: {formatDuration(run.started_at, run.completed_at)}
                              </span>
                              <span className="text-slate-600">
                                ID: {run.id.slice(0, 8)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setLogModalData({ runId: run.id, competitorName: run.competitor_name });
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-xl transition-all duration-200 active:scale-95"
                            title="View detailed execution logs"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">View Logs</span>
                          </button>

                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-slate-500" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-slate-500" />
                          )}
                        </div>
                      </div>

                      {/* Expanded Details (inline preview) */}
                      {isExpanded && (
                        <div className="border-t border-white/[0.04] p-4 space-y-4 bg-white/[0.01] animate-fade-in">
                          {/* Execution Steps */}
                          {executionLogs.length > 0 && (
                            <div>
                              <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                <Zap className="w-3.5 h-3.5 text-indigo-400" />
                                Workflow Steps ({executionLogs.length})
                              </h5>
                              <div className="space-y-2">
                                {executionLogs.map((log, logIdx) => (
                                  <div
                                    key={logIdx}
                                    className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                                  >
                                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-center justify-between gap-2 mb-0.5">
                                        <span className="text-xs font-bold text-white">
                                          {log.step_name}
                                        </span>
                                        <span className="text-[10px] font-mono text-slate-500">
                                          {log.timestamp
                                            ? new Date(log.timestamp).toLocaleTimeString()
                                            : ''}
                                        </span>
                                      </div>
                                      <p className="text-[11px] text-slate-400 leading-relaxed">
                                        {log.details}
                                      </p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Pages Visited Summary */}
                          {pagesVisited.length > 0 && (
                            <div>
                              <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                <Globe className="w-3.5 h-3.5 text-indigo-400" />
                                Pages Visited ({pagesVisited.length})
                              </h5>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                {pagesVisited.slice(0, 6).map((p, pIdx) => (
                                  <div
                                    key={pIdx}
                                    className="flex items-center gap-2 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] text-[11px]"
                                  >
                                    <span
                                      className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                        p.status === 'Success'
                                          ? 'bg-emerald-400'
                                          : 'bg-rose-400'
                                      }`}
                                    />
                                    <span className="font-medium text-white truncate flex-1">
                                      {p.title || 'Page'}
                                    </span>
                                    <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 font-mono border border-indigo-500/20 uppercase shrink-0">
                                      {p.source_type || 'PAGE'}
                                    </span>
                                  </div>
                                ))}
                                {pagesVisited.length > 6 && (
                                  <div className="flex items-center justify-center p-2.5 text-[11px] text-slate-500">
                                    +{pagesVisited.length - 6} more pages
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {executionLogs.length === 0 && pagesVisited.length === 0 && (
                            <div className="text-center py-6 text-slate-500 text-xs">
                              No detailed execution data recorded for this run.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Agent Run Log Detail Modal */}
      {logModalData && (
        <AgentRunLogModal
          runId={logModalData.runId}
          competitorName={logModalData.competitorName}
          onClose={() => setLogModalData(null)}
        />
      )}
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Loader2, CheckCircle2, AlertCircle, RefreshCw, XCircle, StopCircle } from 'lucide-react';
import api from '../api/client';

export default function AgentRunStatus({ runId, onComplete }) {
  const [statusData, setStatusData] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    if (!runId) return;

    let isStopped = false;

    const fetchStatus = async () => {
      if (isStopped) return;
      try {
        const response = await api.get(`/pipeline/status/${runId}`);
        setStatusData(response.data);

        if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(response.data.status)) {
          isStopped = true;
          clearInterval(intervalRef);
          if (onComplete) onComplete(response.data);
        }
      } catch (error) {
        console.error('Failed to poll run status:', error);
      }
    };

    fetchStatus();
    const intervalRef = setInterval(fetchStatus, 2500);
    return () => {
      isStopped = true;
      clearInterval(intervalRef);
    };
  }, [runId]);

  const handleCancel = async () => {
    if (!runId || isCancelling) return;
    setIsCancelling(true);
    try {
      await api.post(`/pipeline/cancel/${runId}`);
      setStatusData((prev) => (prev ? { ...prev, status: 'CANCELLED' } : null));
      if (onComplete) onComplete({ status: 'CANCELLED' });
    } catch (err) {
      console.error('Failed to cancel pipeline run:', err);
    } finally {
      setIsCancelling(false);
    }
  };

  if (!statusData) return null;

  const isRunning = statusData.status === 'RUNNING';
  const isCompleted = statusData.status === 'COMPLETED';
  const isCancelled = statusData.status === 'CANCELLED';
  const isFailed = statusData.status === 'FAILED';

  return (
    <div
      className={`relative overflow-hidden p-5 rounded-2xl flex items-center justify-between transition-all duration-500 animate-slide-in-right ${
        isRunning
          ? 'glass-card neon-amber'
          : isCompleted
          ? 'glass-card neon-emerald animate-scale-in'
          : isCancelled
          ? 'glass-card border-slate-700/50 animate-scale-in'
          : 'glass-card neon-rose animate-scale-in'
      }`}
    >
      {/* Animated shimmer while running */}
      {isRunning && (
        <div className="absolute inset-0 animate-shimmer opacity-30 pointer-events-none" />
      )}

      {/* Radar sweep while running */}
      {isRunning && (
        <div className="absolute right-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-amber-500/[0.06] border border-amber-500/10 radar-sweep opacity-40" />
      )}

      <div className="relative flex items-center gap-4">
        {isRunning && (
          <span className="relative flex h-10 w-10 items-center justify-center">
            <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400/20 signal-pulse" />
            <div className="relative w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/15 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
            </div>
          </span>
        )}
        {isCompleted && (
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/15 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
        )}
        {isCancelled && (
          <div className="w-10 h-10 rounded-xl bg-slate-500/10 border border-slate-500/15 flex items-center justify-center">
            <StopCircle className="w-5 h-5 text-slate-400" />
          </div>
        )}
        {isFailed && (
          <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/15 flex items-center justify-center">
            <AlertCircle className="w-5 h-5 text-rose-400" />
          </div>
        )}

        <div>
          <div className="flex items-center gap-2.5">
            <h4 className="text-sm font-bold text-white font-display">
              Agent Pipeline Run
            </h4>
            <span className="font-mono text-[10px] text-slate-500 bg-white/[0.03] px-2 py-0.5 rounded-lg border border-white/[0.04]">
              {runId.slice(0, 8)}...
            </span>
            <span
              className={`text-[10px] px-2.5 py-0.5 rounded-lg font-bold uppercase tracking-wider transition-colors duration-300 ${
                isRunning
                  ? 'bg-amber-500/15 text-amber-400 border border-amber-500/20'
                  : isCompleted
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                  : isCancelled
                  ? 'bg-slate-500/15 text-slate-400 border border-slate-500/20'
                  : 'bg-rose-500/15 text-rose-400 border border-rose-500/20'
              }`}
            >
              {statusData.status}
            </span>
          </div>

          <p className="text-[11px] text-slate-500 mt-1 font-mono">
            Started: {new Date(statusData.started_at).toLocaleTimeString()}
            {statusData.completed_at && (
              <> • Completed: {new Date(statusData.completed_at).toLocaleTimeString()}</>
            )}
          </p>

          {/* Progress bar while running */}
          {isRunning && (
            <div className="mt-2 w-48 progress-bar">
              <div className="progress-bar-fill" style={{ width: '65%', background: 'linear-gradient(90deg, #f59e0b, #fbbf24, #f59e0b)' }} />
            </div>
          )}
        </div>
      </div>

      <div className="relative flex items-center gap-3">
        {isRunning && (
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            className="relative z-10 flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 rounded-xl transition-all duration-200 active:scale-95 disabled:opacity-50 shadow-sm"
            title="Cancel ongoing pipeline execution"
          >
            {isCancelling ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <XCircle className="w-3.5 h-3.5 text-rose-400" />
            )}
            {isCancelling ? 'Cancelling...' : 'Cancel Run'}
          </button>
        )}

        {statusData.reflection_triggered && (
          <span className="relative flex items-center gap-1.5 text-[11px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/15 px-3 py-1.5 rounded-xl animate-scale-in">
            <RefreshCw className="w-3 h-3 text-indigo-400 animate-spin" style={{ animationDuration: '2s' }} />
            Reflection Triggered
          </span>
        )}
      </div>
    </div>
  );
}
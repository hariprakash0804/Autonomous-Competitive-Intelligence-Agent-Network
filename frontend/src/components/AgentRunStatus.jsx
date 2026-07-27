import { useEffect, useState } from 'react';
import { Loader2, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import api from '../api/client';

export default function AgentRunStatus({ runId, onComplete }) {
  const [statusData, setStatusData] = useState(null);

  useEffect(() => {
    if (!runId) return;

    let isStopped = false;

    const fetchStatus = async () => {
      if (isStopped) return;
      try {
        const response = await api.get(`/pipeline/status/${runId}`);
        setStatusData(response.data);

        if (response.data.status === 'COMPLETED' || response.data.status === 'FAILED') {
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

  if (!statusData) return null;

  const isRunning = statusData.status === 'RUNNING';
  const isCompleted = statusData.status === 'COMPLETED';
  const isFailed = statusData.status === 'FAILED';

  return (
    <div
      className={`relative overflow-hidden p-5 rounded-2xl flex items-center justify-between transition-all duration-500 animate-slide-in-right ${
        isRunning
          ? 'glass-card neon-amber'
          : isCompleted
          ? 'glass-card neon-emerald animate-scale-in'
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

      {statusData.reflection_triggered && (
        <span className="relative flex items-center gap-1.5 text-[11px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/15 px-3 py-1.5 rounded-xl animate-scale-in">
          <RefreshCw className="w-3 h-3 text-indigo-400 animate-spin" style={{ animationDuration: '2s' }} />
          Reflection Triggered
        </span>
      )}
    </div>
  );
}
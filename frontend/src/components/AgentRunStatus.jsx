import React, { useEffect, useState } from 'react';
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
      className={`p-4 rounded-xl border flex items-center justify-between transition-all ${
        isRunning
          ? 'bg-amber-950/30 border-amber-500/50 shadow-md shadow-amber-950/20 animate-pulse'
          : isCompleted
          ? 'bg-emerald-950/30 border-emerald-500/50 shadow-md'
          : 'bg-rose-950/30 border-rose-500/50 shadow-md'
      }`}
    >
      <div className="flex items-center gap-3">
        {isRunning && <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />}
        {isCompleted && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
        {isFailed && <AlertCircle className="w-5 h-5 text-rose-400" />}

        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-slate-100">
              Agent Pipeline Run: <span className="font-mono text-xs">{runId.slice(0, 8)}...</span>
            </h4>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                isRunning
                  ? 'bg-amber-500 text-slate-950'
                  : isCompleted
                  ? 'bg-emerald-500 text-slate-950'
                  : 'bg-rose-500 text-white'
              }`}
            >
              {statusData.status}
            </span>
          </div>

          <p className="text-xs text-slate-400 mt-0.5">
            Started: {new Date(statusData.started_at).toLocaleTimeString()}
            {statusData.completed_at && (
              <> • Completed: {new Date(statusData.completed_at).toLocaleTimeString()}</>
            )}
          </p>
        </div>
      </div>

      {statusData.reflection_triggered && (
        <span className="flex items-center gap-1 text-[11px] bg-indigo-950 text-indigo-300 border border-indigo-800 px-2.5 py-1 rounded-md">
          <RefreshCw className="w-3 h-3 text-indigo-400" /> Reflection Triggered
        </span>
      )}
    </div>
  );
}

import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Info,
  AlertTriangle,
  X,
  Trash2,
  HelpCircle,
  Send,
  CornerDownLeft,
} from 'lucide-react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [confirmState, setConfirmState] = useState(null);
  const [promptState, setPromptState] = useState(null);
  const [promptValue, setPromptValue] = useState('');

  // ── Toast Notifications ──────────────────────────────────────────────────
  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((message, type = 'info', title = null, duration = 4000) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev.slice(-4), { id, message, type, title, duration }]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, [removeToast]);

  const success = useCallback((msg, title = 'Success') => showToast(msg, 'success', title), [showToast]);
  const error = useCallback((msg, title = 'Error') => showToast(msg, 'error', title, 5000), [showToast]);
  const info = useCallback((msg, title = 'Notification') => showToast(msg, 'info', title), [showToast]);
  const warning = useCallback((msg, title = 'Warning') => showToast(msg, 'warning', title), [showToast]);

  // ── Confirmation Modal ───────────────────────────────────────────────────
  const confirm = useCallback(({ title = 'Confirm Action', message = 'Are you sure you want to proceed?', confirmText = 'Confirm', cancelText = 'Cancel', type = 'danger' }) => {
    return new Promise((resolve) => {
      setConfirmState({ title, message, confirmText, cancelText, type, resolve });
    });
  }, []);

  const handleConfirmClose = (result) => {
    if (confirmState?.resolve) {
      confirmState.resolve(result);
    }
    setConfirmState(null);
  };

  // ── Prompt Modal ─────────────────────────────────────────────────────────
  const prompt = useCallback(({ title = 'Input Required', message = 'Please enter value:', placeholder = '', defaultValue = '', confirmText = 'Submit', cancelText = 'Cancel' }) => {
    setPromptValue(defaultValue);
    return new Promise((resolve) => {
      setPromptState({ title, message, placeholder, defaultValue, confirmText, cancelText, resolve });
    });
  }, []);

  const handlePromptClose = (submitted) => {
    if (promptState?.resolve) {
      promptState.resolve(submitted ? promptValue : null);
    }
    setPromptState(null);
    setPromptValue('');
  };

  return (
    <ToastContext.Provider
      value={{
        showToast,
        success,
        error,
        info,
        warning,
        confirm,
        prompt,
      }}
    >
      {children}

      {/* Floating Toast Notifications Stack */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-3 sm:px-0">
        {toasts.map((toast) => {
          const isSuccess = toast.type === 'success';
          const isError = toast.type === 'error';
          const isWarning = toast.type === 'warning';

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto p-4 rounded-2xl bg-[#0c0c16]/90 backdrop-blur-xl border border-white/[0.08] shadow-2xl shadow-black/80 flex items-start gap-3.5 animate-slide-in-right relative overflow-hidden transition-all duration-300 group hover:border-white/[0.15] ${
                isSuccess
                  ? 'shadow-emerald-500/10'
                  : isError
                  ? 'shadow-rose-500/10'
                  : isWarning
                  ? 'shadow-amber-500/10'
                  : 'shadow-indigo-500/10'
              }`}
            >
              {/* Left Accent Bar */}
              <div
                className={`absolute left-0 top-0 bottom-0 w-1.5 ${
                  isSuccess
                    ? 'bg-emerald-400'
                    : isError
                    ? 'bg-rose-500'
                    : isWarning
                    ? 'bg-amber-400'
                    : 'bg-indigo-500'
                }`}
              />

              {/* Icon */}
              <div
                className={`p-2 rounded-xl shrink-0 mt-0.5 ${
                  isSuccess
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : isError
                    ? 'bg-rose-500/15 text-rose-400'
                    : isWarning
                    ? 'bg-amber-500/15 text-amber-400'
                    : 'bg-indigo-500/15 text-indigo-400'
                }`}
              >
                {isSuccess && <CheckCircle2 className="w-5 h-5" />}
                {isError && <AlertCircle className="w-5 h-5" />}
                {isWarning && <AlertTriangle className="w-5 h-5" />}
                {!isSuccess && !isError && !isWarning && <Info className="w-5 h-5" />}
              </div>

              {/* Body */}
              <div className="flex-1 min-w-0 pr-4">
                {toast.title && (
                  <h4 className="text-xs font-bold text-white font-display tracking-wide mb-0.5">
                    {toast.title}
                  </h4>
                )}
                <p className="text-xs text-slate-300 leading-relaxed font-sans font-medium break-words">
                  {toast.message}
                </p>
              </div>

              {/* Close Button */}
              <button
                onClick={() => removeToast(toast.id)}
                className="text-slate-500 hover:text-white p-1 rounded-lg hover:bg-white/[0.06] transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>

              {/* Progress Bar Animation */}
              {toast.duration > 0 && (
                <div
                  className={`absolute bottom-0 left-0 h-0.5 opacity-60 ${
                    isSuccess
                      ? 'bg-emerald-400'
                      : isError
                      ? 'bg-rose-500'
                      : isWarning
                      ? 'bg-amber-400'
                      : 'bg-indigo-400'
                  }`}
                  style={{
                    animation: `toast-progress ${toast.duration}ms linear forwards`,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Confirmation Modal */}
      {confirmState && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl max-w-sm w-full p-6 neon-border shadow-2xl space-y-4 animate-spring-in border border-white/[0.08] relative overflow-hidden">
            <div className="flex items-center gap-3.5 border-b border-white/[0.06] pb-4">
              <div
                className={`p-2.5 rounded-xl ${
                  confirmState.type === 'danger'
                    ? 'bg-rose-500/15 text-rose-400 border border-rose-500/20'
                    : 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/20'
                }`}
              >
                {confirmState.type === 'danger' ? (
                  <Trash2 className="w-5 h-5" />
                ) : (
                  <HelpCircle className="w-5 h-5" />
                )}
              </div>
              <div>
                <h3 className="text-sm font-bold text-white font-display">
                  {confirmState.title}
                </h3>
                <p className="text-[10px] text-slate-500">Please confirm your action</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {confirmState.message}
            </p>

            <div className="pt-2 flex items-center justify-end gap-2.5">
              <button
                onClick={() => handleConfirmClose(false)}
                className="px-4 py-2 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white rounded-xl text-xs font-semibold border border-white/[0.06] transition-all duration-200"
              >
                {confirmState.cancelText}
              </button>
              <button
                onClick={() => handleConfirmClose(true)}
                className={`px-4 py-2 text-xs font-semibold rounded-xl transition-all duration-200 shadow-lg ${
                  confirmState.type === 'danger'
                    ? 'bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 text-white shadow-rose-600/25'
                    : 'btn-gradient text-white shadow-indigo-600/25'
                }`}
              >
                {confirmState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Modal */}
      {promptState && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl max-w-md w-full p-6 neon-border shadow-2xl space-y-4 animate-spring-in border border-white/[0.08] relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <h3 className="text-sm font-bold text-white font-display flex items-center gap-2">
                <Send className="w-4 h-4 text-indigo-400" />
                {promptState.title}
              </h3>
              <button
                onClick={() => handlePromptClose(false)}
                className="text-slate-500 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {promptState.message}
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handlePromptClose(true);
              }}
              className="space-y-3"
            >
              <input
                type="text"
                autoFocus
                value={promptValue}
                onChange={(e) => setPromptValue(e.target.value)}
                placeholder={promptState.placeholder}
                className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-600 input-glow transition-all duration-300 font-mono"
              />

              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => handlePromptClose(false)}
                  className="px-4 py-2 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white rounded-xl text-xs font-semibold border border-white/[0.06] transition-all duration-200"
                >
                  {promptState.cancelText}
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 btn-gradient text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/25 flex items-center gap-1.5"
                >
                  <CornerDownLeft className="w-3.5 h-3.5" />
                  {promptState.confirmText}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

import React, { useEffect, useState } from 'react';
import { FileText, ExternalLink, Download, Send, Mail, Copy, Check, Clock } from 'lucide-react';
import api, { API_BASE_URL } from '../api/client';

export default function ReportsPanel({ selectedCompetitorId }) {
  const [reports, setReports] = useState([]);
  const [copiedId, setCopiedId] = useState(null);
  const [sendingSlackId, setSendingSlackId] = useState(null);
  const [sendingEmailId, setSendingEmailId] = useState(null);

  const fetchReports = async () => {
    try {
      const endpoint = selectedCompetitorId
        ? `/reports/competitor/${selectedCompetitorId}`
        : '/reports/';
      const res = await api.get(endpoint);
      setReports(res.data);
    } catch (err) {
      console.error('Failed to fetch reports:', err);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [selectedCompetitorId]);

  const handleCopyLink = (reportId) => {
    const link = `${window.location.origin}/reports/${reportId}/html`;
    navigator.clipboard.writeText(link);
    setCopiedId(reportId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSendSlack = async (reportId) => {
    setSendingSlackId(reportId);
    try {
      await api.post(`/reports/deliver-slack/${reportId}`, {});
      alert('Slack notification sent successfully!');
    } catch (err) {
      console.error('Failed to send Slack alert:', err);
      alert('Failed to send Slack alert.');
    } finally {
      setSendingSlackId(null);
    }
  };

  const handleSendEmail = async (reportId) => {
    setSendingEmailId(reportId);
    try {
      const res = await api.post(`/reports/deliver-email/${reportId}`, {});
      if (res.data.email_result?.status === 'skipped') {
        alert(res.data.email_result.reason);
      } else if (res.data.email_result?.status === 'sent') {
        alert(`Email successfully sent to ${res.data.email_result.recipient}!`);
      } else {
        alert(`Email failed: ${res.data.email_result?.reason}`);
      }
    } catch (err) {
      console.error('Failed to send email:', err);
      alert('Failed to send email report.');
    } finally {
      setSendingEmailId(null);
    }
  };

  // Model color mapping
  const modelColors = {
    'gpt-4': 'from-emerald-500 to-emerald-400',
    'gpt-4o': 'from-emerald-500 to-cyan-400',
    'gpt-3.5': 'from-blue-500 to-blue-400',
    'gemini': 'from-violet-500 to-purple-400',
    'claude': 'from-amber-500 to-orange-400',
  };

  const getModelColor = (model) => {
    if (!model) return 'from-indigo-500 to-indigo-400';
    const lower = model.toLowerCase();
    for (const [key, value] of Object.entries(modelColors)) {
      if (lower.includes(key)) return value;
    }
    return 'from-indigo-500 to-indigo-400';
  };

  return (
    <div className="glass-card rounded-2xl p-5 neon-border space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2 font-display">
            <div className="p-1.5 rounded-lg bg-indigo-500/10">
              <FileText className="w-4 h-4 text-indigo-400" />
            </div>
            Executive Reports & Delivery
          </h2>
          <p className="text-[10px] text-slate-500 mt-0.5">
            HTML reports with Slack and Email dispatch
          </p>
        </div>
      </div>

      <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
        {(Array.isArray(reports) ? reports : []).map((r, idx) => (
          <div
            key={r.id}
            style={{ '--i': idx }}
            className="stagger-item hover-lift p-4 bg-white/[0.02] border border-white/[0.04] rounded-xl flex items-center justify-between text-xs group transition-all duration-300 hover:border-white/[0.08]"
          >
            <div className="flex items-center gap-3">
              {/* Model color bar */}
              <div className={`w-1 h-10 rounded-full bg-gradient-to-b ${getModelColor(r.model_used)}`} />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white text-[13px]">{r.competitor_name}</span>
                  <span className="text-[10px] bg-white/[0.04] text-slate-400 border border-white/[0.06] px-2 py-0.5 rounded-lg font-mono">
                    {r.model_used}
                  </span>
                </div>
                <p className="text-slate-500 text-[10px] mt-0.5 flex items-center gap-1 font-mono">
                  <Clock className="w-3 h-3 text-slate-600" /> {r.formatted_date}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <a
                href={`${API_BASE_URL}${r.html_url}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 bg-indigo-500/10 hover:bg-indigo-600 text-indigo-400 hover:text-white px-2.5 py-1.5 rounded-lg border border-indigo-500/10 transition-all duration-200 hover:scale-105 text-[10px] font-medium"
              >
                <ExternalLink className="w-3 h-3" />
                <span className="hidden group-hover:inline">HTML</span>
              </a>

              <a
                href={`${API_BASE_URL}${r.pdf_url || `/reports/${r.id}/pdf`}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 bg-amber-500/10 hover:bg-amber-600 text-amber-400 hover:text-white px-2.5 py-1.5 rounded-lg border border-amber-500/10 transition-all duration-200 hover:scale-105 text-[10px] font-medium"
              >
                <Download className="w-3 h-3" />
                <span className="hidden group-hover:inline">PDF</span>
              </a>

              <button
                onClick={() => handleSendSlack(r.id)}
                disabled={sendingSlackId === r.id}
                title="Send Slack Notification"
                className="flex items-center gap-1 bg-emerald-500/10 hover:bg-emerald-600 text-emerald-400 hover:text-white px-2.5 py-1.5 rounded-lg border border-emerald-500/10 transition-all duration-200 hover:scale-105 active:scale-95 text-[10px] font-medium disabled:opacity-40 disabled:hover:scale-100"
              >
                {sendingSlackId === r.id ? (
                  <span className="w-3 h-3 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
                ) : (
                  <Send className="w-3 h-3" />
                )}
              </button>

              <button
                onClick={() => handleSendEmail(r.id)}
                disabled={sendingEmailId === r.id}
                title="Send Email"
                className="flex items-center gap-1 bg-violet-500/10 hover:bg-violet-600 text-violet-400 hover:text-white px-2.5 py-1.5 rounded-lg border border-violet-500/10 transition-all duration-200 hover:scale-105 active:scale-95 text-[10px] font-medium disabled:opacity-40 disabled:hover:scale-100"
              >
                {sendingEmailId === r.id ? (
                  <span className="w-3 h-3 border-2 border-violet-400/30 border-t-violet-400 rounded-full animate-spin" />
                ) : (
                  <Mail className="w-3 h-3" />
                )}
              </button>

              <button
                onClick={() => handleCopyLink(r.id)}
                title="Copy Link"
                className="p-1.5 bg-white/[0.03] hover:bg-white/[0.08] text-slate-400 hover:text-white rounded-lg border border-white/[0.06] transition-all duration-200 hover:scale-110"
              >
                {copiedId === r.id ? (
                  <Check className="w-3 h-3 text-emerald-400 animate-scale-in" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
              </button>
            </div>
          </div>
        ))}
        {(!Array.isArray(reports) || reports.length === 0) && (
          <div className="text-center py-10 animate-fade-in-up">
            <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mx-auto mb-3">
              <FileText className="w-7 h-7 text-slate-700" />
            </div>
            <p className="text-xs text-slate-500 font-medium">No reports generated yet</p>
            <p className="text-[10px] text-slate-600 mt-1">Run an agent pipeline to generate executive reports</p>
          </div>
        )}
      </div>
    </div>
  );
}
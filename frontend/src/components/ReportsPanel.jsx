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

  const filteredReports = reports;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <FileText className="w-5 h-5 text-indigo-400" /> Executive Reports & Delivery
          </h2>
          <p className="text-xs text-slate-400">
            Rendered HTML reports with Slack and 100% Free Email dispatch
          </p>
        </div>
      </div>

      <div className="space-y-3 max-h-[260px] overflow-y-auto pr-1">
        {(Array.isArray(filteredReports) ? filteredReports : []).map((r, idx) => (
          <div
            key={r.id}
            style={{ '--i': idx }}
            className="stagger-item hover-lift p-3.5 bg-slate-800/40 border border-slate-700/60 rounded-xl flex items-center justify-between text-xs"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-100">{r.competitor_name}</span>
                <span className="text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-800 px-2 py-0.5 rounded font-mono">
                  {r.model_used}
                </span>
              </div>
              <p className="text-slate-400 text-[11px] mt-1 flex items-center gap-1">
                <Clock className="w-3 h-3 text-slate-500" /> {r.formatted_date}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <a
                href={`${API_BASE_URL}${r.html_url}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white px-2.5 py-1.5 rounded-lg border border-indigo-500/30 transition-all duration-200 hover:scale-105 text-[11px] font-medium"
              >
                <ExternalLink className="w-3.5 h-3.5" /> HTML
              </a>

              <a
                href={`${API_BASE_URL}${r.pdf_url || `/reports/${r.id}/pdf`}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 bg-amber-950/60 hover:bg-amber-900 text-amber-300 hover:text-white px-2.5 py-1.5 rounded-lg border border-amber-800/30 transition-all duration-200 hover:scale-105 text-[11px] font-medium"
              >
                <Download className="w-3.5 h-3.5" /> PDF
              </a>

              <button
                onClick={() => handleSendSlack(r.id)}
                disabled={sendingSlackId === r.id}
                title="Send Slack Webhook Notification"
                className="flex items-center gap-1 bg-emerald-950/60 hover:bg-emerald-900 text-emerald-300 px-2.5 py-1.5 rounded-lg border border-emerald-800 transition-all duration-200 hover:scale-105 active:scale-95 text-[11px] font-medium disabled:opacity-50 disabled:hover:scale-100"
              >
                {sendingSlackId === r.id ? (
                  <span className="w-3.5 h-3.5 border-2 border-emerald-400/40 border-t-emerald-400 rounded-full animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5 text-emerald-400" />
                )}
                Slack
              </button>

              <button
                onClick={() => handleSendEmail(r.id)}
                disabled={sendingEmailId === r.id}
                title="Send Email Notification (Free Gmail SMTP)"
                className="flex items-center gap-1 bg-indigo-950/60 hover:bg-indigo-900 text-indigo-300 px-2.5 py-1.5 rounded-lg border border-indigo-800 transition-all duration-200 hover:scale-105 active:scale-95 text-[11px] font-medium disabled:opacity-50 disabled:hover:scale-100"
              >
                {sendingEmailId === r.id ? (
                  <span className="w-3.5 h-3.5 border-2 border-indigo-400/40 border-t-indigo-400 rounded-full animate-spin" />
                ) : (
                  <Mail className="w-3.5 h-3.5 text-indigo-400" />
                )}
                Email
              </button>

              <button
                onClick={() => handleCopyLink(r.id)}
                title="Copy Link"
                className="p-1.5 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-600 transition-all duration-200 hover:scale-110"
              >
                {copiedId === r.id ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400 animate-scale-in" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>
        ))}

        {filteredReports.length === 0 && (
          <div className="text-center py-6 text-slate-500 text-xs animate-fade-in-up">
            No generated reports found. Trigger an agent pipeline run to generate executive reports.
          </div>
        )}
      </div>
    </div>
  );
}
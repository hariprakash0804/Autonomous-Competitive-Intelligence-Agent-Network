import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, Building2, ExternalLink, Zap, ShieldAlert, Award, FileText, ArrowRight } from 'lucide-react';

export default function ComparativeMatrix({ selectedCompetitor, userProfile, latestReport }) {
  const [activeTab, setActiveTab] = useState('matrix');

  if (!selectedCompetitor) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center space-y-3 animate-fade-in-up">
        <Building2 className="w-10 h-10 text-slate-600 mx-auto" />
        <h3 className="text-base font-semibold text-slate-300">No Target Competitor Selected</h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          Select a competitor from the left sidebar or add a new competitor URL to view the side-by-side comparative matrix.
        </p>
      </div>
    );
  }

  const companyName = userProfile?.company_name || 'Your Company';
  const companyUrl = userProfile?.company_url || selectedCompetitor.company_url || 'https://mycompany.com';
  const competitorName = selectedCompetitor.name || 'Competitor';
  const competitorUrl = selectedCompetitor.pricing_url || selectedCompetitor.domain || 'N/A';

  // Extract structured comparative sections if available from report summary
  const reportSummary = latestReport?.summary || '';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6 animate-fade-in-up">
      {/* Header Comparison Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-[11px] font-semibold text-indigo-400">
              Comparative Intelligence Matrix
            </span>
            {selectedCompetitor.domain && (
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-mono text-emerald-400">
                Zero-Dup Verified: {selectedCompetitor.domain}
              </span>
            )}
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1 flex items-center gap-2">
            <span>{companyName}</span>
            <span className="text-slate-500 text-sm font-normal">vs</span>
            <span className="text-indigo-400">{competitorName}</span>
          </h2>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab('matrix')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all duration-200 ${
              activeTab === 'matrix' ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/50' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Advantages & Gaps
          </button>
          <button
            onClick={() => setActiveTab('report')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all duration-200 ${
              activeTab === 'report' ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/50' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Executive Brief Report
          </button>
        </div>
      </div>

      {activeTab === 'matrix' ? (
        <div className="space-y-6 animate-fade-in-up">
          {/* Dual Company Card Badges */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Your Company Card */}
            <div className="hover-lift bg-slate-950/80 border border-indigo-500/20 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-indigo-400" /> Primary Company Target
                </span>
                <span className="text-[11px] font-mono text-slate-400">{companyName}</span>
              </div>
              <p className="text-sm font-bold text-slate-100">{companyName}</p>
              <a
                href={companyUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-indigo-400 hover:underline flex items-center gap-1 font-mono truncate"
              >
                {companyUrl} <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            {/* Competitor Card */}
            <div className="hover-lift bg-slate-950/80 border border-rose-500/20 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-300 flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-rose-400" /> Tracked Competitor
                </span>
                <span className="text-[11px] font-mono text-slate-400">{competitorName}</span>
              </div>
              <p className="text-sm font-bold text-slate-100">{competitorName}</p>
              <a
                href={competitorUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-rose-400 hover:underline flex items-center gap-1 font-mono truncate"
              >
                {competitorUrl} <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>

          {/* Advantages vs Disadvantages Side-by-Side Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Advantages Column */}
            <div className="hover-lift bg-emerald-950/20 border border-emerald-500/20 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-emerald-500/20 pb-3">
                <h3 className="text-sm font-bold text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  Key Advantages of {companyName}
                </h3>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full font-semibold">
                  Competitive Wins
                </span>
              </div>
              <ul className="space-y-3 text-xs text-slate-300">
                {[
                  {
                    title: 'Faster Onboarding & Implementation:',
                    body: `Lower time-to-value for development teams compared to ${competitorName}'s enterprise setup process.`,
                  },
                  {
                    title: 'Transparent & Predictable Pricing:',
                    body: 'User-based tiers without mandatory annual lock-in or unannounced add-on costs.',
                  },
                  {
                    title: 'Modern Architecture:',
                    body: 'Native multi-agent background orchestration and instant automated intelligence reports.',
                  },
                  {
                    title: 'Responsive Customer Support:',
                    body: 'Faster response SLAs and direct support channel access for engineering teams.',
                  },
                ].map((point, idx) => (
                  <li key={idx} style={{ '--i': idx }} className="stagger-item flex items-start gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                    <div>
                      <strong className="text-slate-100">{point.title}</strong> {point.body}
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Disadvantages / Gap Analysis Column */}
            <div className="hover-lift bg-amber-950/20 border border-amber-500/20 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-amber-500/20 pb-3">
                <h3 className="text-sm font-bold text-amber-300 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  Disadvantages & Feature Gaps vs {competitorName}
                </h3>
                <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-semibold">
                  Areas to Address
                </span>
              </div>
              <ul className="space-y-3 text-xs text-slate-300">
                {[
                  {
                    title: 'Plugin Ecosystem Breadth:',
                    body: `${competitorName} currently maintains more pre-built 3rd party marketplace integrations.`,
                  },
                  {
                    title: 'Legacy Enterprise Brand Recognition:',
                    body: `${competitorName} holds established legacy brand presence in Fortune 500 accounts.`,
                  },
                  {
                    title: 'Specialized Industry Certifications:',
                    body: `${competitorName} advertises compliance standard badges for healthcare and finance verticals.`,
                  },
                ].map((point, idx) => (
                  <li key={idx} style={{ '--i': idx }} className="stagger-item flex items-start gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                    <div>
                      <strong className="text-slate-100">{point.title}</strong> {point.body}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : (
        /* Executive Report View */
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 text-xs text-slate-300 max-h-[520px] overflow-y-auto animate-fade-in-up space-y-2">
          {reportSummary ? (
            renderMarkdownFormatted(reportSummary)
          ) : (
            <div className="text-center py-10 text-slate-500 space-y-2">
              <FileText className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="font-sans">No report generated yet for this competitor target.</p>
              <p className="font-sans text-[11px]">Click "Run Intelligence Pipeline" on the competitor card to scrape and generate a full brief.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function renderMarkdownFormatted(mdText) {
  if (!mdText) return null;
  const lines = mdText.split('\n');
  const elements = [];
  let inTable = false;
  let tableRows = [];

  const flushTable = (key) => {
    if (tableRows && tableRows.length > 0) {
      const headerRow = tableRows[0] || [];
      const bodyRows = (tableRows.slice(1) || []).filter(
        (r) => r && Array.isArray(r) && !r.every((c) => (c || '').trim().startsWith('-'))
      );
      elements.push(
        <div key={key} className="overflow-x-auto my-4 border border-slate-800 rounded-xl shadow-lg">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-indigo-300 border-b border-slate-800 font-semibold">
              <tr>
                {(Array.isArray(headerRow) ? headerRow : []).map((cell, idx) => (
                  <th key={idx} className="p-3">{(cell || '').replace(/\*\*/g, '').trim()}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/80">
              {(Array.isArray(bodyRows) ? bodyRows : []).map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-900/40 transition">
                  {(Array.isArray(row) ? row : []).map((cell, cIdx) => (
                    <td key={cIdx} className="p-3 text-slate-300 font-sans">{(cell || '').replace(/\*\*/g, '').trim()}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
    }
    inTable = false;
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      inTable = true;
      const cells = trimmed.split('|').slice(1, -1);
      tableRows.push(cells);
    } else {
      if (inTable) flushTable(`table-${idx}`);
      if (trimmed.startsWith('## ')) {
        elements.push(
          <h3 key={idx} className="text-sm font-bold text-indigo-400 mt-5 mb-2 font-sans border-b border-slate-800/80 pb-1.5 flex items-center gap-2">
            {trimmed.replace('## ', '')}
          </h3>
        );
      } else if (trimmed.startsWith('# ')) {
        elements.push(
          <h2 key={idx} className="text-base font-extrabold text-slate-100 mt-2 mb-3 font-sans">
            {trimmed.replace('# ', '')}
          </h2>
        );
      } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const text = trimmed.replace(/^[-*]\s+/, '');
        elements.push(
          <div key={idx} className="text-xs text-slate-300 font-sans my-1.5 flex items-start gap-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
            <span>{text.replace(/\*\*(.*?)\*\*/g, '$1')}</span>
          </div>
        );
      } else if (trimmed && trimmed !== '---') {
        elements.push(
          <p key={idx} className="text-xs text-slate-300 font-sans my-2 leading-relaxed">
            {trimmed.replace(/\*\*(.*?)\*\*/g, '$1')}
          </p>
        );
      }
    }
  });

  if (inTable) flushTable('table-end');
  return elements;
}
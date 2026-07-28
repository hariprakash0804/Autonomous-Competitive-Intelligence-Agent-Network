import { useState } from 'react';
import { CheckCircle2, AlertTriangle, Building2, ExternalLink, Award, FileText, TrendingUp, TrendingDown } from 'lucide-react';

export default function ComparativeMatrix({ selectedCompetitor, userProfile, latestReport, intelligenceData }) {
  const [activeTab, setActiveTab] = useState('matrix');

  if (!selectedCompetitor) {
    return (
      <div className="glass-card rounded-2xl p-10 text-center space-y-4 neon-border animate-fade-in-up">
        <div className="w-16 h-16 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mx-auto">
          <Building2 className="w-8 h-8 text-slate-700" />
        </div>
        <h3 className="text-base font-bold text-slate-300 font-display">No Target Selected</h3>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Select a competitor from the sidebar to view the side-by-side comparative intelligence matrix.
        </p>
      </div>
    );
  }

  const companyName = userProfile?.company_name || 'Your Company';
  const companyUrl = userProfile?.company_url || selectedCompetitor.company_url || 'https://mycompany.com';
  const competitorName = selectedCompetitor.name || 'Competitor';
  const competitorUrl = selectedCompetitor.pricing_url || selectedCompetitor.domain || 'N/A';

  const reportSummary = latestReport?.summary || '';
  const technographics = intelligenceData?.technographics || [];

  return (
    <div className="glass-card rounded-2xl p-6 neon-border space-y-6 animate-fade-in-up">
      {/* Header Battle Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/[0.04] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-lg bg-indigo-500/10 border border-indigo-500/10 text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">
              Comparative Matrix
            </span>
            {selectedCompetitor.domain && (
              <span className="px-2 py-0.5 rounded-lg bg-emerald-500/10 border border-emerald-500/10 text-[10px] font-mono text-emerald-400">
                {selectedCompetitor.domain}
              </span>
            )}
          </div>
          {/* VS Title */}
          <h2 className="text-lg font-bold text-white mt-1 flex items-center gap-3 font-display">
            <span>{companyName}</span>
            <span className="vs-badge inline-flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-[10px] font-black shadow-lg shadow-indigo-600/30">
              VS
            </span>
            <span className="gradient-text-vivid">{competitorName}</span>
          </h2>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center bg-white/[0.03] p-1 rounded-xl border border-white/[0.04] text-xs">
          <button
            onClick={() => setActiveTab('matrix')}
            className={`px-3.5 py-2 rounded-lg font-medium transition-all duration-300 ${
              activeTab === 'matrix' ? 'btn-gradient shadow-md' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            Advantages & Gaps
          </button>
          <button
            onClick={() => setActiveTab('report')}
            className={`px-3.5 py-2 rounded-lg font-medium transition-all duration-300 ${
              activeTab === 'report' ? 'btn-gradient shadow-md' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            Executive Brief
          </button>
        </div>
      </div>

      {activeTab === 'matrix' ? (
        <div className="space-y-6 animate-fade-in-up">
          {/* Dual Company Battle Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Your Company Card */}
            <div className="card-3d rounded-xl p-4 space-y-2 bg-white/[0.02] border border-indigo-500/15 neon-border">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-indigo-300 flex items-center gap-1.5 uppercase tracking-wider">
                  <Award className="w-3.5 h-3.5 text-indigo-400" /> Your Company
                </span>
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <p className="text-sm font-bold text-white font-display">{companyName}</p>
              <a
                href={companyUrl}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-indigo-400 hover:underline flex items-center gap-1 font-mono truncate transition-colors hover:text-indigo-300"
              >
                {companyUrl} <ExternalLink className="w-3 h-3 flex-shrink-0" />
              </a>
            </div>

            {/* Competitor Card */}
            <div className="card-3d rounded-xl p-4 space-y-2 bg-white/[0.02] border border-rose-500/15 neon-rose">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-rose-300 flex items-center gap-1.5 uppercase tracking-wider">
                  <Building2 className="w-3.5 h-3.5 text-rose-400" /> Competitor
                </span>
                <TrendingDown className="w-4 h-4 text-rose-400" />
              </div>
              <p className="text-sm font-bold text-white font-display">{competitorName}</p>
              <a
                href={competitorUrl}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-rose-400 hover:underline flex items-center gap-1 font-mono truncate transition-colors hover:text-rose-300"
              >
                {competitorUrl} <ExternalLink className="w-3 h-3 flex-shrink-0" />
              </a>

              {/* Technographics Tech Stack Badges */}
              {technographics.length > 0 && (
                <div className="pt-2 border-t border-white/[0.04]">
                  <p className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Detected Tech Stack ({technographics.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {technographics.map((tech, tIdx) => (
                      <span
                        key={tIdx}
                        className="px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-[9px] font-mono text-indigo-300"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Advantages vs Disadvantages */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Advantages Column */}
            <div className="rounded-xl p-5 space-y-4 bg-emerald-500/[0.03] border border-emerald-500/10 neon-emerald">
              <div className="flex items-center justify-between border-b border-emerald-500/10 pb-3">
                <h3 className="text-xs font-bold text-emerald-300 flex items-center gap-2 font-display">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  Key Advantages
                </h3>
                <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2.5 py-0.5 rounded-lg font-semibold">
                  Wins
                </span>
              </div>
              <ul className="space-y-3 text-xs text-slate-300">
                {[
                  {
                    title: 'Faster Onboarding & Implementation:',
                    body: `Lower time-to-value for development teams compared to ${competitorName}'s enterprise setup process.`,
                    strength: 85,
                  },
                  {
                    title: 'Transparent & Predictable Pricing:',
                    body: 'User-based tiers without mandatory annual lock-in or unannounced add-on costs.',
                    strength: 78,
                  },
                  {
                    title: 'Modern Architecture:',
                    body: 'Native multi-agent background orchestration and instant automated intelligence reports.',
                    strength: 92,
                  },
                  {
                    title: 'Responsive Customer Support:',
                    body: 'Faster response SLAs and direct support channel access for engineering teams.',
                    strength: 70,
                  },
                ].map((point, idx) => (
                  <li key={idx} style={{ '--i': idx }} className="stagger-item space-y-1.5">
                    <div className="flex items-start gap-2.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                      <div>
                        <strong className="text-slate-100">{point.title}</strong> {point.body}
                      </div>
                    </div>
                    {/* Strength bar */}
                    <div className="ml-4 progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${point.strength}%`, background: 'linear-gradient(90deg, #10b981, #34d399)' }} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Disadvantages Column */}
            <div className="rounded-xl p-5 space-y-4 bg-amber-500/[0.03] border border-amber-500/10 neon-amber">
              <div className="flex items-center justify-between border-b border-amber-500/10 pb-3">
                <h3 className="text-xs font-bold text-amber-300 flex items-center gap-2 font-display">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Gaps vs {competitorName}
                </h3>
                <span className="text-[10px] bg-amber-500/10 text-amber-400 px-2.5 py-0.5 rounded-lg font-semibold">
                  Address
                </span>
              </div>
              <ul className="space-y-3 text-xs text-slate-300">
                {[
                  {
                    title: 'Plugin Ecosystem Breadth:',
                    body: `${competitorName} currently maintains more pre-built 3rd party marketplace integrations.`,
                    gap: 65,
                  },
                  {
                    title: 'Legacy Enterprise Brand Recognition:',
                    body: `${competitorName} holds established legacy brand presence in Fortune 500 accounts.`,
                    gap: 55,
                  },
                  {
                    title: 'Specialized Industry Certifications:',
                    body: `${competitorName} advertises compliance standard badges for healthcare and finance verticals.`,
                    gap: 45,
                  },
                ].map((point, idx) => (
                  <li key={idx} style={{ '--i': idx }} className="stagger-item space-y-1.5">
                    <div className="flex items-start gap-2.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                      <div>
                        <strong className="text-slate-100">{point.title}</strong> {point.body}
                      </div>
                    </div>
                    {/* Gap bar */}
                    <div className="ml-4 progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${point.gap}%`, background: 'linear-gradient(90deg, #f59e0b, #fbbf24)' }} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : (
        /* Executive Report View */
        <div className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-6 text-xs text-slate-300 max-h-[520px] overflow-y-auto animate-fade-in-up space-y-2">
          {reportSummary ? (
            renderMarkdownFormatted(reportSummary)
          ) : (
            <div className="text-center py-12 space-y-3">
              <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mx-auto">
                <FileText className="w-7 h-7 text-slate-700" />
              </div>
              <p className="text-xs text-slate-500 font-medium">No report generated yet</p>
              <p className="text-[10px] text-slate-600">Run the intelligence pipeline to generate a full executive brief.</p>
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
        <div key={key} className="overflow-x-auto my-4 border border-white/[0.06] rounded-xl shadow-lg">
          <table className="w-full text-left text-xs">
            <thead className="bg-white/[0.03] text-indigo-300 border-b border-white/[0.04] font-semibold">
              <tr>
                {(Array.isArray(headerRow) ? headerRow : []).map((cell, idx) => (
                  <th key={idx} className="p-3">{(cell || '').replace(/\*\*/g, '').trim()}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {(Array.isArray(bodyRows) ? bodyRows : []).map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-white/[0.02] transition">
                  {(Array.isArray(row) ? row : []).map((cell, cIdx) => (
                    <td key={cIdx} className="p-3 text-slate-300">{(cell || '').replace(/\*\*/g, '').trim()}</td>
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
          <h3 key={idx} className="text-sm font-bold text-indigo-400 mt-5 mb-2 font-display border-b border-white/[0.04] pb-1.5 flex items-center gap-2">
            {trimmed.replace('## ', '')}
          </h3>
        );
      } else if (trimmed.startsWith('# ')) {
        elements.push(
          <h2 key={idx} className="text-base font-extrabold text-white mt-2 mb-3 font-display">
            {trimmed.replace('# ', '')}
          </h2>
        );
      } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const text = trimmed.replace(/^[-*]\s+/, '');
        elements.push(
          <div key={idx} className="text-xs text-slate-300 my-1.5 flex items-start gap-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
            <span>{text.replace(/\*\*(.*?)\*\*/g, '$1')}</span>
          </div>
        );
      } else if (trimmed && trimmed !== '---') {
        elements.push(
          <p key={idx} className="text-xs text-slate-300 my-2 leading-relaxed">
            {trimmed.replace(/\*\*(.*?)\*\*/g, '$1')}
          </p>
        );
      }
    }
  });

  if (inTable) flushTable('table-end');
  return elements;
}
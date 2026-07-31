import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import Sidebar from '../components/Sidebar';
import CompetitorList from '../components/CompetitorList';
import PriceTimeline from '../components/PriceTimeline';
import SentimentChart from '../components/SentimentChart';
import AgentRunStatus from '../components/AgentRunStatus';
import ChatWidget from '../components/ChatWidget';
import ReportsPanel from '../components/ReportsPanel';
import ComparativeMatrix from '../components/ComparativeMatrix';
import CompetitorNotes from '../components/CompetitorNotes';

import {
  LogOut, Plus, Sparkles, Building2,
  AlertCircle, LayoutDashboard, Globe, FileText, Activity,
  DollarSign, Clock, CheckCircle2, Menu, Zap
} from 'lucide-react';

/* ────────────────────────────────────────────
   Live Clock
   ──────────────────────────────────────────── */
function LiveClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const h = time.getHours().toString().padStart(2, '0');
  const m = time.getMinutes().toString().padStart(2, '0');
  const s = time.getSeconds().toString().padStart(2, '0');
  return (
    <span className="font-mono-data text-xs text-slate-400 flex items-center gap-0.5">
      <Clock className="w-3 h-3 text-slate-500" />
      {h}<span className="clock-separator">:</span>{m}<span className="clock-separator">:</span>{s}
    </span>
  );
}

/* ════════════════════════════════════════════
   DASHBOARD PAGE
   ════════════════════════════════════════════ */
export default function DashboardPage() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [competitors, setCompetitors] = useState([]);
  const [selectedCompId, setSelectedCompId] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [sentimentHistory, setSentimentHistory] = useState([]);
  const [reports, setReports] = useState([]);
  const [activeRuns, setActiveRuns] = useState([]); // [{ runId, compId, compName }]
  const [showChat, setShowChat] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Dual URL competitor form state
  const [newCompName, setNewCompName] = useState('');
  const [newCompanyUrl, setNewCompanyUrl] = useState(user?.company_url || localStorage.getItem('ci_saved_company_url') || '');
  const [useSavedUrl, setUseSavedUrl] = useState(Boolean(user?.company_url || localStorage.getItem('ci_saved_company_url')));
  const [newPricingUrl, setNewPricingUrl] = useState('');
  const [addError, setAddError] = useState('');
  const [submittingAdd, setSubmittingAdd] = useState(false);

  const savedCompanyUrl = user?.company_url || localStorage.getItem('ci_saved_company_url') || '';

  const fetchCompetitors = useCallback(async () => {
    try {
      const res = await api.get('/competitors/');
      const data = Array.isArray(res.data) ? res.data : [];
      setCompetitors(data);
      if (data.length > 0) {
        setSelectedCompId((prev) => prev || data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch competitors:', err);
      setCompetitors([]);
    }
  }, []);

  const [intelligenceData, setIntelligenceData] = useState(null);

  const fetchDetails = async (compId) => {
    if (!compId) return;
    try {
      const [priceRes, sentRes, repRes, intelRes] = await Promise.all([
        api.get(`/competitors/${compId}/price-history`),
        api.get(`/competitors/${compId}/sentiment-history`),
        api.get(`/reports/competitor/${compId}`),
        api.get(`/competitors/${compId}/intelligence`).catch(() => ({ data: null })),
      ]);
      setPriceHistory(Array.isArray(priceRes.data) ? priceRes.data : []);
      setSentimentHistory(Array.isArray(sentRes.data) ? sentRes.data : []);
      setReports(Array.isArray(repRes.data) ? repRes.data : []);
      setIntelligenceData(intelRes?.data || null);
    } catch (err) {
      console.error('Failed to fetch charts history:', err);
      setPriceHistory([]);
      setSentimentHistory([]);
      setReports([]);
      setIntelligenceData(null);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, [fetchCompetitors]);

  useEffect(() => {
    if (selectedCompId) {
      fetchDetails(selectedCompId);
    }
  }, [selectedCompId]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleTriggerPipeline = async (compId) => {
    const comp = competitors.find((c) => c.id === compId);
    const compName = comp?.name || 'Competitor';
    try {
      const res = await api.post(`/pipeline/run/${compId}`);
      const newRun = { runId: res.data.agent_run_id, compId, compName };
      setActiveRuns((prev) => {
        const filtered = prev.filter((r) => r.compId !== compId);
        return [...filtered, newRun];
      });
      toast.info(`Agent pipeline launched for ${compName}`, 'Agent Pipeline');
    } catch (err) {
      console.error('Failed to start agent run:', err);
      toast.error(`Failed to launch agent run for ${compName}. Please check connection.`);
    }
  };

  const handleRunAllPipelines = async () => {
    if (!competitors || competitors.length === 0) return;
    toast.info(`Launching ${competitors.length} concurrent agent pipelines...`, 'Concurrent Pipeline Start');
    for (const comp of competitors) {
      await handleTriggerPipeline(comp.id);
    }
  };

  const handleRunComplete = (finishedRunId, compId) => {
    setActiveRuns((prev) => prev.filter((r) => r.runId !== finishedRunId));
    fetchCompetitors();
    if (selectedCompId === compId) fetchDetails(selectedCompId);
    const comp = competitors.find((c) => c.id === compId);
    toast.success(`Agent pipeline for ${comp?.name || 'Competitor'} completed!`, 'Pipeline Finished');
  };

  const handleDeleteCompetitor = async (compId) => {
    const isConfirmed = await toast.confirm({
      title: 'Delete Competitor Target',
      message: 'Are you sure you want to delete this competitor target and all associated snapshots?',
      confirmText: 'Delete Target',
      type: 'danger',
    });
    if (!isConfirmed) return;

    try {
      await api.delete(`/competitors/${compId}`);
      if (selectedCompId === compId) {
        setSelectedCompId(null);
        setPriceHistory([]);
        setSentimentHistory([]);
        setReports([]);
      }
      toast.success('Competitor target deleted.');
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to delete competitor:', err);
      toast.error('Failed to delete competitor target.');
    }
  };

  const handleOpenAddModal = () => {
    setAddError('');
    setNewCompName('');
    setNewPricingUrl('');
    const currentSaved = user?.company_url || localStorage.getItem('ci_saved_company_url') || '';
    setNewCompanyUrl(currentSaved);
    setUseSavedUrl(Boolean(currentSaved));
    setShowAddModal(true);
  };

  const handleAddCompetitorSubmit = async (e) => {
    e.preventDefault();
    if (!newCompName.trim()) return;
    setSubmittingAdd(true);
    setAddError('');

    const effectiveCompanyUrl = (useSavedUrl && savedCompanyUrl) ? savedCompanyUrl : newCompanyUrl;

    try {
      const payload = {
        name: newCompName.trim(),
        company_url: effectiveCompanyUrl || null,
        pricing_url: newPricingUrl || null,
        review_urls: [],
        news_keywords: [newCompName.trim()],
      };
      const res = await api.post('/competitors/', payload);

      // Auto-save new company URL to user profile if user changed/entered a new URL
      if (effectiveCompanyUrl && effectiveCompanyUrl !== user?.company_url) {
        try {
          await api.put('/auth/profile', {
            name: user?.name,
            company_name: user?.company_name,
            company_url: effectiveCompanyUrl,
          });
          localStorage.setItem('ci_saved_company_url', effectiveCompanyUrl);
        } catch (profileErr) {
          console.error('Failed to auto-update profile company URL:', profileErr);
        }
      }

      setShowAddModal(false);
      setNewCompName('');
      setNewPricingUrl('');
      await fetchCompetitors();
      setSelectedCompId(res.data.id);
    } catch (err) {
      console.error('Failed to add competitor:', err);
      if (err.response?.status === 409) {
        setAddError(err.response.data.detail || 'A competitor with this domain already exists in your account.');
      } else {
        setAddError('Failed to add competitor.');
      }
    } finally {
      setSubmittingAdd(false);
    }
  };

  const selectedCompetitor = Array.isArray(competitors) ? competitors.find((c) => c.id === selectedCompId) : null;
  const latestReport = Array.isArray(reports) && reports.length > 0 ? reports[0] : null;

  // KPI data
  const totalCompetitors = competitors.length;
  const totalReports = reports.length;
  const avgSentiment = sentimentHistory.length > 0
    ? (sentimentHistory.reduce((s, h) => s + (h.score || 0), 0) / sentimentHistory.length).toFixed(2)
    : '—';
  const totalPriceChanges = priceHistory.filter(p => !p.is_baseline).length;

  return (
    <div className="min-h-screen bg-[#050507] text-slate-100 flex font-sans noise-overlay">
      {/* Responsive Sidebar */}
      <Sidebar
        onToggleChat={() => setShowChat(!showChat)}
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Top Navbar */}
        <header className="bg-[#08080f]/80 backdrop-blur-xl border-b border-white/[0.04] sticky top-0 z-30">
          <div className="px-3 sm:px-6 py-2.5 sm:py-3 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              {/* Mobile Menu Button */}
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 transition-colors shrink-0"
                title="Open Navigation"
              >
                <Menu className="w-5 h-5" />
              </button>

              {/* Mobile Brand Logo */}
              <img
                src="/favicon.svg"
                alt="Logo"
                className="w-7 h-7 rounded-lg lg:hidden shrink-0"
              />

              <div className="min-w-0">
                <h1 className="text-xs sm:text-sm font-bold text-white font-display flex items-center gap-1.5 truncate">
                  <LayoutDashboard className="w-4 h-4 text-indigo-400 shrink-0 hidden xs:inline-block" />
                  <span className="truncate">CI Dashboard</span>
                </h1>
                <p className="text-[10px] text-slate-500 hidden sm:block truncate">Real-time competitive analysis command center</p>
              </div>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
              <div className="hidden md:flex items-center">
                <LiveClock />
              </div>

              <div className="h-4 w-px bg-white/[0.06] hidden md:block" />

              <button
                onClick={() => setShowChat(!showChat)}
                className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 sm:px-3.5 py-1.5 sm:py-2 rounded-xl transition-all duration-300 active:scale-95 ${
                  showChat
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/25'
                    : 'bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-300 border border-indigo-500/20'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-cyan-400" />
                <span className="hidden sm:inline">RAG Chat</span>
                <span className="sm:hidden text-[11px]">Chat</span>
                {!showChat && (
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 badge-pulse" />
                )}
              </button>

              <div className="h-4 w-px bg-white/[0.06] hidden xs:block" />

              <div className="flex items-center gap-1.5">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shadow-lg shadow-indigo-600/20 shrink-0">
                  {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
                </div>
                <span className="text-xs text-slate-300 font-medium hidden md:block">
                  {user?.name || user?.email}
                </span>
              </div>

              <button
                onClick={handleLogout}
                title="Sign Out"
                className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all duration-200"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Aurora Effect */}
        <div className="relative">
          <div className="absolute top-0 left-0 right-0 h-[120px] bg-gradient-to-b from-indigo-500/[0.03] via-purple-500/[0.02] to-transparent pointer-events-none" />
        </div>

        {/* Main Dashboard Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
            {/* Welcome Banner + KPIs */}
            <div className="animate-fade-in-up">
              {/* Welcome */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-5">
                <div>
                  <h2 className="text-xl font-bold text-white font-display">
                    Welcome back, <span className="gradient-text-vivid">{user?.name || 'Agent'}</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Your competitive intelligence overview at a glance</p>
                </div>
                <button
                  onClick={handleOpenAddModal}
                  className="flex items-center gap-2 btn-gradient px-4 py-2.5 rounded-xl text-xs shadow-lg shadow-indigo-600/20"
                >
                  <Plus className="w-4 h-4" />
                  Add Competitor
                </button>
              </div>

              {/* KPI Cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="kpi-card kpi-indigo card-3d">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-2 rounded-lg bg-indigo-500/10">
                      <Globe className="w-4 h-4 text-indigo-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Competitors</span>
                  </div>
                  <p className="text-2xl font-bold text-white counter-number">{totalCompetitors}</p>
                  <p className="text-[11px] text-slate-500 mt-1">Active targets tracked</p>
                </div>

                <div className="kpi-card kpi-emerald card-3d">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-2 rounded-lg bg-emerald-500/10">
                      <FileText className="w-4 h-4 text-emerald-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Reports</span>
                  </div>
                  <p className="text-2xl font-bold text-white counter-number">{totalReports}</p>
                  <p className="text-[11px] text-slate-500 mt-1">Intelligence briefs</p>
                </div>

                <div className="kpi-card kpi-violet card-3d">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-2 rounded-lg bg-violet-500/10">
                      <Activity className="w-4 h-4 text-violet-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Avg Sentiment</span>
                  </div>
                  <p className="text-2xl font-bold text-white counter-number">{avgSentiment}</p>
                  <p className="text-[11px] text-slate-500 mt-1">VADER compound score</p>
                </div>

                <div className="kpi-card kpi-amber card-3d">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-2 rounded-lg bg-amber-500/10">
                      <DollarSign className="w-4 h-4 text-amber-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Price Changes</span>
                  </div>
                  <p className="text-2xl font-bold text-white counter-number">{totalPriceChanges}</p>
                  <p className="text-[11px] text-slate-500 mt-1">Detected movements</p>
                </div>
              </div>
            </div>

            {/* Active Concurrent Pipeline Runs Status Grid */}
            {activeRuns.length > 0 && (
              <div className="space-y-3 animate-fade-in-up">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2 font-display">
                    <Zap className="w-3.5 h-3.5 text-amber-400" />
                    Active Agent Pipelines ({activeRuns.length})
                  </h3>
                  {activeRuns.length > 1 && (
                    <span className="text-[10px] text-amber-400 font-mono bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md animate-pulse">
                      Concurrent Multi-Agent Processing Active
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {activeRuns.map((run) => (
                    <AgentRunStatus
                      key={run.runId}
                      runId={run.runId}
                      competitorName={run.compName}
                      onComplete={() => handleRunComplete(run.runId, run.compId)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Section Divider */}
            <div className="section-divider text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
              Intelligence Analysis
            </div>

            {/* Dashboard Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Tracked Competitor List */}
              <div className="lg:col-span-1 space-y-6 stagger-item" style={{ '--i': 0 }}>
                <CompetitorList
                  competitors={competitors}
                  selectedId={selectedCompId}
                  runningCompIds={activeRuns.map((r) => r.compId)}
                  onSelect={setSelectedCompId}
                  onRunPipeline={handleTriggerPipeline}
                  onRunAllPipelines={handleRunAllPipelines}
                  onOpenChat={(id) => {
                    setSelectedCompId(id);
                    setShowChat(true);
                  }}
                  onAddCompetitor={handleOpenAddModal}
                  onDeleteCompetitor={handleDeleteCompetitor}
                />
              </div>

              {/* Right Column: Intelligence Panels */}
              <div className="lg:col-span-2 space-y-6 stagger-item" style={{ '--i': 1 }}>
                <ComparativeMatrix
                  selectedCompetitor={selectedCompetitor}
                  userProfile={user}
                  latestReport={latestReport}
                  intelligenceData={intelligenceData}
                />

                <div id="price-timeline-section">
                  <PriceTimeline
                    priceHistory={priceHistory}
                    competitorName={selectedCompetitor?.name}
                  />
                </div>

                <div id="sentiment-section">
                  <SentimentChart
                    sentimentHistory={sentimentHistory}
                    competitorName={selectedCompetitor?.name}
                    userCompany={user}
                  />
                </div>

                <div id="reports-section">
                  <ReportsPanel selectedCompetitorId={selectedCompId} />
                </div>

                <div id="notes-section">
                  <CompetitorNotes selectedCompetitor={selectedCompetitor} />
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Dual-URL Add Competitor Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-scale-in" style={{ animationDuration: '0.25s' }}>
          <div className="glass-card rounded-2xl max-w-md w-full p-6 neon-border shadow-2xl space-y-4 animate-spring-in">
            <div className="flex items-center justify-between border-b border-white/[0.04] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2 font-display">
                <div className="p-1.5 rounded-lg bg-indigo-500/10">
                  <Building2 className="w-4 h-4 text-indigo-400" />
                </div>
                Add Competitor Target
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-500 hover:text-slate-200 transition-all duration-200 hover:rotate-90 p-1"
              >
                ✕
              </button>
            </div>

            {addError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl text-xs flex items-center gap-2 animate-scale-in">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{addError}</span>
              </div>
            )}

            <form onSubmit={handleAddCompetitorSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Competitor Name *
                </label>
                <input
                  type="text"
                  required
                  value={newCompName}
                  onChange={(e) => setNewCompName(e.target.value)}
                  placeholder="e.g. Stripe, Linear, Vercel"
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 input-glow transition-all duration-300"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  URL 1: Your Company URL
                </label>

                {useSavedUrl && savedCompanyUrl ? (
                  <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-between gap-3 animate-scale-in">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 text-[10px] text-indigo-300 font-semibold uppercase tracking-wider">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>Using Saved Company URL</span>
                      </div>
                      <p className="text-xs font-mono text-slate-200 truncate mt-0.5">{savedCompanyUrl}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setUseSavedUrl(false);
                        setNewCompanyUrl(savedCompanyUrl);
                      }}
                      className="px-2.5 py-1 text-[11px] bg-white/[0.06] hover:bg-white/[0.12] text-slate-300 rounded-lg transition-colors font-medium shrink-0"
                    >
                      Change URL
                    </button>
                  </div>
                ) : (
                  <div className="space-y-1.5 animate-scale-in">
                    <input
                      type="url"
                      value={newCompanyUrl}
                      onChange={(e) => setNewCompanyUrl(e.target.value)}
                      placeholder="https://mycompany.com"
                      className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 input-glow transition-all duration-300"
                    />
                    {savedCompanyUrl && (
                      <button
                        type="button"
                        onClick={() => {
                          setUseSavedUrl(true);
                          setNewCompanyUrl(savedCompanyUrl);
                        }}
                        className="text-[10px] text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 transition-colors"
                      >
                        ← Revert to saved URL ({savedCompanyUrl})
                      </button>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Competitor URL *
                </label>
                <input
                  type="url"
                  required
                  value={newPricingUrl}
                  onChange={(e) => setNewPricingUrl(e.target.value)}
                  placeholder="https://competitor.com (e.g. https://groq.com, https://stripe.com)"
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 input-glow transition-all duration-300"
                />
                <div className="mt-1.5 p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/15 text-[10px] text-indigo-300 flex items-center gap-1.5">
                  <span className="shrink-0 font-bold">✨ Auto-Crawler:</span>
                  <span>Our Autonomous Agent Network will automatically crawl, navigate, and discover all related pricing, product, feature, and enterprise sub-pages.</span>
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 rounded-xl transition-all duration-200 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingAdd}
                  className="px-4 py-2.5 btn-gradient rounded-xl transition-all duration-200 text-xs disabled:opacity-50 disabled:hover:scale-100"
                >
                  {submittingAdd ? 'Adding...' : 'Save Competitor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Floating RAG Chat Widget */}
      {showChat && (
        <div className="fixed bottom-6 right-6 z-40">
          <ChatWidget
            selectedCompetitor={selectedCompetitor}
            onClose={() => setShowChat(false)}
          />
        </div>
      )}
    </div>
  );
}
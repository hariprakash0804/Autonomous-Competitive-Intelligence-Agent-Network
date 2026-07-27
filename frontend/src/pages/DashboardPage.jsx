import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

import CompetitorList from '../components/CompetitorList';
import PriceTimeline from '../components/PriceTimeline';
import SentimentChart from '../components/SentimentChart';
import AgentRunStatus from '../components/AgentRunStatus';
import ChatWidget from '../components/ChatWidget';
import ReportsPanel from '../components/ReportsPanel';

import { Bot, LogOut, Plus, Sparkles, Building2, TrendingUp, BarChart2 } from 'lucide-react';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [competitors, setCompetitors] = useState([]);
  const [selectedCompId, setSelectedCompId] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [sentimentHistory, setSentimentHistory] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [showChat, setShowChat] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  // New competitor form state
  const [newCompName, setNewCompName] = useState('');
  const [newPricingUrl, setNewPricingUrl] = useState('');
  const [newReviewUrl, setNewReviewUrl] = useState('');

  const fetchCompetitors = async () => {
    try {
      const res = await api.get('/competitors/');
      setCompetitors(res.data);
      if (res.data.length > 0 && !selectedCompId) {
        setSelectedCompId(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch competitors:', err);
    }
  };

  const fetchDetails = async (compId) => {
    if (!compId) return;
    try {
      const [priceRes, sentRes] = await Promise.all([
        api.get(`/competitors/${compId}/price-history`),
        api.get(`/competitors/${compId}/sentiment-history`),
      ]);
      setPriceHistory(priceRes.data);
      setSentimentHistory(sentRes.data);
    } catch (err) {
      console.error('Failed to fetch charts history:', err);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, []);

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
    try {
      const res = await api.post(`/pipeline/run/${compId}`);
      setActiveRunId(res.data.agent_run_id);
    } catch (err) {
      console.error('Failed to start agent run:', err);
      alert('Failed to launch agent run. Please check backend connection.');
    }
  };

  const handleRunComplete = () => {
    fetchCompetitors();
    if (selectedCompId) fetchDetails(selectedCompId);
  };

  const handleDeleteCompetitor = async (compId) => {
    try {
      await api.delete(`/competitors/${compId}`);
      if (selectedCompId === compId) {
        setSelectedCompId(null);
        setPriceHistory([]);
        setSentimentHistory([]);
      }
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to delete competitor:', err);
      alert('Failed to delete competitor.');
    }
  };

  const handleAddCompetitorSubmit = async (e) => {
    e.preventDefault();
    if (!newCompName.trim()) return;

    try {
      const payload = {
        name: newCompName,
        pricing_url: newPricingUrl || null,
        review_urls: newReviewUrl ? [newReviewUrl] : [],
        news_keywords: [newCompName],
      };
      const res = await api.post('/competitors/', payload);
      setShowAddModal(false);
      setNewCompName('');
      setNewPricingUrl('');
      setNewReviewUrl('');
      await fetchCompetitors();
      setSelectedCompId(res.data.id);
    } catch (err) {
      console.error('Failed to add competitor:', err);
      alert('Failed to add competitor.');
    }
  };

  const selectedCompetitor = competitors.find((c) => c.id === selectedCompId);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-100 leading-tight">
                Autonomous Competitive Intelligence
              </h1>
              <p className="text-[11px] text-slate-400">Agent Network Platform</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowChat(!showChat)}
              className="flex items-center gap-2 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-semibold px-3.5 py-2 rounded-xl transition"
            >
              <Sparkles className="w-4 h-4 text-indigo-400" /> RAG AI Assistant
            </button>

            <div className="h-4 w-px bg-slate-800"></div>

            <span className="text-xs text-slate-300 font-medium">
              {user?.name || user?.email}
            </span>

            <button
              onClick={handleLogout}
              title="Sign Out"
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Dashboard Layout */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 space-y-6 w-full">
        {/* Active Pipeline Run Status Poller */}
        {activeRunId && (
          <AgentRunStatus runId={activeRunId} onComplete={handleRunComplete} />
        )}

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Tracked Competitor List */}
          <div className="lg:col-span-1 space-y-6">
            <CompetitorList
              competitors={competitors}
              selectedId={selectedCompId}
              onSelect={setSelectedCompId}
              onRunPipeline={handleTriggerPipeline}
              onOpenChat={(id) => {
                setSelectedCompId(id);
                setShowChat(true);
              }}
              onAddCompetitor={() => setShowAddModal(true)}
              onDeleteCompetitor={handleDeleteCompetitor}
            />
          </div>

          {/* Right Column: Recharts Visualizations & Reports */}
          <div className="lg:col-span-2 space-y-6">
            <PriceTimeline
              priceHistory={priceHistory}
              competitorName={selectedCompetitor?.name}
            />

            <SentimentChart
              sentimentHistory={sentimentHistory}
              competitorName={selectedCompetitor?.name}
            />

            <ReportsPanel selectedCompetitorId={selectedCompId} />
          </div>
        </div>
      </main>

      {/* Add Competitor Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-indigo-400" /> Add New Competitor Target
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddCompetitorSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Competitor Name *
                </label>
                <input
                  type="text"
                  required
                  value={newCompName}
                  onChange={(e) => setNewCompName(e.target.value)}
                  placeholder="e.g. Vercel, Linear, Supabase"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Pricing URL
                </label>
                <input
                  type="url"
                  value={newPricingUrl}
                  onChange={(e) => setNewPricingUrl(e.target.value)}
                  placeholder="https://example.com/pricing"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Review / About URL
                </label>
                <input
                  type="url"
                  value={newReviewUrl}
                  onChange={(e) => setNewReviewUrl(e.target.value)}
                  placeholder="https://example.com/about"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition"
                >
                  Save Competitor
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

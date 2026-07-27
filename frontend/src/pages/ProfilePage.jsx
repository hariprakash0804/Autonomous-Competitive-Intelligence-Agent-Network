import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import {
  User,
  Building2,
  Globe,
  Mail,
  Shield,
  Save,
  Plus,
  Edit2,
  Trash2,
  Play,
  Bot,
  LogOut,
  LayoutDashboard,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Search
} from 'lucide-react';

export default function ProfilePage() {
  const { user, login, logout } = useAuth();
  const navigate = useNavigate();

  // Profile Form state
  const [name, setName] = useState(user?.name || '');
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [companyUrl, setCompanyUrl] = useState(user?.company_url || '');
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMsg, setProfileMsg] = useState({ type: '', text: '' });

  // Competitors list state
  const [competitors, setCompetitors] = useState([]);
  const [loadingComps, setLoadingComps] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Edit Competitor Modal state
  const [editingComp, setEditingComp] = useState(null);
  const [editName, setEditName] = useState('');
  const [editCompanyUrl, setEditCompanyUrl] = useState('');
  const [editPricingUrl, setEditPricingUrl] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState('');

  // Add Competitor Modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [addName, setAddName] = useState('');
  const [addCompanyUrl, setAddCompanyUrl] = useState(user?.company_url || '');
  const [addPricingUrl, setAddPricingUrl] = useState('');
  const [addingComp, setAddingComp] = useState(false);
  const [addError, setAddError] = useState('');

  const fetchProfile = async () => {
    try {
      const res = await api.get('/auth/me');
      setName(res.data.name || '');
      setCompanyName(res.data.company_name || '');
      setCompanyUrl(res.data.company_url || '');
    } catch (err) {
      console.error('Failed to fetch profile:', err);
    }
  };

  const fetchCompetitors = async () => {
    setLoadingComps(true);
    try {
      const res = await api.get('/competitors/');
      setCompetitors(res.data);
    } catch (err) {
      console.error('Failed to fetch competitors:', err);
    } finally {
      setLoadingComps(false);
    }
  };

  useEffect(() => {
    fetchProfile();
    fetchCompetitors();
  }, []);

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    setProfileMsg({ type: '', text: '' });
    try {
      await api.put('/auth/profile', {
        name,
        company_name: companyName,
        company_url: companyUrl,
      });
      setProfileMsg({ type: 'success', text: 'Profile & Company details updated successfully!' });
    } catch (err) {
      console.error('Failed to update profile:', err);
      setProfileMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to update profile.' });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleOpenEdit = (comp) => {
    setEditingComp(comp);
    setEditName(comp.name || '');
    setEditCompanyUrl(comp.company_url || companyUrl || '');
    setEditPricingUrl(comp.pricing_url || '');
    setEditError('');
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingComp) return;
    setSavingEdit(true);
    setEditError('');
    try {
      await api.put(`/competitors/${editingComp.id}`, {
        name: editName,
        company_url: editCompanyUrl,
        pricing_url: editPricingUrl,
      });
      setEditingComp(null);
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to edit competitor:', err);
      if (err.response?.status === 409) {
        setEditError(err.response.data.detail || 'A competitor with this domain already exists.');
      } else {
        setEditError('Failed to update competitor.');
      }
    } finally {
      setSavingEdit(false);
    }
  };

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    if (!addName.trim()) return;
    setAddingComp(true);
    setAddError('');
    try {
      await api.post('/competitors/', {
        name: addName,
        company_url: addCompanyUrl || companyUrl || null,
        pricing_url: addPricingUrl || null,
        review_urls: [],
        news_keywords: [addName],
      });
      setShowAddModal(false);
      setAddName('');
      setAddPricingUrl('');
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to add competitor:', err);
      if (err.response?.status === 409) {
        setAddError(err.response.data.detail || 'A competitor with this domain already exists in your account.');
      } else {
        setAddError('Failed to add competitor.');
      }
    } finally {
      setAddingComp(false);
    }
  };

  const handleDelete = async (compId) => {
    if (!window.confirm('Are you sure you want to delete this competitor target?')) return;
    try {
      await api.delete(`/competitors/${compId}`);
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to delete competitor:', err);
      alert('Failed to delete competitor.');
    }
  };

  const handleTriggerRun = async (compId) => {
    try {
      await api.post(`/pipeline/run/${compId}`);
      alert('Background multi-agent run launched successfully!');
      navigate('/dashboard');
    } catch (err) {
      console.error('Failed to launch run:', err);
      alert('Failed to launch agent run.');
    }
  };

  const filteredCompetitors = competitors.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.domain && c.domain.toLowerCase().includes(searchQuery.toLowerCase()))
  );

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
              <p className="text-[11px] text-slate-400">User Profile & Competitor Management</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold px-3.5 py-2 rounded-xl transition"
            >
              <LayoutDashboard className="w-4 h-4 text-indigo-400" /> Go to Dashboard
            </button>

            <div className="h-4 w-px bg-slate-800" />

            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              title="Sign Out"
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 space-y-8 w-full">
        {/* Profile Header Greeting */}
        <div className="bg-gradient-to-r from-indigo-900/40 via-slate-900 to-slate-900 border border-indigo-500/20 rounded-2xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 font-bold text-xl">
              {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100">{user?.name || 'User Profile'}</h2>
              <p className="text-xs text-slate-400 font-mono mt-0.5">{user?.email}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-semibold text-emerald-400">
                  JWT Session Active
                </span>
                {user?.company_name && (
                  <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-[10px] font-semibold text-indigo-300">
                    {user.company_name}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-indigo-600/20 transition"
            >
              <Plus className="w-4 h-4" /> Add Competitor Target
            </button>
          </div>
        </div>

        {/* Profile Settings & Competitors Management Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: User & Company Settings Form */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <User className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-slate-100">User & Company Details</h3>
              </div>

              {profileMsg.text && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    profileMsg.type === 'success'
                      ? 'bg-emerald-950/60 border border-emerald-500/30 text-emerald-300'
                      : 'bg-rose-950/60 border border-rose-500/30 text-rose-300'
                  }`}
                >
                  {profileMsg.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                  <span>{profileMsg.text}</span>
                </div>
              )}

              <form onSubmit={handleProfileSubmit} className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1">
                    <User className="w-3.5 h-3.5 text-slate-400" /> Full Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-100 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1">
                    <Mail className="w-3.5 h-3.5 text-slate-400" /> Email Address
                  </label>
                  <input
                    type="email"
                    disabled
                    value={user?.email || ''}
                    className="w-full bg-slate-950/50 border border-slate-800/80 rounded-xl px-3.5 py-2.5 text-slate-500 cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1">
                    <Building2 className="w-3.5 h-3.5 text-slate-400" /> Your Company Name
                  </label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-100 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1">
                    <Globe className="w-3.5 h-3.5 text-slate-400" /> Your Company URL (Default)
                  </label>
                  <input
                    type="url"
                    value={companyUrl}
                    onChange={(e) => setCompanyUrl(e.target.value)}
                    placeholder="https://acme.com"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={savingProfile}
                  className="w-full mt-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {savingProfile ? 'Saving...' : 'Save Profile Changes'}
                </button>
              </form>
            </div>
          </div>

          {/* Right Column: Tracked Competitors Management Table */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-3">
                <div>
                  <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-indigo-400" /> Managed Competitors ({competitors.length})
                  </h3>
                  <p className="text-xs text-slate-400">Zero-duplication verified competitor tracking list</p>
                </div>

                {/* Search Bar */}
                <div className="relative w-full sm:w-64">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter competitors..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              {loadingComps ? (
                <div className="py-8 text-center text-xs text-slate-400">Loading competitors...</div>
              ) : filteredCompetitors.length === 0 ? (
                <div className="py-12 text-center text-slate-500 space-y-2">
                  <Building2 className="w-8 h-8 text-slate-700 mx-auto" />
                  <p className="text-xs">No competitors found matching your criteria.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 font-semibold">
                        <th className="pb-3 pt-1 px-3">Competitor Target</th>
                        <th className="pb-3 pt-1 px-3">Pricing URL</th>
                        <th className="pb-3 pt-1 px-3">Snapshots</th>
                        <th className="pb-3 pt-1 px-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {(Array.isArray(filteredCompetitors) ? filteredCompetitors : []).map((c) => (
                        <tr key={c.id} className="hover:bg-slate-800/30 transition">
                          <td className="py-3 px-3">
                            <div className="font-bold text-slate-100">{c.name}</div>
                            {c.domain && (
                              <span className="inline-block mt-0.5 text-[10px] font-mono bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded">
                                {c.domain}
                              </span>
                            )}
                          </td>

                          <td className="py-3 px-3 font-mono text-slate-300 max-w-[200px] truncate">
                            {c.pricing_url ? (
                              <a href={c.pricing_url} target="_blank" rel="noreferrer" className="hover:underline text-indigo-400">
                                {c.pricing_url}
                              </a>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>

                          <td className="py-3 px-3">
                            <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded font-mono font-semibold">
                              {c.snapshot_count || 0}
                            </span>
                          </td>

                          <td className="py-3 px-3 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => handleTriggerRun(c.id)}
                                title="Run Multi-Agent Analysis"
                                className="p-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg transition"
                              >
                                <Play className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleOpenEdit(c)}
                                title="Edit Competitor Details"
                                className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg transition"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDelete(c.id)}
                                title="Delete Competitor"
                                className="p-1.5 bg-rose-500/10 hover:bg-rose-600 text-rose-400 hover:text-white rounded-lg transition"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Edit Competitor Modal */}
      {editingComp && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Edit2 className="w-5 h-5 text-indigo-400" /> Edit Competitor Target
              </h3>
              <button onClick={() => setEditingComp(null)} className="text-slate-400 hover:text-slate-200">
                ✕
              </button>
            </div>

            {editError && (
              <div className="p-3 bg-rose-950/60 border border-rose-500/30 text-rose-300 rounded-xl text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleSaveEdit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Competitor Name *</label>
                <input
                  type="text"
                  required
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Your Company URL</label>
                <input
                  type="url"
                  value={editCompanyUrl}
                  onChange={(e) => setEditCompanyUrl(e.target.value)}
                  placeholder="https://mycompany.com"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Competitor Pricing URL</label>
                <input
                  type="url"
                  value={editPricingUrl}
                  onChange={(e) => setEditPricingUrl(e.target.value)}
                  placeholder="https://competitor.com/pricing"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingComp(null)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition disabled:opacity-50"
                >
                  {savingEdit ? 'Updating...' : 'Save Competitor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Competitor Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-indigo-400" /> Add Dual-URL Competitor Target
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-slate-200">
                ✕
              </button>
            </div>

            {addError && (
              <div className="p-3 bg-rose-950/60 border border-rose-500/30 text-rose-300 rounded-xl text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{addError}</span>
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Competitor Name *</label>
                <input
                  type="text"
                  required
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  placeholder="e.g. Stripe, Linear, Vercel"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">URL 1: Your Company URL</label>
                <input
                  type="url"
                  value={addCompanyUrl}
                  onChange={(e) => setAddCompanyUrl(e.target.value)}
                  placeholder="https://mycompany.com"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">URL 2: Competitor Pricing URL</label>
                <input
                  type="url"
                  value={addPricingUrl}
                  onChange={(e) => setAddPricingUrl(e.target.value)}
                  placeholder="https://competitor.com/pricing"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500"
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
                  disabled={addingComp}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition disabled:opacity-50"
                >
                  {addingComp ? 'Adding...' : 'Add Competitor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

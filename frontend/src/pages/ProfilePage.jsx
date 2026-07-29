import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import Sidebar from '../components/Sidebar';
import {
  User,
  Building2,
  Globe,
  Mail,
  Plus,
  Edit2,
  Trash2,
  Play,
  LogOut,
  LayoutDashboard,
  CheckCircle2,
  AlertCircle,
  Search,
  Bell,
  Menu,
} from 'lucide-react';

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Profile Form state
  const [name, setName] = useState(user?.name || '');
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [companyUrl, setCompanyUrl] = useState(user?.company_url || '');
  const [slackWebhookUrl, setSlackWebhookUrl] = useState(user?.slack_webhook_url || '');
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
  const [addCompanyUrl, setAddCompanyUrl] = useState(user?.company_url || localStorage.getItem('ci_saved_company_url') || '');
  const [useSavedAddUrl, setUseSavedAddUrl] = useState(Boolean(user?.company_url || localStorage.getItem('ci_saved_company_url')));
  const [addPricingUrl, setAddPricingUrl] = useState('');
  const [addingComp, setAddingComp] = useState(false);
  const [addError, setAddError] = useState('');

  const savedCompanyUrl = user?.company_url || localStorage.getItem('ci_saved_company_url') || '';

  const handleOpenAddModal = () => {
    setAddError('');
    setAddName('');
    setAddPricingUrl('');
    const currentSaved = user?.company_url || localStorage.getItem('ci_saved_company_url') || '';
    setAddCompanyUrl(currentSaved);
    setUseSavedAddUrl(Boolean(currentSaved));
    setShowAddModal(true);
  };

  const fetchProfile = async () => {
    try {
      const res = await api.get('/auth/me');
      setName(res.data.name || '');
      setCompanyName(res.data.company_name || '');
      setCompanyUrl(res.data.company_url || '');
      setSlackWebhookUrl(res.data.slack_webhook_url || '');
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
        slack_webhook_url: slackWebhookUrl,
      });
      setProfileMsg({ type: 'success', text: 'Profile & Webhook settings updated successfully!' });
    } catch (err) {
      console.error('Failed to update profile:', err);
      setProfileMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to update profile.' });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleEditClick = (comp) => {
    setEditingComp(comp);
    setEditName(comp.name || '');
    setEditCompanyUrl(comp.company_url || companyUrl || '');
    setEditPricingUrl(comp.pricing_url || '');
    setEditError('');
  };

  const handleEditSubmit = async (e) => {
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

    const effectiveCompanyUrl = (useSavedAddUrl && savedCompanyUrl) ? savedCompanyUrl : addCompanyUrl;

    try {
      await api.post('/competitors/', {
        name: addName.trim(),
        company_url: effectiveCompanyUrl || null,
        pricing_url: addPricingUrl || null,
        review_urls: [],
        news_keywords: [addName.trim()],
      });

      if (effectiveCompanyUrl && effectiveCompanyUrl !== user?.company_url) {
        try {
          await api.put('/auth/profile', {
            name,
            company_name: companyName,
            company_url: effectiveCompanyUrl,
          });
          localStorage.setItem('ci_saved_company_url', effectiveCompanyUrl);
        } catch (profileErr) {
          console.error('Failed to auto-update profile company URL:', profileErr);
        }
      }

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
    const isConfirmed = await toast.confirm({
      title: 'Delete Competitor Target',
      message: 'Are you sure you want to delete this competitor target? All associated snapshots and data will be permanently removed.',
      confirmText: 'Delete Target',
      type: 'danger',
    });
    if (!isConfirmed) return;

    try {
      await api.delete(`/competitors/${compId}`);
      toast.success('Competitor target deleted successfully');
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to delete competitor:', err);
      toast.error('Failed to delete competitor target.');
    }
  };

  const handleTriggerRun = async (compId) => {
    try {
      await api.post(`/pipeline/run/${compId}`);
      toast.success('Background multi-agent run launched successfully!', 'Agent Network');
      navigate('/dashboard');
    } catch (err) {
      console.error('Failed to launch run:', err);
      toast.error('Failed to launch background agent run.');
    }
  };

  const filteredCompetitors = competitors.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.domain && c.domain.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-[#050507] text-slate-100 flex font-sans noise-overlay">
      {/* Responsive Sidebar */}
      <Sidebar
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Top Navbar */}
        <header className="bg-[#08080f]/70 backdrop-blur-xl border-b border-white/[0.04] sticky top-0 z-30">
          <div className="px-4 sm:px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Mobile Menu Button */}
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 transition-colors"
                title="Open Navigation"
              >
                <Menu className="w-5 h-5" />
              </button>

              <div>
                <h1 className="text-xs sm:text-sm font-bold text-white font-display flex items-center gap-2">
                  <User className="w-4 h-4 text-violet-400" />
                  Profile & Competitor Management
                </h1>
                <p className="text-[10px] text-slate-500 hidden sm:block">Manage your identity and competitor tracking targets</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/dashboard')}
                className="flex items-center gap-2 bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 border border-white/[0.06] text-xs font-semibold px-3.5 py-2 rounded-xl transition-all duration-200"
              >
                <LayoutDashboard className="w-4 h-4 text-indigo-400" /> Dashboard
              </button>

              <div className="h-4 w-px bg-white/[0.06]" />

              <button
                onClick={() => {
                  logout();
                  navigate('/login');
                }}
                title="Sign Out"
                className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all duration-200"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
            {/* Profile Header Greeting */}
            <div className="glass-card rounded-2xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 neon-border animate-fade-in-up">
              <div className="flex items-center gap-4">
                {/* Animated Avatar Ring */}
                <div className="relative">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-purple-600 flex items-center justify-center text-white font-bold text-2xl font-display shadow-lg shadow-indigo-600/25">
                    {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
                  </div>
                  <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-emerald-400 border-[3px] border-[#0a0a12] badge-pulse" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white font-display">{user?.name || 'User Profile'}</h2>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">{user?.email}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="px-2.5 py-0.5 rounded-lg bg-emerald-500/10 border border-emerald-500/15 text-[10px] font-semibold text-emerald-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 badge-pulse" /> Session Active
                    </span>
                    {user?.company_name && (
                      <span className="px-2.5 py-0.5 rounded-lg bg-indigo-500/10 border border-indigo-500/15 text-[10px] font-semibold text-indigo-300">
                        {user.company_name}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-3">
                <div className="px-4 py-2 rounded-xl bg-white/[0.03] border border-white/[0.04] text-center">
                  <p className="text-lg font-bold text-white counter-number">{competitors.length}</p>
                  <p className="text-[10px] text-slate-500">Targets</p>
                </div>
                <div className="px-4 py-2 rounded-xl bg-white/[0.03] border border-white/[0.04] text-center">
                  <p className="text-lg font-bold text-white counter-number">
                    {competitors.reduce((s, c) => s + (c.snapshot_count || 0), 0)}
                  </p>
                  <p className="text-[10px] text-slate-500">Snapshots</p>
                </div>
                <button
                  onClick={handleOpenAddModal}
                  className="flex items-center gap-2 btn-gradient px-4 py-2.5 rounded-xl text-xs shadow-lg shadow-indigo-600/20"
                >
                  <Plus className="w-4 h-4" /> Add Target
                </button>
              </div>
            </div>

            {/* Profile Settings & Competitors Management */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: User & Company Settings Form */}
              <div className="lg:col-span-1 space-y-6 stagger-item" style={{ '--i': 0 }}>
                <div className="glass-card rounded-2xl p-6 space-y-5 neon-border">
                  <div className="flex items-center gap-2 border-b border-white/[0.04] pb-3">
                    <div className="p-1.5 rounded-lg bg-violet-500/10">
                      <User className="w-4 h-4 text-violet-400" />
                    </div>
                    <h3 className="text-sm font-bold text-white font-display">User & Company Details</h3>
                  </div>

                  {profileMsg.text && (
                    <div
                      className={`p-3 rounded-xl text-xs flex items-center gap-2 animate-scale-in ${
                        profileMsg.type === 'success'
                          ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300'
                          : 'bg-rose-500/10 border border-rose-500/20 text-rose-300'
                      }`}
                    >
                      {profileMsg.type === 'success' ? (
                        <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                      ) : (
                        <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                      )}
                      <span>{profileMsg.text}</span>
                    </div>
                  )}

                  <form onSubmit={handleProfileSubmit} className="space-y-4 text-xs">
                    <div>
                      <label className="block text-slate-400 font-semibold mb-1.5 flex items-center gap-1 text-[10px] uppercase tracking-wider">
                        <User className="w-3 h-3 text-slate-500" /> Full Name
                      </label>
                      <input
                        type="text"
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Jane Doe"
                        className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 font-semibold mb-1.5 flex items-center gap-1 text-[10px] uppercase tracking-wider">
                        <Mail className="w-3 h-3 text-slate-500" /> Email Address
                      </label>
                      <input
                        type="email"
                        disabled
                        value={user?.email || ''}
                        className="w-full bg-white/[0.02] rounded-xl px-3.5 py-2.5 text-slate-600 cursor-not-allowed border border-white/[0.03]"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 font-semibold mb-1.5 flex items-center gap-1 text-[10px] uppercase tracking-wider">
                        <Building2 className="w-3 h-3 text-slate-500" /> Company Name
                      </label>
                      <input
                        type="text"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        placeholder="Acme Corp"
                        className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 font-semibold mb-1.5 flex items-center gap-1 text-[10px] uppercase tracking-wider">
                        <Globe className="w-3 h-3 text-slate-500" /> Your Company Website
                      </label>
                      <input
                        type="url"
                        value={companyUrl}
                        onChange={(e) => setCompanyUrl(e.target.value)}
                        placeholder="https://mycompany.com"
                        className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 font-semibold mb-1.5 flex items-center gap-1 text-[10px] uppercase tracking-wider">
                        <Bell className="w-3 h-3 text-violet-400" /> Slack / Notification Webhook URL
                      </label>
                      <input
                        type="url"
                        value={slackWebhookUrl}
                        onChange={(e) => setSlackWebhookUrl(e.target.value)}
                        placeholder="https://hooks.slack.com/services/..."
                        className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300 font-mono text-[11px]"
                      />
                      <p className="text-[10px] text-slate-500 mt-1">Configure your personal Slack/Discord webhook URL for report deliveries</p>
                    </div>

                    <button
                      type="submit"
                      disabled={savingProfile}
                      className="w-full py-3 btn-gradient rounded-xl transition-all duration-300 font-semibold disabled:opacity-50 text-xs shadow-lg shadow-indigo-600/15"
                    >
                      {savingProfile ? 'Saving...' : 'Save Profile Changes'}
                    </button>
                  </form>
                </div>
              </div>

              {/* Right Column: Tracked Competitors Management Table */}
              <div className="lg:col-span-2 space-y-6 stagger-item" style={{ '--i': 1 }}>
                <div className="glass-card rounded-2xl p-6 space-y-4 neon-border">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/[0.04] pb-3">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2 font-display">
                        <div className="p-1.5 rounded-lg bg-indigo-500/10">
                          <Building2 className="w-4 h-4 text-indigo-400" />
                        </div>
                        Managed Competitors ({competitors?.length || 0})
                      </h3>
                      <p className="text-[10px] text-slate-500 mt-0.5">Zero-duplication verified competitor tracking list</p>
                    </div>

                    {/* Search Bar */}
                    <div className="relative w-full sm:w-64">
                      <Search className="w-4 h-4 text-slate-600 absolute left-3 top-2.5" />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Filter competitors..."
                        className="w-full bg-white/[0.03] rounded-xl pl-9 pr-3 py-2 text-xs text-slate-100 input-glow transition-all duration-300"
                      />
                    </div>
                  </div>

                  {loadingComps ? (
                    <div className="py-8 text-center text-xs text-slate-500">
                      <div className="w-6 h-6 border-2 border-indigo-400/20 border-t-indigo-400 rounded-full animate-spin mx-auto mb-3" />
                      Loading competitors...
                    </div>
                  ) : (!Array.isArray(filteredCompetitors) || filteredCompetitors.length === 0) ? (
                    <div className="py-12 text-center text-slate-600 space-y-3">
                      <div className="w-14 h-14 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-center mx-auto">
                        <Building2 className="w-7 h-7 text-slate-700" />
                      </div>
                      <p className="text-xs font-medium">No competitors found</p>
                      <p className="text-[10px] text-slate-600">Add a competitor target to start tracking</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-white/[0.04] text-slate-500 font-semibold text-[10px] uppercase tracking-wider">
                            <th className="pb-3 pt-1 px-3">Competitor Target</th>
                            <th className="pb-3 pt-1 px-3">Pricing URL</th>
                            <th className="pb-3 pt-1 px-3">Snapshots</th>
                            <th className="pb-3 pt-1 px-3 text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.03]">
                          {(Array.isArray(filteredCompetitors) ? filteredCompetitors : []).map((c, idx) => (
                            <tr
                              key={c.id}
                              className="hover:bg-white/[0.02] transition-all duration-200 stagger-item"
                              style={{ '--i': idx }}
                            >
                              <td className="py-3.5 px-3">
                                <div className="font-bold text-slate-100 text-[13px]">{c.name}</div>
                                {c.domain && (
                                  <span className="inline-block mt-0.5 text-[10px] font-mono bg-indigo-500/10 border border-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-lg">
                                    {c.domain}
                                  </span>
                                )}
                              </td>

                              <td className="py-3.5 px-3 text-slate-400 font-mono text-[11px] max-w-[180px] truncate">
                                {c.pricing_url || '—'}
                              </td>

                              <td className="py-3.5 px-3">
                                <span className="px-2 py-0.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-[11px] font-mono text-slate-300">
                                  {c.snapshot_count || 0}
                                </span>
                              </td>

                              <td className="py-3.5 px-3 text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    onClick={() => handleTriggerRun(c.id)}
                                    title="Trigger Agent Run"
                                    className="p-1.5 bg-indigo-500/10 hover:bg-indigo-600 text-indigo-400 hover:text-white rounded-lg transition-all duration-200"
                                  >
                                    <Play className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleEditClick(c)}
                                    title="Edit Competitor"
                                    className="p-1.5 bg-white/[0.03] hover:bg-white/[0.08] text-slate-400 hover:text-white rounded-lg transition-all duration-200"
                                  >
                                    <Edit2 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleDelete(c.id)}
                                    title="Delete Target"
                                    className="p-1.5 bg-rose-500/10 hover:bg-rose-600 text-rose-400 hover:text-white rounded-lg transition-all duration-200"
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
          </div>
        </main>
      </div>

      {/* Edit Competitor Modal */}
      {editingComp && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl max-w-md w-full p-6 neon-border shadow-2xl space-y-4 animate-spring-in">
            <div className="flex items-center justify-between border-b border-white/[0.04] pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2 font-display">
                <Building2 className="w-4 h-4 text-indigo-400" /> Edit Competitor Target
              </h3>
              <button onClick={() => setEditingComp(null)} className="text-slate-500 hover:text-slate-200 transition-all duration-200 hover:rotate-90">
                ✕
              </button>
            </div>

            {editError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/15 text-rose-300 rounded-xl text-xs flex items-center gap-2 animate-scale-in">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 text-[10px] uppercase tracking-wider">Competitor Name *</label>
                <input type="text" required value={editName} onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300" />
              </div>
              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 text-[10px] uppercase tracking-wider">Your Company URL</label>
                <input type="url" value={editCompanyUrl} onChange={(e) => setEditCompanyUrl(e.target.value)} placeholder="https://mycompany.com"
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300" />
              </div>
              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 text-[10px] uppercase tracking-wider">Competitor Pricing URL</label>
                <input type="url" value={editPricingUrl} onChange={(e) => setEditPricingUrl(e.target.value)} placeholder="https://competitor.com/pricing"
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 input-glow transition-all duration-300" />
              </div>
              <div className="pt-3 flex justify-end gap-2">
                <button type="button" onClick={() => setEditingComp(null)}
                  className="px-4 py-2.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 rounded-xl transition-all duration-200">Cancel</button>
                <button type="submit" disabled={savingEdit}
                  className="px-4 py-2.5 btn-gradient rounded-xl transition-all duration-200 disabled:opacity-50">
                  {savingEdit ? 'Updating...' : 'Save Competitor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Competitor Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl max-w-md w-full p-6 neon-border shadow-2xl space-y-4 animate-spring-in">
            <div className="flex items-center justify-between border-b border-white/[0.04] pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2 font-display">
                <Building2 className="w-4 h-4 text-indigo-400" /> Add Competitor Target
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-500 hover:text-slate-200 transition-all duration-200 hover:rotate-90">
                ✕
              </button>
            </div>

            {addError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/15 text-rose-300 rounded-xl text-xs flex items-center gap-2 animate-scale-in">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{addError}</span>
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 text-[10px] uppercase tracking-wider">Competitor Name *</label>
                <input type="text" required value={addName} onChange={(e) => setAddName(e.target.value)} placeholder="e.g. Stripe, Linear, Vercel"
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 input-glow transition-all duration-300" />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1.5 text-[10px] uppercase tracking-wider">URL 1: Your Company URL</label>
                {useSavedAddUrl && savedCompanyUrl ? (
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
                        setUseSavedAddUrl(false);
                        setAddCompanyUrl(savedCompanyUrl);
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
                      value={addCompanyUrl}
                      onChange={(e) => setAddCompanyUrl(e.target.value)}
                      placeholder="https://mycompany.com"
                      className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 input-glow transition-all duration-300"
                    />
                    {savedCompanyUrl && (
                      <button
                        type="button"
                        onClick={() => {
                          setUseSavedAddUrl(true);
                          setAddCompanyUrl(savedCompanyUrl);
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
                <label className="block text-slate-400 font-semibold mb-1 text-[10px] uppercase tracking-wider">Competitor URL *</label>
                <input type="url" required value={addPricingUrl} onChange={(e) => setAddPricingUrl(e.target.value)} placeholder="https://competitor.com (e.g. https://groq.com, https://stripe.com)"
                  className="w-full bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-600 input-glow transition-all duration-300" />
                <div className="mt-1.5 p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/15 text-[10px] text-indigo-300 flex items-center gap-1.5">
                  <span className="shrink-0 font-bold">✨ Auto-Crawler:</span>
                  <span>Our Autonomous Agent Network will automatically crawl, navigate, and discover all related pricing, product, feature, and enterprise sub-pages.</span>
                </div>
              </div>
              <div className="pt-3 flex justify-end gap-2">
                <button type="button" onClick={() => setShowAddModal(false)}
                  className="px-4 py-2.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 rounded-xl transition-all duration-200">Cancel</button>
                <button type="submit" disabled={addingComp}
                  className="px-4 py-2.5 btn-gradient rounded-xl transition-all duration-200 disabled:opacity-50">
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

import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import {
  Building2,
  Globe,
  FileText,
  Upload,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight
} from 'lucide-react';

export default function OnboardingModal({ onComplete }) {
  const { user, completeOnboarding } = useAuth();
  const toast = useToast();

  const [activeTab, setActiveTab] = useState('url'); // 'url' | 'text' | 'document'
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [companyUrl, setCompanyUrl] = useState(user?.company_url || '');
  const [descriptionText, setDescriptionText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!companyName.trim()) {
      setError('Please provide your company name.');
      return;
    }

    if (activeTab === 'url' && !companyUrl.trim()) {
      setError('Please provide a valid company website URL.');
      return;
    }

    if (activeTab === 'text' && !descriptionText.trim()) {
      setError('Please type a description of your company.');
      return;
    }

    if (activeTab === 'document' && !selectedFile) {
      setError('Please select a company document file to upload.');
      return;
    }

    setLoading(true);
    setStatusMessage('Gathering and extracting intelligence about your company...');

    try {
      const formData = new FormData();
      formData.append('method', activeTab);
      formData.append('company_name', companyName.trim());

      if (companyUrl.trim()) {
        formData.append('company_url', companyUrl.trim());
      }
      if (descriptionText.trim()) {
        formData.append('description_text', descriptionText.trim());
      }
      if (selectedFile) {
        formData.append('file', selectedFile);
      }

      await completeOnboarding(formData);

      toast.success('Company intelligence onboarding completed successfully!', 'Onboarding Complete');
      if (onComplete) onComplete();
    } catch (err) {
      console.error('Onboarding failed:', err);
      setError(err.response?.data?.detail || 'Failed to complete onboarding. Please try again.');
    } finally {
      setLoading(false);
      setStatusMessage('');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-xl z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="glass-card neon-border rounded-2xl max-w-xl w-full p-6 sm:p-8 shadow-2xl relative overflow-hidden animate-spring-in">
        {/* Top ambient glow */}
        <div className="absolute -top-20 -right-20 w-64 h-64 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 mb-3 signal-pulse">
            <Building2 className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-extrabold text-white font-display tracking-tight">
            Company Onboarding
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto font-medium">
            Describe your company so our autonomous agents can build your baseline competitive profile.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2 animate-scale-in">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Company Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
              Your Company Name *
            </label>
            <input
              type="text"
              required
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="e.g. Acme Corp, OpenAI, Vercel"
              className="w-full px-4 py-3 bg-white/[0.03] rounded-xl text-white placeholder-slate-600 text-sm input-glow transition-all duration-300"
            />
          </div>

          {/* Method Select Tabs */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
              Choose How to Describe Your Company *
            </label>
            <div className="grid grid-cols-3 gap-2 p-1.5 rounded-xl bg-white/[0.03] border border-white/[0.05]">
              <button
                type="button"
                onClick={() => { setActiveTab('url'); setError(''); }}
                className={`flex flex-col items-center justify-center py-2.5 px-2 rounded-lg text-xs font-semibold transition-all duration-200 gap-1 ${
                  activeTab === 'url'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/25'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                <Globe className="w-4 h-4" />
                <span>Website URL</span>
              </button>

              <button
                type="button"
                onClick={() => { setActiveTab('text'); setError(''); }}
                className={`flex flex-col items-center justify-center py-2.5 px-2 rounded-lg text-xs font-semibold transition-all duration-200 gap-1 ${
                  activeTab === 'text'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/25'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>Type Description</span>
              </button>

              <button
                type="button"
                onClick={() => { setActiveTab('document'); setError(''); }}
                className={`flex flex-col items-center justify-center py-2.5 px-2 rounded-lg text-xs font-semibold transition-all duration-200 gap-1 ${
                  activeTab === 'document'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/25'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                <Upload className="w-4 h-4" />
                <span>Upload File</span>
              </button>
            </div>
          </div>

          {/* Dynamic Tab Body */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
            {activeTab === 'url' && (
              <div className="space-y-2 animate-fade-in">
                <label className="block text-[11px] font-medium text-slate-400">
                  Enter your company website homepage or pricing URL:
                </label>
                <input
                  type="url"
                  value={companyUrl}
                  onChange={(e) => setCompanyUrl(e.target.value)}
                  placeholder="https://mycompany.com"
                  className="w-full px-4 py-3 bg-white/[0.03] rounded-xl text-white placeholder-slate-600 text-sm input-glow transition-all duration-300 font-mono text-xs"
                />
                <p className="text-[10px] text-slate-500 flex items-center gap-1.5 pt-1">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span>Our autonomous agent network will automatically crawl your site, extract features, and build your profile.</span>
                </p>
              </div>
            )}

            {activeTab === 'text' && (
              <div className="space-y-2 animate-fade-in">
                <label className="block text-[11px] font-medium text-slate-400">
                  Type a description of your products, value proposition, and pricing:
                </label>
                <textarea
                  rows={4}
                  value={descriptionText}
                  onChange={(e) => setDescriptionText(e.target.value)}
                  placeholder="e.g. We provide real-time AI analytics for enterprise sales teams. Our core plans start at $49/user/month with custom enterprise SLA options."
                  className="w-full p-3.5 bg-white/[0.03] rounded-xl text-white placeholder-slate-600 text-xs input-glow transition-all duration-300 resize-none"
                />
              </div>
            )}

            {activeTab === 'document' && (
              <div className="space-y-3 text-center animate-fade-in">
                <label className="block text-[11px] font-medium text-slate-400 text-left">
                  Upload pitch deck, product sheet, whitepaper, or company overview (PDF, TXT, MD):
                </label>
                <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-white/10 hover:border-indigo-500/40 rounded-xl cursor-pointer bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-300">
                  <Upload className="w-8 h-8 text-indigo-400 mb-2" />
                  <span className="text-xs font-semibold text-slate-300">
                    {selectedFile ? selectedFile.name : 'Click to choose or drag & drop file'}
                  </span>
                  <span className="text-[10px] text-slate-500 mt-1">Supports PDF, TXT, MD files up to 10MB</span>
                  <input
                    type="file"
                    accept=".pdf,.txt,.md,.doc,.docx"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>
                {selectedFile && (
                  <div className="flex items-center justify-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 py-1.5 px-3 rounded-lg border border-emerald-500/20">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span className="truncate">{selectedFile.name} ready for processing</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Loading status text */}
          {loading && (
            <div className="flex items-center justify-center gap-2 text-xs text-amber-400 bg-amber-500/10 p-3 rounded-xl border border-amber-500/20 animate-pulse">
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
              <span>{statusMessage}</span>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-4 btn-gradient rounded-xl text-sm font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 disabled:opacity-50 transition-all duration-300"
          >
            {loading ? (
              <span>Processing Intelligence...</span>
            ) : (
              <>
                <span>Complete Onboarding & Enter Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  User,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Globe,
  FileText,
  Activity,
  DollarSign,
  X,
  NotebookPen,
} from 'lucide-react';

export default function Sidebar({ onToggleChat, mobileOpen = false, onMobileClose }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleInsightClick = (type) => {
    onMobileClose?.();
    if (type === 'Competitors') {
      navigate('/profile');
    } else if (type === 'Price Intel') {
      navigate('/dashboard');
      setTimeout(() => {
        const el = document.getElementById('price-timeline-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else if (type === 'Sentiment') {
      navigate('/dashboard');
      setTimeout(() => {
        const el = document.getElementById('sentiment-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else if (type === 'Reports') {
      navigate('/dashboard');
      setTimeout(() => {
        const el = document.getElementById('reports-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else if (type === 'Notes') {
      navigate('/dashboard');
      setTimeout(() => {
        const el = document.getElementById('notes-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  };

  const navItems = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard', color: 'text-indigo-400' },
    { label: 'Profile & Targets', icon: User, path: '/profile', color: 'text-violet-400' },
  ];

  const toolItems = [
    {
      label: 'RAG AI Chat',
      icon: Sparkles,
      action: () => {
        onMobileClose?.();
        onToggleChat?.();
      },
      color: 'text-cyan-400',
    },
  ];

  const insightItems = [
    { label: 'Competitors', icon: Globe, color: 'text-emerald-400' },
    { label: 'Price Intel', icon: DollarSign, color: 'text-amber-400' },
    { label: 'Sentiment', icon: Activity, color: 'text-rose-400' },
    { label: 'Reports', icon: FileText, color: 'text-indigo-400' },
    { label: 'Notes', icon: NotebookPen, color: 'text-indigo-400' },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          onClick={() => onMobileClose?.()}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden transition-opacity animate-fade-in"
        />
      )}

      <aside
        className={`sidebar ${collapsed ? 'collapsed' : ''} fixed lg:static inset-y-0 left-0 z-50 transform ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        } transition-transform duration-300 ease-in-out h-full flex flex-col bg-[#08080f]/95 backdrop-blur-xl border-r border-white/[0.04] w-64 lg:w-auto`}
      >
      {/* Aurora glow on sidebar top */}
      <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-indigo-500/[0.04] to-transparent pointer-events-none" />

      {/* Logo Area */}
      <div className="p-4 border-b border-white/[0.04] relative flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <img
              src="/favicon.svg"
              alt="Logo"
              className="w-9 h-9 rounded-xl shadow-lg shadow-indigo-600/20 signal-pulse"
            />
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-[#08080f] badge-pulse" />
          </div>
          {!collapsed && (
            <div className="animate-fade-in-up">
              <h1 className="text-[13px] font-bold text-white leading-tight tracking-tight font-display">
                CI Agent Network
              </h1>
              <p className="text-[10px] text-slate-500 font-medium">Autonomous Intelligence</p>
            </div>
          )}
        </div>
        {/* Mobile close button */}
        <button
          onClick={() => onMobileClose?.()}
          className="lg:hidden text-slate-500 hover:text-slate-200 p-1.5 rounded-lg bg-white/[0.04]"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {/* Main Nav */}
        <div className={`mb-4 ${collapsed ? 'px-0' : 'px-1'}`}>
          {!collapsed && (
            <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-2 px-3">
              Navigation
            </p>
          )}
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`sidebar-link w-full ${isActive ? 'active' : ''} ${
                  collapsed ? 'justify-center px-3' : ''
                }`}
                title={collapsed ? item.label : undefined}
              >
                <Icon className={`w-[18px] h-[18px] ${isActive ? item.color : 'text-slate-500'} transition-colors flex-shrink-0`} />
                {!collapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </div>

        {/* Tools */}
        <div className={`mb-4 ${collapsed ? 'px-0' : 'px-1'}`}>
          {!collapsed && (
            <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-2 px-3">
              Tools
            </p>
          )}
          {toolItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={item.action || (() => navigate(item.path))}
                className={`sidebar-link w-full ${collapsed ? 'justify-center px-3' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <Icon className={`w-[18px] h-[18px] ${item.color} flex-shrink-0`} />
                {!collapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </div>

        {/* Insights Section */}
        <div className={`${collapsed ? 'px-0' : 'px-1'}`}>
          {!collapsed && (
            <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-2 px-3">
              Insights
            </p>
          )}
          {insightItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={() => handleInsightClick(item.label)}
                className={`sidebar-link w-full ${collapsed ? 'justify-center px-3' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <Icon className={`w-[18px] h-[18px] ${item.color} flex-shrink-0`} />
                {!collapsed && <span className="text-slate-300">{item.label}</span>}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Collapse Toggle */}
      <div className="p-3 border-t border-white/[0.04]">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center gap-2 p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] text-slate-400 hover:text-slate-200 transition-all duration-200 text-xs font-medium"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
      {/* Ambient glow at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-indigo-500/[0.02] to-transparent pointer-events-none" />
    </aside>
  </>
);
}

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff, Bot, Shield, Zap, Globe } from 'lucide-react';

/* ────────────────────────────────────────────
   Human Suitcase Character Component
   ──────────────────────────────────────────── */
function SuitcaseCharacter({ isSignup, isSwitching, onSuitcaseOpen }) {
  const [hasArrived, setHasArrived] = useState(false);

  useEffect(() => {
    // 2s walk-in CSS animation + 100ms buffer so the animation is fully
    // settled before the class swap (walking → arrived) happens.
    const timer = setTimeout(() => {
      setHasArrived(true);
      // Trigger card reveal once suitcase finishes opening
      setTimeout(() => {
        onSuitcaseOpen?.(true);
      }, 350);
    }, 2100);
    return () => clearTimeout(timer);
  }, [onSuitcaseOpen]);

  const isOpening = hasArrived && !isSwitching;
  const containerClass = `character-container mt-4 mb-2 ${
    !hasArrived ? 'walking character-walking' : 'arrived character-arrived'
  }`;

  return (
    <div className={containerClass}>
      {/* Human Character Body */}
      <div className={`character-body ${isOpening ? 'character-opening' : ''}`}>
        {/* Hair */}
        <div className="character-hair" />

        {/* Head */}
        <div className="character-head">
          {/* Ears */}
          <div className="character-ear ear-left" />
          <div className="character-ear ear-right" />

          {/* Eyebrows */}
          <div className="character-eyebrow eyebrow-left" />
          <div className="character-eyebrow eyebrow-right" />

          {/* Eyes with pupils */}
          <div className="character-eye eye-left">
            <div className="character-pupil" />
          </div>
          <div className="character-eye eye-right">
            <div className="character-pupil" />
          </div>

          {/* Rosy Cheeks */}
          <div className="character-blush blush-left" />
          <div className="character-blush blush-right" />

          {/* Smile */}
          <div
            className="character-smile"
            style={{ width: isSignup ? '18px' : '16px' }}
          />
        </div>

        {/* Neck */}
        <div className="character-neck" />

        {/* Torso & Suit Jacket */}
        <div className="character-torso">
          {/* White Shirt Collar */}
          <div className="character-collar collar-left" />
          <div className="character-collar collar-right" />

          {/* Tie */}
          <div className={`character-tie ${isSignup ? 'tie-signup' : 'tie-login'}`} />

          {/* Suit Lapels */}
          <div className="character-lapel lapel-left" />
          <div className="character-lapel lapel-right" />

          {/* Arms with Skin Hands */}
          <div className="character-arm-left">
            <div className="character-hand" />
          </div>
          <div className="character-arm-right">
            <div className="character-hand" />
          </div>
        </div>

        {/* Legs with Dress Shoes */}
        <div className="character-legs mt-1">
          <div className="character-leg">
            <div className="character-shoe" />
          </div>
          <div className="character-leg">
            <div className="character-shoe" />
          </div>
        </div>
      </div>

      {/* Suitcase */}
      <div className={`suitcase ${isSwitching ? 'suitcase-switching' : ''}`}>
        <div className={`suitcase-body ${isSignup ? 'signup-case' : 'login-case'} ${isOpening ? 'suitcase-open' : ''}`}>
          <div className="suitcase-handle" />
          <div className="suitcase-lid" style={{ background: isSignup
            ? 'linear-gradient(135deg, #7c3aed, #a855f7)'
            : 'linear-gradient(135deg, #4f46e5, #6366f1)'
          }} />
          <div className="suitcase-lock" />
          <div className="suitcase-glow" />
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────
   Floating Particle Dots
   ──────────────────────────────────────────── */
function ParticleField() {
  const particles = Array.from({ length: 30 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    top: `${Math.random() * 100}%`,
    delay: `${-Math.random() * 20}s`,
    size: Math.random() * 2 + 1,
  }));

  return (
    <div className="particles">
      {particles.map((p) => (
        <div
          key={p.id}
          className="particle"
          style={{
            left: p.left,
            animationDelay: p.delay,
            width: `${p.size}px`,
            height: `${p.size}px`,
          }}
        />
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────
   Typing Effect Hook
   ──────────────────────────────────────────── */
function useTypingEffect(text, speed = 40) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed('');
    setDone(false);
    let i = 0;
    const timer = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        setDone(true);
        clearInterval(timer);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed]);

  return { displayed, done };
}

/* ════════════════════════════════════════════
   LOGIN PAGE
   ════════════════════════════════════════════ */
export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSignup, setIsSignup] = useState(false);
  const [name, setName] = useState('');
  const [isSwitching, setIsSwitching] = useState(false);
  const [isSuitcaseOpen, setIsSuitcaseOpen] = useState(false);

  const { login, signup } = useAuth();
  const navigate = useNavigate();

  const tagline = useTypingEffect('Autonomous agent network for market intelligence', 35);

  const handleToggleMode = () => {
    setIsSwitching(true);
    setIsSuitcaseOpen(false);
    setError('');
    // Close suitcase, wait, then switch mode
    setTimeout(() => {
      setIsSignup(!isSignup);
      // Open new suitcase after a beat
      setTimeout(() => {
        setIsSwitching(false);
        setIsSuitcaseOpen(true);
      }, 400);
    }, 500);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isSignup) {
        await signup(email, password, name);
      } else {
        await login(email, password);
      }
      navigate('/dashboard');
    } catch (err) {
      const msg =
        err.response?.data?.detail || 'Something went wrong. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen mesh-gradient-bg flex flex-col items-center justify-center p-4 relative overflow-hidden noise-overlay">
      {/* Particle constellation background */}
      <ParticleField />

      {/* Ambient grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.02] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      {/* Background ambient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-indigo-600/[0.07] rounded-full blur-[100px] orb-float" />
        <div className="absolute -bottom-32 -left-32 w-[500px] h-[500px] bg-purple-600/[0.06] rounded-full blur-[100px] orb-float-slow" />
        <div className="absolute top-1/3 left-1/4 w-[300px] h-[300px] bg-cyan-500/[0.04] rounded-full blur-[80px] orb-float" />
        <div className="absolute bottom-1/4 right-1/3 w-[250px] h-[250px] bg-rose-500/[0.03] rounded-full blur-[80px] orb-float-slow" />
      </div>

      <div className="w-full max-w-md relative z-10 flex flex-col items-center">
        {/* Brand text at top */}
        <div className="text-center mb-6 animate-fade-in-up">
          <h1 className="text-3xl font-extrabold gradient-text-vivid font-display tracking-tight">
            Competitive Intelligence
          </h1>
          <p className="text-slate-400 text-sm mt-2 h-5 font-medium">
            {tagline.displayed}
            {!tagline.done && <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse" />}
          </p>
        </div>

        {/* Login/Signup Card (reveals when suitcase opens) */}
        <div
          className={`w-full transition-all duration-700 transform ${
            isSuitcaseOpen
              ? 'opacity-100 scale-100 translate-y-0 max-h-[600px] mb-6'
              : 'opacity-0 scale-90 translate-y-8 max-h-0 overflow-hidden pointer-events-none mb-0'
          }`}
        >
          <div className="glass-card rounded-2xl p-8 neon-border shadow-2xl">
            <h2 className="text-xl font-bold text-white mb-1 font-display">
              {isSignup ? 'Create your account' : 'Welcome back'}
            </h2>
            <p className="text-xs text-slate-500 mb-6">
              {isSignup
                ? 'Set up your intelligence command center'
                : 'Sign in to your intelligence dashboard'
              }
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              {isSignup && (
                <div className="animate-fade-in-up">
                  <label htmlFor="name" className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                    Full Name
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required={isSignup}
                    placeholder="John Doe"
                    className="w-full px-4 py-3 bg-white/[0.03] rounded-xl text-white placeholder-slate-600 text-sm input-glow transition-all duration-300"
                  />
                </div>
              )}

              <div className="stagger-item" style={{ '--i': 1 }}>
                <label htmlFor="email" className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@company.com"
                  className="w-full px-4 py-3 bg-white/[0.03] rounded-xl text-white placeholder-slate-600 text-sm input-glow transition-all duration-300"
                />
              </div>

              <div className="stagger-item" style={{ '--i': 2 }}>
                <label htmlFor="password" className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    className="w-full px-4 py-3 pr-11 bg-white/[0.03] rounded-xl text-white placeholder-slate-600 text-sm input-glow transition-all duration-300"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-indigo-400 transition-colors duration-200"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 animate-scale-in">
                  <svg
                    className="w-4 h-4 text-rose-400 flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                  </svg>
                  <span className="text-sm text-rose-300">{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3.5 px-4 btn-gradient rounded-xl text-sm transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {isSignup ? 'Creating account...' : 'Signing in...'}
                  </span>
                ) : isSignup ? (
                  'Create Account'
                ) : (
                  'Sign In'
                )}
              </button>
            </form>

            <div className="mt-6 text-center">
              <button
                onClick={handleToggleMode}
                disabled={isSwitching}
                className="text-sm text-slate-400 hover:text-indigo-400 transition-colors duration-200 disabled:opacity-50"
              >
                {isSignup
                  ? 'Already have an account? Sign in'
                  : "Don't have an account? Sign up"}
              </button>
            </div>
          </div>
        </div>

        {/* Character + Suitcase Animation (positioned below) */}
        <div className="text-center">
          <SuitcaseCharacter
            isSignup={isSignup}
            isSwitching={isSwitching}
            onSuitcaseOpen={(open) => setIsSuitcaseOpen(open)}
          />
        </div>

        {/* Trust Indicators */}
        <div className="mt-6 flex items-center justify-center gap-6 animate-fade-in-up" style={{ animationDelay: '400ms' }}>
          {[
            { icon: Bot, label: 'AI Agents' },
            { icon: Shield, label: 'Encrypted' },
            { icon: Zap, label: 'Real-time' },
            { icon: Globe, label: 'Global Intel' },
          ].map(({ icon: Icon, label }) => (
            <div key={label} className="flex flex-col items-center gap-1 group">
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.04] group-hover:border-indigo-500/20 transition-all duration-300 group-hover:bg-white/[0.05]">
                <Icon className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 transition-colors" />
              </div>
              <span className="text-[10px] text-slate-600 group-hover:text-slate-400 transition-colors">{label}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <p className="mt-4 text-center text-[11px] text-slate-600">
          Powered by autonomous AI agents • Multi-agent orchestration
        </p>
      </div>
    </div>
  );
}
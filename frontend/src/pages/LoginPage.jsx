import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSignup, setIsSignup] = useState(false);
  const [name, setName] = useState('');

  const { login, signup } = useAuth();
  const navigate = useNavigate();

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
    <div className="min-h-screen gradient-bg flex items-center justify-center p-4 relative overflow-hidden">
      {/* Ambient grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      {/* Background decoration — now with ambient drift */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-600/10 rounded-full blur-3xl orb-float" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-600/10 rounded-full blur-3xl orb-float-slow" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl orb-float" />
      </div>

      <div className="w-full max-w-md relative z-10 animate-fade-in-up">
        {/* Logo / Brand */}
        <div className="text-center mb-8 animate-fade-in-up" style={{ '--i': 0 }}>
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl glass glow mb-4 signal-pulse transition-transform duration-300 hover:scale-105 hover:rotate-3">
            <img src="/favicon.svg" alt="CI Agent Network Logo" className="w-10 h-10 drop-shadow-md" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-1 gradient-text">
            Competitive Intelligence
          </h1>
          <p className="text-dark-200 text-sm">
            Autonomous agent network for market analysis
          </p>
        </div>

        {/* Login Card */}
        <div className="glass rounded-2xl p-8 glow animate-scale-in" style={{ animationDelay: '80ms' }}>
          <h2 className="text-xl font-semibold text-white mb-6">
            {isSignup ? 'Create your account' : 'Welcome back'}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {isSignup && (
              <div className="animate-fade-in-up">
                <label
                  htmlFor="name"
                  className="block text-sm font-medium text-dark-100 mb-1.5"
                >
                  Full Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required={isSignup}
                  placeholder="John Doe"
                  className="w-full px-4 py-3 bg-dark-700/50 border border-dark-400/30 rounded-xl text-white placeholder-dark-300 focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
                />
              </div>
            )}

            <div className="stagger-item" style={{ '--i': 1 }}>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-dark-100 mb-1.5"
              >
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className="w-full px-4 py-3 bg-dark-700/50 border border-dark-400/30 rounded-xl text-white placeholder-dark-300 focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
              />
            </div>

            <div className="stagger-item" style={{ '--i': 2 }}>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-dark-100 mb-1.5"
              >
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
                  className="w-full px-4 py-3 pr-11 bg-dark-700/50 border border-dark-400/30 rounded-xl text-white placeholder-dark-300 focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-300 hover:text-primary-400 transition-colors duration-200"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 animate-scale-in">
                <svg
                  className="w-4 h-4 text-red-400 flex-shrink-0"
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
                <span className="text-sm text-red-300">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 text-white font-medium rounded-xl transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-lg shadow-primary-500/20 hover:shadow-primary-500/40"
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
              onClick={() => {
                setIsSignup(!isSignup);
                setError('');
              }}
              className="text-sm text-dark-200 hover:text-primary-400 transition-colors duration-200"
            >
              {isSignup
                ? 'Already have an account? Sign in'
                : "Don't have an account? Sign up"}
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-dark-300">
          Powered by autonomous AI agents
        </p>
      </div>
    </div>
  );
}
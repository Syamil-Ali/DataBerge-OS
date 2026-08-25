import { FormEvent, useEffect, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

type AuthMode = 'login' | 'register';

type LoginPageProps = {
  initialMode?: AuthMode;
  onModeChange?: (mode: AuthMode) => void;
  onBackHome?: () => void;
};

export function LoginPage({ initialMode = 'login', onModeChange, onBackHome }: LoginPageProps) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setMode(initialMode);
    setError('');
  }, [initialMode]);

  const selectMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setError('');
    setConfirmPassword('');
    setShowConfirmPassword(false);
    onModeChange?.(nextMode);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (mode === 'register' && !name.trim()) {
      setError('Enter your name.');
      return;
    }
    if (mode === 'register' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      if (mode === 'register') {
        await register(email, name, password);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      {onBackHome && (
        <button className="auth-back" type="button" onClick={onBackHome} aria-label="Return to Data-Berge homepage">
          <img src="/favicon.svg" alt="" />
          <span>Data-Berge</span>
        </button>
      )}
      <aside className="auth-visual" aria-hidden="true">
        <img src="/data-berge-hero-wide.webp" alt="" />
        <div className="auth-visual-shade" />
        <div className="auth-visual-copy">
          <span>Data-Berge</span>
          <h2>The deeper story starts with your data.</h2>
          <p>Prepare messy workbooks, uncover relationships, and move from raw files to useful answers.</p>
        </div>
      </aside>
      <div className={`auth-card ${mode === 'register' ? 'auth-card-register' : ''}`}>
        <div className="auth-intro">
          <h1>{mode === 'login' ? 'Welcome back.' : 'Create your workspace.'}</h1>
          <p>{mode === 'login' ? 'Sign in to continue exploring your data.' : 'Start turning your files into clear, useful answers.'}</p>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => selectMode('login')}
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => selectMode('register')}
          >
            Create Account
          </button>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && (
            <label>
              <span>Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </label>
          )}
          <label>
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </label>
          <label>
            <span>Password</span>
            <div className="auth-password-field">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 12 characters with a number"
                minLength={12}
                required
              />
              <button
                type="button"
                className="auth-password-toggle"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          {mode === 'register' && (
            <label>
              <span>Re-enter password</span>
              <div className="auth-password-field">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Enter your password again"
                  minLength={12}
                  required
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowConfirmPassword((visible) => !visible)}
                  aria-label={showConfirmPassword ? 'Hide confirmation password' : 'Show confirmation password'}
                  aria-pressed={showConfirmPassword}
                >
                  {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>
          )}
          <button type="submit" className="auth-submit" disabled={busy}>
            {busy ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

      </div>
    </div>
  );
}

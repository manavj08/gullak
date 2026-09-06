import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import GullakMark from '../components/GullakMark';
import { Button, Field, Input, Banner } from '../components/ui';
import './AuthPages.css';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(form.email, form.password);
      navigate('/home');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Could not sign in. Check your email and password.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <GullakMark size={40} />
          <h1>Gullak</h1>
        </div>
        <p className="auth-tagline">Track what you spend, save what you can.</p>

        {error && <Banner tone="warn">{error}</Banner>}

        <form onSubmit={handleSubmit} noValidate>
          <Field label="Email" htmlFor="email">
            <Input
              id="email" type="email" required autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field label="Password" htmlFor="password">
            <Input
              id="password" type="password" required autoComplete="current-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </Field>
          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <div className="auth-links">
          <Link to="/forgot-password">Forgot password?</Link>
          <Link to="/register">Create an account</Link>
        </div>

        <div className="auth-demo-hint">
          <strong>Demo login:</strong> demo@gullak.app / Demo@12345
        </div>
      </div>
    </div>
  );
}

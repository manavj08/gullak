import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import GullakMark from '../components/GullakMark';
import { Button, Field, Input, Banner } from '../components/ui';
import './AuthPages.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', email: '', phone: '', password: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await register(form);
      navigate('/mpin-setup');
    } catch (err) {
      const data = err.response?.data;
      const firstError = data && typeof data === 'object' ? Object.values(data)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || 'Could not create your account.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <GullakMark size={40} />
          <h1>Create account</h1>
        </div>
        <p className="auth-tagline">Start building your Gullak today.</p>

        {error && <Banner tone="warn">{error}</Banner>}

        <form onSubmit={handleSubmit} noValidate>
          <Field label="Full name / username" htmlFor="username">
            <Input id="username" required value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </Field>
          <Field label="Email" htmlFor="email">
            <Input id="email" type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <Field label="Phone (optional)" htmlFor="phone" hint="e.g. +919876543210">
            <Input id="phone" value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          <Field label="Password" htmlFor="password" hint="At least 8 characters.">
            <Input id="password" type="password" required value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field>
          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>

        <div className="auth-links">
          <span />
          <Link to="/login">Already have an account?</Link>
        </div>
      </div>
    </div>
  );
}

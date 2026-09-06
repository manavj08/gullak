import { useState } from 'react';
import { Link } from 'react-router-dom';
import { requestPasswordReset } from '../api/endpoints';
import GullakMark from '../components/GullakMark';
import { Banner, Button, Field, Input } from '../components/ui';
import './AuthPages.css';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand"><GullakMark size={40} /><h1>Reset password</h1></div>
        <p className="auth-tagline">We'll help you get back into your account.</p>

        {sent ? (
          <Banner tone="success">
            If that email exists, we've sent a reset link to <strong>{email}</strong>. It expires in an hour —
            check your inbox (and spam folder) for an email from Gullak.
          </Banner>
        ) : (
          <form onSubmit={handleSubmit}>
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Button type="submit" size="lg" disabled={submitting}>
              {submitting ? 'Sending…' : 'Send reset link'}
            </Button>
          </form>
        )}

        <div className="auth-links">
          <Link to="/login">Back to sign in</Link>
          <span />
        </div>
      </div>
    </div>
  );
}

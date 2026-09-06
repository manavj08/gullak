import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { confirmPasswordReset } from '../api/endpoints';
import GullakMark from '../components/GullakMark';
import { Banner, Button, Field, Input } from '../components/ui';
import './AuthPages.css';

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await confirmPasswordReset({ uid, token, new_password: newPassword });
      setDone(true);
    } catch (err) {
      const data = err.response?.data;
      const firstError = data && typeof data === 'object' ? Object.values(data)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || 'Could not reset password.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!uid || !token) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <Banner tone="warn">This reset link is invalid or incomplete.</Banner>
          <Link to="/forgot-password">Request a new link</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand"><GullakMark size={40} /><h1>Choose new password</h1></div>

        {error && <Banner tone="warn">{error}</Banner>}

        {done ? (
          <>
            <Banner tone="success">Password reset successfully.</Banner>
            <Button size="lg" onClick={() => navigate('/login')}>Go to sign in</Button>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <Field label="New password" htmlFor="new_password" hint="At least 8 characters.">
              <Input
                id="new_password" type="password" required
                value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" size="lg" disabled={submitting}>
              {submitting ? 'Saving…' : 'Reset password'}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

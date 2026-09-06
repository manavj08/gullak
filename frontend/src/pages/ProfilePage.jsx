import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { updateMe, changePassword, setMpin } from '../api/endpoints';
import { Card, Field, Input, Button, Banner } from '../components/ui';
import GullakMark from '../components/GullakMark';
import './ProfilePage.css';

export default function ProfilePage() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="profile-page">
      <div className="profile-header">
        <GullakMark size={44} />
        <div>
          <p className="page-subtitle" style={{ marginBottom: 2 }}>{user.username}</p>
          <p className="muted">{user.email}</p>
        </div>
      </div>

      <ProfileForm user={user} onSaved={refreshUser} />
      <PasswordForm />
      <MpinForm user={user} onSaved={refreshUser} />

      <Button
        variant="secondary" size="lg"
        onClick={async () => { await logout(); navigate('/login'); }}
        style={{ marginTop: 8 }}
      >
        Log out
      </Button>
    </div>
  );
}

function ProfileForm({ user, onSaved }) {
  const [phone, setPhone] = useState(user.phone || '');
  const [upiId, setUpiId] = useState(user.upi_id || '');
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSaved(false); setSubmitting(true);
    try {
      await updateMe({ phone, upi_id: upiId });
      await onSaved();
      setSaved(true);
    } catch (err) {
      setError(err.response?.data?.phone?.[0] || err.response?.data?.upi_id?.[0] || 'Could not update profile.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="profile-section">
      <h2>Profile</h2>
      {error && <Banner tone="warn">{error}</Banner>}
      {saved && <Banner tone="success">Profile updated.</Banner>}
      <form onSubmit={handleSubmit}>
        <Field label="Phone" htmlFor="phone">
          <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </Field>
        <Field label="UPI ID" htmlFor="upi_id" hint="Used to build your Pay via UPI link in group settlements, e.g. yourname@okhdfcbank.">
          <Input id="upi_id" value={upiId} onChange={(e) => setUpiId(e.target.value)} placeholder="yourname@bank" />
        </Field>
        <Button type="submit" disabled={submitting}>{submitting ? 'Saving…' : 'Save changes'}</Button>
      </form>
    </Card>
  );
}

function PasswordForm() {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSaved(false); setSubmitting(true);
    try {
      await changePassword({ old_password: oldPassword, new_password: newPassword });
      setOldPassword(''); setNewPassword('');
      setSaved(true);
    } catch (err) {
      const data = err.response?.data;
      const firstError = data && typeof data === 'object' ? Object.values(data)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || 'Could not change password.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="profile-section">
      <h2>Change password</h2>
      {error && <Banner tone="warn">{error}</Banner>}
      {saved && <Banner tone="success">Password changed.</Banner>}
      <form onSubmit={handleSubmit}>
        <Field label="Current password" htmlFor="old_password">
          <Input id="old_password" type="password" required value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)} />
        </Field>
        <Field label="New password" htmlFor="new_password" hint="At least 8 characters.">
          <Input id="new_password" type="password" required value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)} />
        </Field>
        <Button type="submit" disabled={submitting}>{submitting ? 'Saving…' : 'Change password'}</Button>
      </form>
    </Card>
  );
}

function MpinForm({ user, onSaved }) {
  const [mpin, setMpinValue] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSaved(false); setSubmitting(true);
    try {
      await setMpin(mpin);
      await onSaved();
      setMpinValue('');
      setSaved(true);
    } catch (err) {
      setError(err.response?.data?.mpin?.[0] || 'Could not update MPIN.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="profile-section">
      <h2>{user.has_mpin ? 'Update MPIN' : 'Set up MPIN'}</h2>
      <p className="muted">Used for quick unlock instead of your password.</p>
      {error && <Banner tone="warn">{error}</Banner>}
      {saved && <Banner tone="success">MPIN saved.</Banner>}
      <form onSubmit={handleSubmit}>
        <Field label="New MPIN (4-6 digits)" htmlFor="new_mpin">
          <Input id="new_mpin" type="password" inputMode="numeric" pattern="\d{4,6}" required
            value={mpin} onChange={(e) => setMpinValue(e.target.value.replace(/\D/g, ''))} maxLength={6} />
        </Field>
        <Button type="submit" disabled={submitting || mpin.length < 4}>
          {submitting ? 'Saving…' : 'Save MPIN'}
        </Button>
      </form>
    </Card>
  );
}

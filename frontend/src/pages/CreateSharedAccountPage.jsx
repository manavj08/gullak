import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createSharedPair, createSharedGroup, sendGroupInvite } from '../api/endpoints';
import { Card, Field, Input, Button, Banner } from '../components/ui';
import './CreateSharedAccountPage.css';

export default function CreateSharedAccountPage() {
  const navigate = useNavigate();
  const [kind, setKind] = useState(null); // 'pair' | 'group'
  const [createdAccount, setCreatedAccount] = useState(null);
  const [form, setForm] = useState({ name: '', occasion_name: '', occasion_date: '', reminder_enabled: false });
  const [inviteUsername, setInviteUsername] = useState('');
  const [error, setError] = useState('');
  const [inviteMessage, setInviteMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      let account;
      if (kind === 'pair') {
        const { data } = await createSharedPair(form.name);
        account = data;
      } else {
        const { data } = await createSharedGroup({
          name: form.name,
          occasion_name: form.occasion_name || form.name,
          occasion_date: form.occasion_date || null,
          reminder_enabled: form.reminder_enabled,
        });
        account = data;
      }
      setCreatedAccount(account);
    } catch (err) {
      setError(err.response?.data?.name?.[0] || err.response?.data?.detail || 'Could not create the account.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    setError('');
    setInviteMessage('');
    setSubmitting(true);
    try {
      await sendGroupInvite(createdAccount.id, inviteUsername.trim());
      setInviteMessage(`Invite sent to ${inviteUsername.trim()}.`);
      setInviteUsername('');
    } catch (err) {
      setError(err.response?.data?.invited_username || 'Could not send invite.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!kind) {
    return (
      <div>
        <p className="page-subtitle">Choose a type to get started.</p>
        <div className="kind-grid">
          <Card className="kind-card" onClick={() => setKind('pair')}>
            <h3>Relationship</h3>
            <p>Just the two of you \u2014 no admin, equal partners.</p>
          </Card>
          <Card className="kind-card" onClick={() => setKind('group')}>
            <h3>Family &amp; Friends group</h3>
            <p>Pool money for a trip, gift, or event with an admin to manage members.</p>
          </Card>
        </div>
      </div>
    );
  }

  if (createdAccount) {
    return (
      <div>
        <p className="page-subtitle">{createdAccount.name}</p>
        <Banner tone="success">Account created. Invite people to join by their username.</Banner>
        <Card>
          <form onSubmit={handleInvite}>
            <Field label="Username">
              <Input
                value={inviteUsername}
                onChange={(e) => setInviteUsername(e.target.value)}
                placeholder="e.g. rahul_k"
                required
              />
            </Field>
            {error && <Banner tone="warn">{error}</Banner>}
            {inviteMessage && <Banner tone="success">{inviteMessage}</Banner>}
            <Button type="submit" disabled={submitting}>{submitting ? 'Sending…' : 'Send invite'}</Button>
          </form>
        </Card>
        <div className="create-shared__done">
          <Button variant="secondary" onClick={() => navigate(`/shared-accounts/${createdAccount.id}`)}>
            Go to account →
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <p className="page-subtitle">{kind === 'pair' ? 'Relationship account' : 'Group account'}</p>
      <Card>
        <form onSubmit={handleCreate}>
          <Field label="Account name">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={kind === 'pair' ? 'e.g. Our Fund' : 'e.g. Goa Trip'}
              required
            />
          </Field>

          {kind === 'group' && (
            <>
              <Field label="Occasion name" hint="What is this group saving for?">
                <Input
                  value={form.occasion_name}
                  onChange={(e) => setForm({ ...form, occasion_name: e.target.value })}
                  placeholder="e.g. Goa Trip Fund"
                />
              </Field>
              <Field label="Occasion date (optional)">
                <Input
                  type="date"
                  value={form.occasion_date}
                  onChange={(e) => setForm({ ...form, occasion_date: e.target.value })}
                />
              </Field>
              <label className="create-shared__checkbox">
                <input
                  type="checkbox"
                  checked={form.reminder_enabled}
                  onChange={(e) => setForm({ ...form, reminder_enabled: e.target.checked })}
                />
                Remind the group as the occasion date approaches
              </label>
            </>
          )}

          {error && <Banner tone="warn">{error}</Banner>}
          <Button type="submit" disabled={submitting}>{submitting ? 'Creating…' : 'Create account'}</Button>
        </form>
      </Card>
    </div>
  );
}

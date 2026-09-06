import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  fetchSharedAccountDetail, fetchAccounts, contributeToShared, sharedEmergencyUnblock,
  sendGroupInvite, leaveSharedAccount, removeGroupMember, requestAdminTransfer,
} from '../api/endpoints';
import { formatMoney, toApiAmount } from '../utils/money';
import { newClientRequestId } from '../utils/idempotency';
import { useAuth } from '../context/AuthContext';
import { Card, Field, Input, Select, Button, Banner, Spinner } from '../components/ui';
import './SharedAccountDetailPage.css';

export default function SharedAccountDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [myAccounts, setMyAccounts] = useState([]);
  const [mode, setMode] = useState(null); // 'contribute' | 'unblock' | 'invite' | 'admin'
  const [amount, setAmount] = useState('');
  const [sourceAccountId, setSourceAccountId] = useState('');
  const [inviteUsername, setInviteUsername] = useState('');
  const [transferUsername, setTransferUsername] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    const { data } = await fetchSharedAccountDetail(id);
    setDetail(data);
  };

  const loadMyAccounts = async () => {
    const { data } = await fetchAccounts({ is_archived: false });
    const spendable = (data.results ?? data).filter((a) => a.is_block_capable);
    setMyAccounts(spendable);
    if (spendable.length > 0 && !sourceAccountId) setSourceAccountId(String(spendable[0].id));
  };

  useEffect(() => { load(); loadMyAccounts(); }, [id]);

  if (!detail) return <Spinner label="Loading account" />;

  const { account, members, visibility, occasion, common_goals: commonGoals } = detail;
  const myMembership = members.find((m) => m.user.id === user.id);
  const isAdmin = myMembership?.role === 'admin';
  const isGroup = account.owner_type === 'shared_group';
  const pooledTotal = Number(account.block_balance || 0);

  const resetFlow = () => { setMode(null); setAmount(''); setError(''); setMessage(''); };

  const handleContribute = async (e) => {
    e.preventDefault();
    setError(''); setSubmitting(true);
    try {
      await contributeToShared(id, {
        from_account: Number(sourceAccountId), amount: toApiAmount(amount), client_request_id: newClientRequestId(),
      });
      await Promise.all([load(), loadMyAccounts()]);
      resetFlow();
    } catch (err) {
      setError(err.response?.data?.amount || err.response?.data?.detail || 'Could not contribute.');
    } finally { setSubmitting(false); }
  };

  const handleUnblock = async (e) => {
    e.preventDefault();
    setError(''); setSubmitting(true);
    try {
      await sharedEmergencyUnblock(id, {
        to_account: Number(sourceAccountId), amount: toApiAmount(amount), client_request_id: newClientRequestId(),
      });
      await Promise.all([load(), loadMyAccounts()]);
      resetFlow();
    } catch (err) {
      setError(err.response?.data?.amount || err.response?.data?.detail || 'Could not unblock.');
    } finally { setSubmitting(false); }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    setError(''); setMessage(''); setSubmitting(true);
    try {
      await sendGroupInvite(id, inviteUsername.trim());
      setMessage(`Invite sent to ${inviteUsername.trim()}.`);
      setInviteUsername('');
    } catch (err) {
      setError(err.response?.data?.invited_username || 'Could not send invite.');
    } finally { setSubmitting(false); }
  };

  const handleTransferAdmin = async (e) => {
    e.preventDefault();
    setError(''); setMessage(''); setSubmitting(true);
    try {
      await requestAdminTransfer(id, transferUsername.trim());
      setMessage(`Admin request sent to ${transferUsername.trim()}. They must accept before it takes effect.`);
      setTransferUsername('');
    } catch (err) {
      setError(err.response?.data?.target_username || err.response?.data?.detail || 'Could not send request.');
    } finally { setSubmitting(false); }
  };

  const handleLeave = async () => {
    if (!window.confirm('Leave this shared account? Your past contribution stays in the pooled total.')) return;
    try {
      await leaveSharedAccount(id);
      navigate('/shared-accounts');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not leave the account.');
    }
  };

  const handleRemove = async (username) => {
    if (!window.confirm(`Remove ${username} from this account?`)) return;
    try {
      await removeGroupMember(id, username);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not remove member.');
    }
  };

  return (
    <div>
      <p className="page-subtitle" style={{ marginBottom: 4 }}>{account.name}</p>
      <p className="shared-detail__type">
        {isGroup ? 'Family & Friends group' : 'Relationship account'}
        {isGroup && occasion?.occasion_date && ` · ${occasion.occasion_date}`}
      </p>

      <Card className="shared-detail__hero">
        <p className="shared-detail__label">Pooled total</p>
        <p className="shared-detail__amount">{formatMoney(pooledTotal)}</p>
        <div className="shared-detail__breakdown">
          <div>
            <span className="dot dot--mine" /> You contributed
            <strong>{formatMoney(Number(visibility.own_contribution))}</strong>
          </div>
          <div>
            <span className="dot dot--others" /> Everyone else (combined)
            <strong>{formatMoney(Number(visibility.others_aggregate))}</strong>
          </div>
        </div>
        <p className="shared-detail__hint">
          Other members' individual contributions are never shown separately — only this combined total.
        </p>
      </Card>

      {error && <Banner tone="warn">{error}</Banner>}
      {message && <Banner tone="success">{message}</Banner>}

      {!mode && (
        <div className="shared-detail__actions">
          <Button onClick={() => setMode('contribute')}>Contribute</Button>
          <Button variant="secondary" onClick={() => setMode('unblock')}>Emergency unblock (my share)</Button>
          <Button variant="secondary" onClick={() => setMode('invite')}>Invite someone</Button>
        </div>
      )}

      {isGroup && (
        <div className="shared-detail__actions">
          <Link to={`/shared-accounts/${id}/expenses`} className="shared-detail__expense-link">
            <Button variant="secondary">Group expenses & settlements</Button>
          </Link>
        </div>
      )}

      {mode === 'contribute' && (
        <Card>
          <form onSubmit={handleContribute}>
            <Field label="From your account">
              <Select value={sourceAccountId} onChange={(e) => setSourceAccountId(e.target.value)}>
                {myAccounts.map((a) => <option key={a.id} value={a.id}>{a.name} ({formatMoney(Number(a.unblock_balance))})</option>)}
              </Select>
            </Field>
            <Field label="Amount">
              <Input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required />
            </Field>
            <div className="shared-detail__form-actions">
              <Button type="submit" disabled={submitting}>{submitting ? 'Contributing…' : 'Contribute'}</Button>
              <Button type="button" variant="secondary" onClick={resetFlow}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {mode === 'unblock' && (
        <Card>
          <Banner tone="info">You can only unblock your own contributed portion (₹{Number(visibility.own_contribution).toFixed(2)} available).</Banner>
          <form onSubmit={handleUnblock}>
            <Field label="To your account">
              <Select value={sourceAccountId} onChange={(e) => setSourceAccountId(e.target.value)}>
                {myAccounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </Select>
            </Field>
            <Field label="Amount">
              <Input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required />
            </Field>
            <div className="shared-detail__form-actions">
              <Button type="submit" disabled={submitting}>{submitting ? 'Unblocking…' : 'Unblock'}</Button>
              <Button type="button" variant="secondary" onClick={resetFlow}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {mode === 'invite' && (
        <Card>
          <form onSubmit={handleInvite}>
            <Field label="Username">
              <Input value={inviteUsername} onChange={(e) => setInviteUsername(e.target.value)} required />
            </Field>
            <div className="shared-detail__form-actions">
              <Button type="submit" disabled={submitting}>{submitting ? 'Sending…' : 'Send invite'}</Button>
              <Button type="button" variant="secondary" onClick={resetFlow}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {commonGoals && commonGoals.length > 0 && (
        <>
          <h2 className="shared-detail__section-title">Common goals</h2>
          <div className="member-list">
            {commonGoals.map((g) => {
              const percent = Number(g.target_amount) > 0
                ? Math.min(100, Math.round((Number(g.allocated_amount) / Number(g.target_amount)) * 100))
                : 0;
              return (
                <Link key={g.id} to={`/goals/shared/${g.id}`} className="common-goal-link">
                  <Card className="member-row">
                    <div>
                      <p className="member-row__name">{g.name}{g.is_achieved && ' 🎉'}</p>
                      <p className="member-row__role">{formatMoney(Number(g.allocated_amount))} of {formatMoney(Number(g.target_amount))} · {percent}%</p>
                    </div>
                    <span className="common-goal-link__arrow">→</span>
                  </Card>
                </Link>
              );
            })}
          </div>
        </>
      )}

      <h2 className="shared-detail__section-title">Members</h2>
      <div className="member-list">
        {members.map((m) => (
          <Card key={m.id} className="member-row">
            <div>
              <p className="member-row__name">{m.user.username}{m.user.id === user.id && ' (you)'}</p>
              {isGroup && <p className="member-row__role">{m.role === 'admin' ? 'Admin' : 'Member'}</p>}
            </div>
            {isGroup && isAdmin && m.user.id !== user.id && (
              <Button size="sm" variant="secondary" onClick={() => handleRemove(m.user.username)}>Remove</Button>
            )}
          </Card>
        ))}
      </div>

      {isGroup && isAdmin && (
        <Card className="shared-detail__admin-card">
          <h3>Transfer admin role</h3>
          <form onSubmit={handleTransferAdmin}>
            <Field label="New admin's username" hint="They must accept before the transfer takes effect.">
              <Input value={transferUsername} onChange={(e) => setTransferUsername(e.target.value)} required />
            </Field>
            <Button type="submit" size="sm" disabled={submitting}>{submitting ? 'Sending…' : 'Request transfer'}</Button>
          </form>
        </Card>
      )}

      <div className="shared-detail__leave">
        <Button variant="secondary" onClick={handleLeave}>Leave this account</Button>
      </div>
    </div>
  );
}

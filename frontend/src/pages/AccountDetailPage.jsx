import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  fetchAccount, blockFunds, emergencyUnblock, fetchTransactions, deleteAccount, fetchAccounts,
} from '../api/endpoints';
import { formatMoney, toApiAmount, categoryLabel, accountCategoryLabel } from '../utils/money';
import { newClientRequestId } from '../utils/idempotency';
import GullakMark from '../components/GullakMark';
import { Card, Spinner, Button, Field, Input, Select, Banner } from '../components/ui';
import './AccountDetailPage.css';

export default function AccountDetailPage() {
  const { id } = useParams();
  const [account, setAccount] = useState(null);

  const load = async () => {
    const { data } = await fetchAccount(id);
    setAccount(data);
  };

  useEffect(() => { load(); }, [id]);

  if (!account) return <Spinner label="Loading account" />;

  return account.category === 'gullak'
    ? <GullakDetail account={account} onChange={load} />
    : <RegularAccountDetail account={account} onChange={load} />;
}

// ---------------------------------------------------------------------------
// Gullak account: its own dedicated view — total, block-in from any account,
// emergency-unblock out, and its full block/unblock history.
// ---------------------------------------------------------------------------
function GullakDetail({ account, onChange }) {
  const [otherAccounts, setOtherAccounts] = useState([]);
  const [txns, setTxns] = useState([]);
  const [mode, setMode] = useState(null); // 'block' | 'unblock-confirm' | 'unblock-reason'
  const [sourceAccountId, setSourceAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadExtras = async () => {
    const [accRes, txnRes] = await Promise.all([
      fetchAccounts({ is_archived: false }),
      fetchTransactions({ account: account.id, include_gullak: 'true', ordering: '-timestamp' }),
    ]);
    const spendable = (accRes.data.results ?? accRes.data).filter((a) => a.is_block_capable);
    setOtherAccounts(spendable);
    if (spendable.length > 0 && !sourceAccountId) setSourceAccountId(String(spendable[0].id));
    setTxns((txnRes.data.results ?? txnRes.data).slice(0, 15));
  };

  useEffect(() => { loadExtras(); }, [account.id]);

  const resetFlow = () => { setMode(null); setAmount(''); setError(''); };

  const sourceAccount = otherAccounts.find((a) => String(a.id) === String(sourceAccountId));

  const handleBlock = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await blockFunds(sourceAccountId, toApiAmount(amount), newClientRequestId());
      await Promise.all([onChange(), loadExtras()]);
      resetFlow();
    } catch (err) {
      setError(err.response?.data?.amount?.[0] || err.response?.data?.detail || 'Could not block funds.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEmergencyUnblock = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await emergencyUnblock(sourceAccountId, toApiAmount(amount), newClientRequestId());
      await Promise.all([onChange(), loadExtras()]);
      resetFlow();
    } catch (err) {
      setError(err.response?.data?.amount?.[0] || err.response?.data?.detail || 'Could not unblock funds.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="account-detail">
      <div className="account-detail__head">
        <div className="gullak-detail-title">
          <GullakMark size={28} />
          <span className="gullak-detail-title__text">Gullak</span>
        </div>
      </div>

      <Card className="gullak-detail-hero">
        <p className="gullak-detail-hero__label">Total in Gullak</p>
        <p className="gullak-detail-hero__amount">{formatMoney(account.unblock_balance)}</p>
      </Card>

      {!mode && (
        <div className="action-row">
          <Button variant="success" onClick={() => setMode('block')} disabled={otherAccounts.length === 0}>
            Block funds in
          </Button>
          <Button variant="danger" onClick={() => setMode('unblock-confirm')}>Emergency unblock</Button>
        </div>
      )}

      {otherAccounts.length === 0 && !mode && (
        <p className="muted" style={{ marginTop: 8 }}>
          You need a Daily Transaction or Savings account before you can block funds into Gullak.
        </p>
      )}

      {mode === 'block' && (
        <Card className="action-panel">
          <h3>Block funds into Gullak</h3>
          <p className="muted">Move money from an account's available balance into your Gullak.</p>
          {error && <Banner tone="warn">{error}</Banner>}
          <form onSubmit={handleBlock}>
            <Field label="From account" htmlFor="source_account">
              <Select id="source_account" value={sourceAccountId} onChange={(e) => setSourceAccountId(e.target.value)}>
                {otherAccounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} ({accountCategoryLabel(a.category)})</option>
                ))}
              </Select>
            </Field>
            {sourceAccount && (
              <div className="account-balance-hint">
                <span>Available: <strong>{formatMoney(sourceAccount.unblock_balance)}</strong></span>
              </div>
            )}
            <Field label="Amount (₹)" htmlFor="block_amount">
              <Input id="block_amount" type="number" min="0.01" step="0.01" required
                value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
            </Field>
            <div className="action-row">
              <Button type="submit" variant="success" disabled={submitting}>
                {submitting ? 'Blocking…' : 'Confirm block'}
              </Button>
              <Button type="button" variant="secondary" onClick={resetFlow}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {mode === 'unblock-confirm' && (
        <Card className="action-panel action-panel--warn">
          <h3>Emergency unblock</h3>
          <p>
            This money was set aside as savings. Unblocking it moves it back to an account's spendable balance —
            think about whether you really need to right now. If this dips into money already allocated to a goal,
            you'll be asked to choose which goal it comes from next time you visit Home.
          </p>
          <div className="action-row">
            <Button variant="danger" onClick={() => setMode('unblock-reason')}>Continue anyway</Button>
            <Button variant="secondary" onClick={resetFlow}>Never mind, keep it saved</Button>
          </div>
        </Card>
      )}

      {mode === 'unblock-reason' && (
        <Card className="action-panel action-panel--warn">
          <h3>Unblock to which account, how much?</h3>
          {error && <Banner tone="warn">{error}</Banner>}
          <form onSubmit={handleEmergencyUnblock}>
            <Field label="To account" htmlFor="dest_account">
              <Select id="dest_account" value={sourceAccountId} onChange={(e) => setSourceAccountId(e.target.value)}>
                {otherAccounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} ({accountCategoryLabel(a.category)})</option>
                ))}
              </Select>
            </Field>
            <Field label="Amount (₹)" htmlFor="unblock_amount">
              <Input id="unblock_amount" type="number" min="0.01" step="0.01" required
                value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
            </Field>
            <div className="action-row">
              <Button type="submit" variant="danger" disabled={submitting || !amount}>
                {submitting ? 'Unblocking…' : 'Unblock funds'}
              </Button>
              <Button type="button" variant="secondary" onClick={resetFlow}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      <section className="home-section">
        <div className="home-section__head"><h2>Gullak history</h2></div>
        {txns.length === 0 ? (
          <Card><p className="muted">No activity in your Gullak yet.</p></Card>
        ) : (
          <Card className="txn-list">
            {txns.map((t) => (
              <div className="txn-row" key={t.id}>
                <div>
                  <p className="txn-row__note">{t.note || (t.type === 'gullak_block' ? 'Blocked in' : 'Unblocked out')}</p>
                  <p className="txn-row__meta">{new Date(t.timestamp).toLocaleDateString()}</p>
                </div>
                <p className={`txn-row__amount txn-row__amount--${t.type === 'gullak_block' && t.account === account.id ? 'positive' : t.type === 'gullak_unblock' && t.account === account.id ? 'negative' : 'neutral'}`}>
                  {formatMoney(t.amount)}
                </p>
              </div>
            ))}
          </Card>
        )}
      </section>

      <p className="gullak-detail-footer-note">
        Want to see how your goals are funded from this? <Link to="/goals">Go to Goals</Link>
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Regular (non-Gullak) account detail: block-out to Gullak, view balances/history.
// ---------------------------------------------------------------------------
function RegularAccountDetail({ account, onChange }) {
  const navigate = useNavigate();
  const [txns, setTxns] = useState([]);
  const [mode, setMode] = useState(null); // 'block' | 'unblock-confirm' | 'unblock-reason'
  const [amount, setAmount] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadTxns = async () => {
    const { data } = await fetchTransactions({ account: account.id, ordering: '-timestamp' });
    setTxns((data.results ?? data).slice(0, 10));
  };

  useEffect(() => { loadTxns(); }, [account.id]);

  const resetFlow = () => { setMode(null); setAmount(''); setError(''); };

  const handleBlock = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await blockFunds(account.id, toApiAmount(amount), newClientRequestId());
      await Promise.all([onChange(), loadTxns()]);
      resetFlow();
    } catch (err) {
      setError(err.response?.data?.amount?.[0] || err.response?.data?.detail || 'Could not block funds.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEmergencyUnblock = async () => {
    setError('');
    setSubmitting(true);
    try {
      await emergencyUnblock(account.id, toApiAmount(amount), newClientRequestId());
      await Promise.all([onChange(), loadTxns()]);
      resetFlow();
    } catch (err) {
      setError(err.response?.data?.amount?.[0] || err.response?.data?.detail || 'Could not unblock funds.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Archive "${account.name}"? You can still see its history, but it will leave your active accounts.`)) return;
    await deleteAccount(account.id);
    navigate('/accounts');
  };

  return (
    <div className="account-detail">
      <div className="account-detail__head">
        <div>
          <p className="account-detail__cat">{accountCategoryLabel(account.category)} · {account.account_type}</p>
          <p className="account-detail__name">{account.name}</p>
        </div>
      </div>

      {account.is_block_capable ? (
        <Card className="balance-card balance-card--unblock">
          <p className="balance-card__label">Available to spend</p>
          <p className="balance-card__amount">{formatMoney(account.unblock_balance)}</p>
        </Card>
      ) : (
        <Card className="balance-card">
          {account.category === 'revenue_generation' && (
            <>
              <p className="balance-card__label">Current value</p>
              <p className="balance-card__amount">{formatMoney(account.current_value)}</p>
              <p className="muted">Principal: {formatMoney(account.principal)}</p>
            </>
          )}
          {account.category === 'loan_debt' && (
            <>
              <p className="balance-card__label">Amount owed</p>
              <p className="balance-card__amount" style={{ color: 'var(--color-warn)' }}>
                {formatMoney(account.amount_owed)}
              </p>
              {account.due_date && <p className="muted">Due {account.due_date}</p>}
            </>
          )}
        </Card>
      )}

      {account.is_block_capable && !mode && (
        <div className="action-row">
          <Button variant="success" onClick={() => setMode('block')}>Block into Gullak</Button>
          <Button variant="danger" onClick={() => setMode('unblock-confirm')}>Emergency unblock</Button>
        </div>
      )}

      {mode === 'block' && (
        <Card className="action-panel">
          <h3>Block funds into Gullak</h3>
          <p className="muted">Move money from this account's spendable balance into your Gullak.</p>
          {error && <Banner tone="warn">{error}</Banner>}
          <form onSubmit={handleBlock}>
            <Field label="Amount (₹)" htmlFor="block_amount">
              <Input id="block_amount" type="number" min="0.01" step="0.01" required
                value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
            </Field>
            <div className="action-row">
              <Button type="submit" variant="success" disabled={submitting}>
                {submitting ? 'Blocking…' : 'Confirm block'}
              </Button>
              <Button type="button" variant="secondary" onClick={resetFlow}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {mode === 'unblock-confirm' && (
        <Card className="action-panel action-panel--warn">
          <h3>Emergency unblock</h3>
          <p>
            This account has no funds in Gullak of its own to unblock directly — emergency unblocks
            pull from your overall Gullak total and land back here.
          </p>
          <div className="action-row">
            <Button variant="danger" onClick={() => setMode('unblock-reason')}>Continue anyway</Button>
            <Button variant="secondary" onClick={resetFlow}>Never mind</Button>
          </div>
        </Card>
      )}

      {mode === 'unblock-reason' && (
        <Card className="action-panel action-panel--warn">
          <h3>How much do you need?</h3>
          {error && <Banner tone="warn">{error}</Banner>}
          <Field label="Amount (₹)" htmlFor="unblock_amount">
            <Input id="unblock_amount" type="number" min="0.01" step="0.01" required
              value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          </Field>
          <div className="action-row">
            <Button variant="danger" onClick={handleEmergencyUnblock} disabled={submitting || !amount}>
              {submitting ? 'Unblocking…' : 'Unblock funds'}
            </Button>
            <Button variant="secondary" onClick={resetFlow}>Cancel</Button>
          </div>
        </Card>
      )}

      <section className="home-section">
        <div className="home-section__head"><h2>Recent activity</h2></div>
        {txns.length === 0 ? (
          <Card><p className="muted">No transactions on this account yet.</p></Card>
        ) : (
          <Card className="txn-list">
            {txns.map((t) => (
              <div className="txn-row" key={t.id}>
                <div>
                  <p className="txn-row__note">{t.note || categoryLabel(t.category)}</p>
                  <p className="txn-row__meta">{new Date(t.timestamp).toLocaleDateString()}</p>
                </div>
                <p className="txn-row__amount">{formatMoney(t.amount)}</p>
              </div>
            ))}
          </Card>
        )}
      </section>

      <button className="archive-link" onClick={handleDelete}>Archive this account</button>
    </div>
  );
}

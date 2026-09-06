import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchAccounts, createTransaction, createTransfer, emergencyUnblock } from '../api/endpoints';
import { toApiAmount, formatMoney, accountCategoryLabel } from '../utils/money';
import { newClientRequestId } from '../utils/idempotency';
import { Card, Field, Input, Select, Button, Banner } from '../components/ui';
import './AddTransactionPage.css';

const TYPES = [
  { value: 'expense', label: 'Expense', tone: 'negative' },
  { value: 'income', label: 'Income', tone: 'positive' },
  { value: 'lend', label: 'Lend', tone: 'negative' },
  { value: 'borrow', label: 'Borrow', tone: 'positive' },
  { value: 'transfer', label: 'Transfer', tone: 'neutral' },
];

const CATEGORIES = ['food', 'transport', 'bills', 'shopping', 'other'];

// Types that draw down the unblock_balance and can therefore hit insufficient funds.
const DEBIT_TYPES = ['expense', 'lend'];

export default function AddTransactionPage() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [type, setType] = useState('expense');
  const [accountId, setAccountId] = useState('');
  const [toAccountId, setToAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('food');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [requestId, setRequestId] = useState(newClientRequestId());

  // Insufficient-balance prompt state
  const [shortfall, setShortfall] = useState(null); // { needed, available, missing, canCover } | null

  // Non-Gullak spendable accounts only — transfers/expenses never touch Gullak directly
  // (blocking/unblocking into Gullak has its own dedicated flow on the account/Gullak pages).
  const reload = () =>
    fetchAccounts({ is_archived: false }).then((res) => {
      const list = res.data.results ?? res.data;
      const spendable = list.filter((a) => a.is_block_capable && a.category !== 'gullak');
      setAccounts(spendable);
      return spendable;
    });

  useEffect(() => {
    reload().then((spendable) => {
      if (spendable.length > 0) setAccountId(String(spendable[0].id));
      if (spendable.length > 1) setToAccountId(String(spendable[1].id));
    });
  }, []);

  const selectedAccount = useMemo(
    () => accounts.find((a) => String(a.id) === String(accountId)) || null,
    [accounts, accountId]
  );
  const toAccount = useMemo(
    () => accounts.find((a) => String(a.id) === String(toAccountId)) || null,
    [accounts, toAccountId]
  );

  const attemptSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setShortfall(null);
    if (!accountId) return setError('Choose an account.');
    if (type === 'transfer' && accountId === toAccountId) {
      return setError('Choose two different accounts for a transfer.');
    }

    const amountNum = parseFloat(amount || 0);
    const isDebit = DEBIT_TYPES.includes(type) || type === 'transfer';
    if (isDebit && selectedAccount && amountNum > Number(selectedAccount.unblock_balance)) {
      const missing = amountNum - Number(selectedAccount.unblock_balance);
      setShortfall({ needed: amountNum, available: Number(selectedAccount.unblock_balance), missing });
      return;
    }

    await doSubmit();
  };

  const doSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      if (type === 'transfer') {
        await createTransfer({
          from_account: Number(accountId),
          to_account: Number(toAccountId),
          amount: toApiAmount(amount),
          note,
          client_request_id: requestId,
        });
      } else {
        await createTransaction({
          account: Number(accountId),
          type,
          amount: toApiAmount(amount),
          category: type === 'expense' || type === 'income' ? category : undefined,
          note,
          client_request_id: requestId,
        });
      }
      navigate('/home');
    } catch (err) {
      const data = err.response?.data;
      const firstError = data && typeof data === 'object' ? Object.values(data)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || 'Could not save transaction.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUnblockAndContinue = async () => {
    if (!shortfall || !selectedAccount) return;
    setSubmitting(true);
    setError('');
    try {
      await emergencyUnblock(selectedAccount.id, toApiAmount(shortfall.missing), newClientRequestId());
      await reload();
      setShortfall(null);
      setRequestId(newClientRequestId());
      await doSubmit();
    } catch (err) {
      setError(err.response?.data?.amount?.[0] || err.response?.data?.detail || 'Could not unblock funds.');
      setSubmitting(false);
    }
  };

  if (accounts.length === 0) {
    return (
      <Card>
        <p className="muted">You need at least one Daily Transaction or Savings account before adding a transaction.</p>
        <Button onClick={() => navigate('/accounts/new')}>Add an account</Button>
      </Card>
    );
  }

  return (
    <div>
      <h1 style={{ fontSize: '1.3rem', marginBottom: 16 }}>Add transaction</h1>

      <div className="type-toggle">
        {TYPES.map((t) => (
          <button
            key={t.value}
            type="button"
            className={`type-chip type-chip--${t.tone}${type === t.value ? ' active' : ''}`}
            onClick={() => { setType(t.value); setShortfall(null); setError(''); }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Card>
        {error && <Banner tone="warn">{error}</Banner>}

        {shortfall && (
          <Banner tone="warn">
            <div className="shortfall-alert">
              <p className="shortfall-alert__title">Insufficient balance</p>
              <p>
                This needs {formatMoney(shortfall.needed)}, but only {formatMoney(shortfall.available)} is
                available to spend — short by {formatMoney(shortfall.missing)}.
              </p>
              <p className="muted" style={{ margin: '4px 0 10px' }}>
                Unblocking {formatMoney(shortfall.missing)} from Gullak will cover the difference
                (if your Gullak total has enough).
              </p>
              <div className="action-row">
                <Button size="sm" variant="danger" onClick={handleUnblockAndContinue} disabled={submitting}>
                  {submitting ? 'Unblocking…' : `Unblock ${formatMoney(shortfall.missing)} and continue`}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setShortfall(null)}>Cancel</Button>
              </div>
            </div>
          </Banner>
        )}

        <form onSubmit={attemptSubmit}>
          <Field label="Amount (₹)" htmlFor="amount">
            <Input id="amount" type="number" min="0.01" step="0.01" required autoFocus
              value={amount} onChange={(e) => { setAmount(e.target.value); setShortfall(null); }} />
          </Field>

          <Field label={type === 'transfer' ? 'From account' : 'Account'} htmlFor="account">
            <Select id="account" value={accountId} onChange={(e) => { setAccountId(e.target.value); setShortfall(null); }}>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({accountCategoryLabel(a.category)})</option>
              ))}
            </Select>
          </Field>

          {selectedAccount && (
            <div className="account-balance-hint">
              <span>Available: <strong>{formatMoney(selectedAccount.unblock_balance)}</strong></span>
            </div>
          )}

          {type === 'transfer' && (
            <Field label="To account" htmlFor="to_account">
              <Select id="to_account" value={toAccountId} onChange={(e) => setToAccountId(e.target.value)}>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} ({accountCategoryLabel(a.category)})</option>
                ))}
              </Select>
            </Field>
          )}

          {type === 'transfer' && toAccount && (
            <div className="account-balance-hint">
              <span>To — Available: <strong>{formatMoney(toAccount.unblock_balance)}</strong></span>
            </div>
          )}

          {(type === 'expense' || type === 'income') && (
            <Field label="Category" htmlFor="category">
              <Select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</option>)}
              </Select>
            </Field>
          )}

          <Field label="Note (optional)" htmlFor="note">
            <Input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} />
          </Field>

          <Button type="submit" size="lg" disabled={submitting || !!shortfall}>
            {submitting ? 'Saving…' : 'Save transaction'}
          </Button>
        </form>
      </Card>
    </div>
  );
}

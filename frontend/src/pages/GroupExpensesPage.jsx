import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  fetchSharedAccountDetail, fetchGroupExpenses, logGroupExpense, deleteGroupExpense,
} from '../api/endpoints';
import { formatMoneyPrecise, toApiAmount, expenseCategoryLabel, todayLocalISO } from '../utils/money';
import { useAuth } from '../context/AuthContext';
import { Card, Field, Input, Select, Button, Banner, Spinner, EmptyState } from '../components/ui';
import './GroupExpensesPage.css';

const CATEGORIES = ['food', 'travel', 'accommodation', 'shopping', 'entertainment', 'utilities', 'other'];

export default function GroupExpensesPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [account, setAccount] = useState(null);
  const [members, setMembers] = useState([]);
  const [expenses, setExpenses] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // form state
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('food');
  const [paidBy, setPaidBy] = useState('');
  const [expenseDate, setExpenseDate] = useState(todayLocalISO());
  const [splitType, setSplitType] = useState('equal');
  const [participantIds, setParticipantIds] = useState([]);
  const [exactAmounts, setExactAmounts] = useState({});

  const load = async () => {
    const [detailRes, expensesRes] = await Promise.all([
      fetchSharedAccountDetail(id), fetchGroupExpenses(id),
    ]);
    setAccount(detailRes.data.account);
    setMembers(detailRes.data.members.map((m) => m.user));
    setExpenses(expensesRes.data);
    if (!paidBy) setPaidBy(String(user.id));
    if (participantIds.length === 0) setParticipantIds(detailRes.data.members.map((m) => String(m.user.id)));
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!expenses || !account) return <Spinner label="Loading expenses" />;

  const toggleParticipant = (uid) => {
    const key = String(uid);
    setParticipantIds((prev) => (prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]));
  };

  const exactTotal = participantIds.reduce((sum, uid) => sum + (parseFloat(exactAmounts[uid]) || 0), 0);
  const amountNum = parseFloat(amount) || 0;

  const resetForm = () => {
    setShowForm(false); setDescription(''); setAmount(''); setCategory('food');
    setSplitType('equal'); setExactAmounts({}); setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSubmitting(true);
    try {
      const payload = {
        paid_by: Number(paidBy), description, amount: toApiAmount(amount), category,
        split_type: splitType, expense_date: expenseDate,
        participant_ids: participantIds.map(Number),
      };
      if (splitType === 'exact') {
        payload.exact_shares = Object.fromEntries(
          participantIds.map((uid) => [uid, toApiAmount(exactAmounts[uid] || 0)])
        );
      }
      await logGroupExpense(id, payload);
      await load();
      resetForm();
    } catch (err) {
      const data = err.response?.data;
      setError(data?.detail || data?.exact_shares || data?.participants || 'Could not log expense.');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (expenseId) => {
    if (!window.confirm('Delete this expense? This cannot be undone.')) return;
    try {
      await deleteGroupExpense(id, expenseId);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete expense.');
    }
  };

  return (
    <div className="group-expenses">
      <p className="page-subtitle" style={{ marginBottom: 4 }}>{account.name}</p>
      <div className="group-expenses__head">
        <Link to={`/shared-accounts/${id}/settlements`} className="group-expenses__settle-link">
          View settlements →
        </Link>
      </div>

      {error && <Banner tone="warn">{error}</Banner>}

      {!showForm && (
        <Button onClick={() => setShowForm(true)} className="group-expenses__add-btn">+ Log an expense</Button>
      )}

      {showForm && (
        <Card>
          <form onSubmit={handleSubmit}>
            <Field label="Description">
              <Input value={description} onChange={(e) => setDescription(e.target.value)} required maxLength={200} />
            </Field>
            <Field label="Amount (₹)">
              <Input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required />
            </Field>
            <Field label="Category">
              <Select value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{expenseCategoryLabel(c)}</option>)}
              </Select>
            </Field>
            <Field label="Paid by">
              <Select value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>{m.username}{m.id === user.id && ' (you)'}</option>
                ))}
              </Select>
            </Field>
            <Field label="Date">
              <Input type="date" value={expenseDate} onChange={(e) => setExpenseDate(e.target.value)} required />
            </Field>

            <Field label="Split among">
              <div className="group-expenses__participants">
                {members.map((m) => (
                  <label key={m.id} className="group-expenses__participant-chip">
                    <input
                      type="checkbox"
                      checked={participantIds.includes(String(m.id))}
                      onChange={() => toggleParticipant(m.id)}
                    />
                    {m.username}
                  </label>
                ))}
              </div>
            </Field>

            <Field label="Split type">
              <Select value={splitType} onChange={(e) => setSplitType(e.target.value)}>
                <option value="equal">Split equally</option>
                <option value="exact">Exact amounts</option>
              </Select>
            </Field>

            {splitType === 'exact' && participantIds.length > 0 && (
              <div className="group-expenses__exact-shares">
                {participantIds.map((uid) => {
                  const member = members.find((m) => String(m.id) === uid);
                  return (
                    <Field key={uid} label={member?.username || uid}>
                      <Input
                        type="number" min="0" step="0.01"
                        value={exactAmounts[uid] || ''}
                        onChange={(e) => setExactAmounts((prev) => ({ ...prev, [uid]: e.target.value }))}
                        required
                      />
                    </Field>
                  );
                })}
                <p className={`group-expenses__exact-total ${Math.abs(exactTotal - amountNum) > 0.001 ? 'group-expenses__exact-total--mismatch' : ''}`}>
                  Total entered: {formatMoneyPrecise(exactTotal)} of {formatMoneyPrecise(amountNum || 0)}
                </p>
              </div>
            )}

            <div className="group-expenses__form-actions">
              <Button type="submit" disabled={submitting}>{submitting ? 'Logging…' : 'Log expense'}</Button>
              <Button type="button" variant="secondary" onClick={resetForm}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      <h2 className="group-expenses__section-title">Expenses</h2>
      {expenses.length === 0 ? (
        <EmptyState title="No expenses yet" message="Log the group's first shared expense to get started." />
      ) : (
        <div className="group-expenses__list">
          {expenses.map((exp) => (
            <Card key={exp.id} className="group-expenses__row">
              <div>
                <p className="group-expenses__desc">{exp.description}</p>
                <p className="group-expenses__meta">
                  {expenseCategoryLabel(exp.category)} · {exp.expense_date} · paid by {exp.paid_by.username}
                  {exp.paid_by.id === user.id && ' (you)'}
                </p>
                <p className="group-expenses__shares">
                  {exp.shares.map((s) => `${s.user.username}: ${formatMoneyPrecise(s.share_amount)}`).join(' · ')}
                </p>
              </div>
              <div className="group-expenses__row-right">
                <span className="group-expenses__amount">{formatMoneyPrecise(exp.amount)}</span>
                {(exp.paid_by.id === user.id || exp.created_by.id === user.id) && (
                  <Button size="sm" variant="secondary" onClick={() => handleDelete(exp.id)}>Delete</Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

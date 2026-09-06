import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchSplitGroupDetail, createSplitExpense } from '../../../api/endpoints';
import { formatMoneyPrecise, todayLocalISO } from '../../../utils/money';
import { useAuth } from '../../../context/AuthContext';
import { Card, Field, Input, Select, Button, Banner, Radio, Spinner } from '../../../components/ui';
import { previewEqualShares, previewPercentageShares, sumValues } from '../shared/splitMath';
import './AddExpensePage.css';

export default function AddExpensePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [group, setGroup] = useState(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [paidBy, setPaidBy] = useState('');
  const [expenseDate, setExpenseDate] = useState(todayLocalISO());
  const [splitType, setSplitType] = useState('equal');
  const [participantIds, setParticipantIds] = useState([]);
  const [exactShares, setExactShares] = useState({});
  const [percentages, setPercentages] = useState({});

  useEffect(() => {
    fetchSplitGroupDetail(id).then(({ data }) => {
      setGroup(data);
      setPaidBy(String(user.id));
      setParticipantIds(data.members.map((m) => String(m.user.id)));
    });
  }, [id, user.id]);

  if (!group) return <Spinner label="Loading group" />;

  const toggleParticipant = (uid) => {
    const key = String(uid);
    setParticipantIds((prev) => (prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]));
  };

  const amountNum = parseFloat(amount) || 0;
  const equalPreview = splitType === 'equal' ? previewEqualShares(amountNum, participantIds.map(Number)) : {};
  const percentageTotal = participantIds.reduce((sum, uid) => sum + (parseFloat(percentages[uid]) || 0), 0);
  const percentagePreview = splitType === 'percentage'
    ? previewPercentageShares(amountNum, Object.fromEntries(participantIds.map((uid) => [uid, percentages[uid] || 0])))
    : {};
  const exactTotal = sumValues(Object.fromEntries(participantIds.map((uid) => [uid, exactShares[uid] || 0])));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSubmitting(true);
    try {
      const payload = {
        description, amount: amountNum.toFixed(2), paid_by: Number(paidBy),
        split_type: splitType, expense_date: expenseDate,
        participant_ids: participantIds.map(Number),
      };
      if (splitType === 'custom') {
        payload.exact_shares = Object.fromEntries(
          participantIds.map((uid) => [uid, (parseFloat(exactShares[uid]) || 0).toFixed(2)]),
        );
      } else if (splitType === 'percentage') {
        payload.percentages = Object.fromEntries(
          participantIds.map((uid) => [uid, (parseFloat(percentages[uid]) || 0).toFixed(2)]),
        );
      }
      await createSplitExpense(id, payload);
      navigate(`/splits/${id}`);
    } catch (err) {
      const d = err.response?.data;
      const firstError = d && typeof d === 'object' ? Object.values(d)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || d?.detail || 'Could not save the expense.');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = description.trim() && amountNum > 0 && paidBy && participantIds.length > 0
    && (splitType !== 'custom' || Math.abs(exactTotal - amountNum) < 0.01)
    && (splitType !== 'percentage' || Math.abs(percentageTotal - 100) < 0.01);

  return (
    <div className="add-expense">
      <Card>
        <form onSubmit={handleSubmit}>
          <Field label="Description">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Dinner" required maxLength={200} />
          </Field>

          <Field label="Amount (₹)">
            <Input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required />
          </Field>

          <Field label="Paid By">
            <Select value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
              {group.members.map((m) => (
                <option key={m.user.id} value={m.user.id}>{m.user.username}{m.user.id === user.id && ' (you)'}</option>
              ))}
            </Select>
          </Field>

          <Field label="Date">
            <Input type="date" value={expenseDate} onChange={(e) => setExpenseDate(e.target.value)} required />
          </Field>

          <Field label="Split Type">
            <Radio name="split_type" value="equal" checked={splitType === 'equal'} onChange={() => setSplitType('equal')} label="Equal" />
            <Radio name="split_type" value="custom" checked={splitType === 'custom'} onChange={() => setSplitType('custom')} label="Custom" />
            <Radio name="split_type" value="percentage" checked={splitType === 'percentage'} onChange={() => setSplitType('percentage')} label="Percentage" />
          </Field>

          <Field label="Participants">
            <div className="add-expense__participants">
              {group.members.map((m) => (
                <label key={m.user.id} className="add-expense__participant-chip">
                  <input
                    type="checkbox"
                    checked={participantIds.includes(String(m.user.id))}
                    onChange={() => toggleParticipant(m.user.id)}
                  />
                  {m.user.username}
                </label>
              ))}
            </div>
          </Field>

          {splitType === 'equal' && participantIds.length > 0 && amountNum > 0 && (
            <div className="add-expense__preview">
              {participantIds.map((uid) => {
                const member = group.members.find((m) => String(m.user.id) === uid);
                return (
                  <p key={uid} className="add-expense__preview-row">
                    <span>{member?.user.username}</span>
                    <span>{formatMoneyPrecise(equalPreview[Number(uid)] || 0)}</span>
                  </p>
                );
              })}
            </div>
          )}

          {splitType === 'custom' && participantIds.length > 0 && (
            <div className="add-expense__custom-shares">
              {participantIds.map((uid) => {
                const member = group.members.find((m) => String(m.user.id) === uid);
                return (
                  <Field key={uid} label={member?.user.username || uid}>
                    <Input
                      type="number" min="0" step="0.01"
                      value={exactShares[uid] || ''}
                      onChange={(e) => setExactShares((prev) => ({ ...prev, [uid]: e.target.value }))}
                      required
                    />
                  </Field>
                );
              })}
              <p className={`add-expense__total ${Math.abs(exactTotal - amountNum) > 0.001 ? 'add-expense__total--mismatch' : ''}`}>
                Total entered: {formatMoneyPrecise(exactTotal)} of {formatMoneyPrecise(amountNum || 0)}
              </p>
            </div>
          )}

          {splitType === 'percentage' && participantIds.length > 0 && (
            <div className="add-expense__custom-shares">
              {participantIds.map((uid) => {
                const member = group.members.find((m) => String(m.user.id) === uid);
                return (
                  <Field key={uid} label={member?.user.username || uid}>
                    <Input
                      type="number" min="0" max="100" step="0.01"
                      value={percentages[uid] || ''}
                      onChange={(e) => setPercentages((prev) => ({ ...prev, [uid]: e.target.value }))}
                      required
                    />
                  </Field>
                );
              })}
              <p className={`add-expense__total ${Math.abs(percentageTotal - 100) > 0.001 ? 'add-expense__total--mismatch' : ''}`}>
                Total: {percentageTotal.toFixed(2)}% of 100%
              </p>
              {amountNum > 0 && Math.abs(percentageTotal - 100) < 0.001 && (
                <div className="add-expense__preview">
                  {participantIds.map((uid) => {
                    const member = group.members.find((m) => String(m.user.id) === uid);
                    return (
                      <p key={uid} className="add-expense__preview-row">
                        <span>{member?.user.username}</span>
                        <span>{formatMoneyPrecise(percentagePreview[Number(uid)] || 0)}</span>
                      </p>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {error && <Banner tone="warn">{error}</Banner>}

          <Button type="submit" disabled={submitting || !canSubmit} className="add-expense__submit">
            {submitting ? 'Saving…' : 'Save Expense'}
          </Button>
        </form>
      </Card>
    </div>
  );
}

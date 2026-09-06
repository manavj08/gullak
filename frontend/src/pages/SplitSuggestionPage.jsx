import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchSplitSuggestion, applySplitSuggestion, fetchMySharedAccountsForSplit, fetchGullakSummary,
} from '../api/endpoints';
import { formatMoney, toApiAmount } from '../utils/money';
import { Card, Field, Input, Button, Banner, EmptyState, Spinner } from '../components/ui';
import './SplitSuggestionPage.css';

export default function SplitSuggestionPage() {
  const navigate = useNavigate();
  const [unallocated, setUnallocated] = useState(null);
  const [newAmount, setNewAmount] = useState('');
  const [sharedAccounts, setSharedAccounts] = useState([]);
  const [selectedSharedIds, setSelectedSharedIds] = useState([]);
  const [askedAboutShared, setAskedAboutShared] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [overrides, setOverrides] = useState({});
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchGullakSummary().then(({ data }) => setUnallocated(Number(data.unallocated)));
    fetchMySharedAccountsForSplit().then(({ data }) => setSharedAccounts(data));
  }, []);

  const amountExceedsUnallocated = unallocated !== null && Number(newAmount) > unallocated;

  const runSuggestion = async (sharedIds) => {
    setError(''); setSubmitting(true);
    try {
      const { data } = await fetchSplitSuggestion(toApiAmount(newAmount), sharedIds);
      setSuggestion(data);
      const initial = {};
      data.forEach((s) => { initial[`${s.goal_id}:${s.funding_source}`] = s.suggested_amount; });
      setOverrides(initial);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not compute a suggestion.');
    } finally { setSubmitting(false); }
  };

  const handleSuggest = async (e) => {
    e.preventDefault();
    if (amountExceedsUnallocated) {
      setError(`This amount is more than your unallocated Gullak (${formatMoney(unallocated)}). Lower it, or add more to your Gullak first.`);
      return;
    }
    // First ask about shared accounts (if the user has any) before computing —
    // so the suggestion is computed once, already including whatever they chose.
    if (sharedAccounts.length > 0 && !askedAboutShared) {
      setAskedAboutShared(true);
      return;
    }
    await runSuggestion(selectedSharedIds);
  };

  const toggleSharedAccount = (id) => {
    setSelectedSharedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const confirmSharedChoice = async () => {
    await runSuggestion(selectedSharedIds);
  };

  const handleApply = async () => {
    setError(''); setSubmitting(true);
    try {
      const allocations = Object.entries(overrides)
        .map(([key, amount]) => ({ goal_id: Number(key.split(':')[0]), amount: toApiAmount(amount) }))
        .filter((a) => Number(a.amount) > 0);
      await applySplitSuggestion(allocations);
      navigate('/goals');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not apply the split.');
    } finally { setSubmitting(false); }
  };

  if (unallocated === null) return <Spinner label="Loading" />;

  return (
    <div>
      <p className="split-sub">
        Enter a new amount and we'll suggest how to split it across your goals based on how urgent each one is
        (how much is left, versus how many days until its deadline).
      </p>
      <p className="split-unallocated">Unallocated in your Gullak right now: <strong>{formatMoney(unallocated)}</strong></p>

      {!askedAboutShared && (
        <Card>
          <form onSubmit={handleSuggest}>
            <Field label="Amount to split" hint={`Up to ${formatMoney(unallocated)} (your current unallocated Gullak)`}>
              <Input
                type="number" min="0.01" max={unallocated} step="0.01"
                value={newAmount} onChange={(e) => setNewAmount(e.target.value)} required
              />
            </Field>
            {error && <Banner tone="warn">{error}</Banner>}
            <Button type="submit" disabled={submitting || !newAmount}>
              {submitting ? 'Calculating…' : 'Continue'}
            </Button>
          </form>
        </Card>
      )}

      {askedAboutShared && suggestion === null && (
        <Card>
          <h2 className="split-section-title">Also split through a shared account?</h2>
          <p className="split-sub">
            You're part of {sharedAccounts.length} shared account{sharedAccounts.length > 1 ? 's' : ''}. Pick any that
            have a common goal you'd also like included — each is capped against that account's own unallocated
            pool, never your personal Gullak.
          </p>
          <div className="split-shared-list">
            {sharedAccounts.map((acc) => (
              <label key={acc.id} className="split-shared-option">
                <input
                  type="checkbox"
                  checked={selectedSharedIds.includes(acc.id)}
                  onChange={() => toggleSharedAccount(acc.id)}
                />
                {acc.name}
              </label>
            ))}
          </div>
          {error && <Banner tone="warn">{error}</Banner>}
          <div className="split-shared-actions">
            <Button onClick={confirmSharedChoice} disabled={submitting}>
              {submitting ? 'Calculating…' : selectedSharedIds.length > 0 ? 'Continue with selected' : 'Skip — personal only'}
            </Button>
          </div>
        </Card>
      )}

      {suggestion !== null && suggestion.length === 0 && (
        <EmptyState
          title="No goals to split across"
          message="Add a deadline to at least one underfunded goal to get a suggestion."
        />
      )}

      {suggestion !== null && suggestion.length > 0 && (
        <div className="split-results">
          <h2 className="split-section-title">Suggested split</h2>
          <p className="split-sub">You can adjust any amount before applying.</p>
          {suggestion.map((s) => {
            const key = `${s.goal_id}:${s.funding_source}`;
            return (
              <Card key={key} className="split-row">
                <div>
                  <span className="split-row__name">{s.goal_name}</span>
                  {s.funding_source !== 'personal_gullak' && <span className="split-row__tag">Shared</span>}
                </div>
                <div className="split-row__input">
                  <span>₹</span>
                  <Input
                    type="number" min="0" step="0.01"
                    value={overrides[key] ?? ''}
                    onChange={(e) => setOverrides({ ...overrides, [key]: e.target.value })}
                  />
                </div>
              </Card>
            );
          })}
          <Button onClick={handleApply} disabled={submitting}>{submitting ? 'Applying…' : 'Apply split'}</Button>
        </div>
      )}
    </div>
  );
}

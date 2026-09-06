import { useEffect, useState, lazy, Suspense } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchGullakSummary, fetchAccounts, fetchStreakSummary, checkIn, fetchTransactions,
  fetchPendingDeductions, resolvePendingDeduction, fetchGoals,
} from '../api/endpoints';
import { formatMoney, todayLocalISO, categoryLabel, accountCategoryLabel } from '../utils/money';
import GullakMark from '../components/GullakMark';
import { Card, Spinner, Button, Banner, Field, Input } from '../components/ui';
import './HomePage.css';

// Lazy-loaded so the recharts library (and its d3 dependencies) ship as a
// separate chunk instead of bloating the main app bundle every page needs.
const NetWorthChart = lazy(() => import('../components/NetWorthChart'));
const SpendByCategoryChart = lazy(() => import('../components/SpendByCategoryChart'));
import './HomePage.css';

export default function HomePage() {
  const [summary, setSummary] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [streak, setStreak] = useState(null);
  const [recentTxns, setRecentTxns] = useState([]);
  const [pendingDeductions, setPendingDeductions] = useState([]);
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checkingIn, setCheckingIn] = useState(false);

  const today = todayLocalISO();

  const load = async () => {
    setLoading(true);
    const [summaryRes, accountsRes, streakRes, txnRes, pendingRes, goalsRes] = await Promise.all([
      fetchGullakSummary(),
      fetchAccounts({ is_archived: false }),
      fetchStreakSummary(today),
      fetchTransactions({ ordering: '-timestamp' }),
      fetchPendingDeductions(),
      fetchGoals(),
    ]);
    setSummary(summaryRes.data);
    setAccounts(accountsRes.data.results ?? accountsRes.data);
    setStreak(streakRes.data);
    setRecentTxns((txnRes.data.results ?? txnRes.data).slice(0, 5));
    setPendingDeductions(pendingRes.data.results ?? pendingRes.data);
    setGoals(goalsRes.data.results ?? goalsRes.data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCheckIn = async () => {
    setCheckingIn(true);
    try {
      await checkIn(today);
      const streakRes = await fetchStreakSummary(today);
      setStreak(streakRes.data);
    } finally {
      setCheckingIn(false);
    }
  };

  if (loading) return <Spinner label="Loading your Gullak" />;

  // Gullak has its own dedicated card/page under Accounts — don't duplicate it in this mini-grid.
  const spendableAccounts = accounts.filter((a) => a.is_block_capable && a.category !== 'gullak');

  return (
    <div className="home-page">
      <header className="home-header">
        <div>
          <p className="home-greeting">Your Gullak</p>
        </div>
        <GullakMark size={30} />
      </header>

      {pendingDeductions.length > 0 && (
        <PendingDeductionModal
          deduction={pendingDeductions[0]}
          goals={goals}
          onResolved={load}
        />
      )}

      <Card className="gullak-hero">
        <p className="gullak-hero__label">Total in Gullak</p>
        <p className="gullak-hero__amount">{formatMoney(summary.gullak_total)}</p>
        <p className="gullak-hero__sub">
          Net worth: {formatMoney(summary.net_worth)} · Unallocated: {formatMoney(summary.unallocated)}
        </p>
      </Card>

      <section className="home-section home-analytics">
        <Suspense fallback={<Spinner label="Loading charts" />}>
          <NetWorthChart />
          <SpendByCategoryChart />
        </Suspense>
      </section>

      {!streak?.checked_in_today && (
        <Banner tone="info">
          <div className="checkin-row">
            <span>Haven't logged anything today. Quick check-in?</span>
            <Button size="sm" variant="secondary" onClick={handleCheckIn} disabled={checkingIn}>
              {checkingIn ? 'Saving…' : "I'm on track"}
            </Button>
          </div>
        </Banner>
      )}

      <div className="streak-row">
        <span className="streak-flame">🔥</span>
        <span><strong>{streak?.current_streak ?? 0}</strong> day streak</span>
      </div>

      <section className="home-section">
        <div className="home-section__head">
          <h2>Accounts</h2>
          <Link to="/accounts" className="home-section__link">View all</Link>
        </div>
        {spendableAccounts.length === 0 ? (
          <Card><p className="muted">No spendable accounts yet. Add one to get started.</p></Card>
        ) : (
          <div className="account-grid">
            {spendableAccounts.slice(0, 4).map((a) => (
              <Card key={a.id} className="account-mini">
                <p className="account-mini__cat">{accountCategoryLabel(a.category)}</p>
                <p className="account-mini__name">{a.name}</p>
                <p className="account-mini__balance">{formatMoney(a.unblock_balance)}</p>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="home-section">
        <div className="home-section__head">
          <h2>Recent activity</h2>
          <Link to="/transactions" className="home-section__link">View all</Link>
        </div>
        {recentTxns.length === 0 ? (
          <Card><p className="muted">No transactions yet. Tap Add to log your first one.</p></Card>
        ) : (
          <Card className="txn-list">
            {recentTxns.map((t) => (
              <div className="txn-row" key={t.id}>
                <div>
                  <p className="txn-row__note">{t.note || categoryLabel(t.category)}</p>
                  <p className="txn-row__meta">{categoryLabel(t.category)} · {new Date(t.timestamp).toLocaleDateString()}</p>
                </div>
                <p className={`txn-row__amount txn-row__amount--${signClass(t.type)}`}>
                  {sign(t.type)}{formatMoney(t.amount)}
                </p>
              </div>
            ))}
          </Card>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Blocks the rest of Home behind a modal until the user decides which goal(s)
// an emergency-unblock overage should be deducted from. Simple single-goal
// picker by default; supports splitting across goals via "Split differently".
// ---------------------------------------------------------------------------
function PendingDeductionModal({ deduction, goals, onResolved }) {
  const eligibleGoals = goals.filter((g) => Number(g.allocated_amount) > 0);
  const [splitMode, setSplitMode] = useState(false);
  const [selectedGoalId, setSelectedGoalId] = useState(eligibleGoals[0]?.id ?? '');
  const [splitAmounts, setSplitAmounts] = useState(() =>
    Object.fromEntries(eligibleGoals.map((g) => [g.id, '']))
  );
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const totalAmount = Number(deduction.amount);

  const handleSingleResolve = async () => {
    setError('');
    if (!selectedGoalId) return setError('Choose a goal.');
    const goal = eligibleGoals.find((g) => g.id === Number(selectedGoalId));
    if (goal && Number(goal.allocated_amount) < totalAmount) {
      return setError(`"${goal.name}" only has ${formatMoney(goal.allocated_amount)} allocated — not enough to cover this ${formatMoney(totalAmount)} adjustment. Try splitting across goals instead.`);
    }
    setSubmitting(true);
    try {
      await resolvePendingDeduction(deduction.id, [
        { goal_id: Number(selectedGoalId), amount: totalAmount.toFixed(2) },
      ]);
      await onResolved();
    } catch (err) {
      setError(err.response?.data?.allocations?.[0] || err.response?.data?.detail || 'Could not resolve this.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSplitResolve = async () => {
    setError('');
    const allocations = Object.entries(splitAmounts)
      .filter(([, v]) => v && Number(v) > 0)
      .map(([goalId, v]) => ({ goal_id: Number(goalId), amount: Number(v).toFixed(2) }));
    const sum = allocations.reduce((s, a) => s + Number(a.amount), 0);
    if (Math.abs(sum - totalAmount) > 0.001) {
      return setError(`Split amounts must add up to exactly ${formatMoney(totalAmount)} (currently ${formatMoney(sum)}).`);
    }
    setSubmitting(true);
    try {
      await resolvePendingDeduction(deduction.id, allocations);
      await onResolved();
    } catch (err) {
      setError(err.response?.data?.allocations?.[0] || err.response?.data?.detail || 'Could not resolve this.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="pending-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="pending-modal-title">
      <Card className="pending-modal">
        <GullakMark size={32} />
        <h2 id="pending-modal-title">A recent emergency unblock dipped into goal funds</h2>
        <p className="muted">
          {formatMoney(totalAmount)} of your last emergency unblock came out of money already allocated to a goal.
          Which goal should it come from?
        </p>

        {error && <Banner tone="warn">{error}</Banner>}

        {eligibleGoals.length === 0 ? (
          <p className="muted">
            No goals currently have funds allocated — this shouldn't normally happen. Contact support if you see this.
          </p>
        ) : !splitMode ? (
          <>
            <div className="pending-modal__goal-list">
              {eligibleGoals.map((g) => (
                <label key={g.id} className="pending-modal__goal-option">
                  <input
                    type="radio" name="pending-goal" value={g.id}
                    checked={String(selectedGoalId) === String(g.id)}
                    onChange={() => setSelectedGoalId(g.id)}
                  />
                  <span>{g.name}</span>
                  <span className="muted">{formatMoney(g.allocated_amount)} allocated</span>
                </label>
              ))}
            </div>
            <div className="action-row">
              <Button variant="danger" onClick={handleSingleResolve} disabled={submitting}>
                {submitting ? 'Applying…' : `Deduct from this goal`}
              </Button>
              {eligibleGoals.length > 1 && (
                <Button variant="secondary" onClick={() => setSplitMode(true)}>Split across goals</Button>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="pending-modal__split-list">
              {eligibleGoals.map((g) => (
                <Field key={g.id} label={`${g.name} (max ${formatMoney(g.allocated_amount)})`} htmlFor={`split-${g.id}`}>
                  <Input
                    id={`split-${g.id}`} type="number" min="0" step="0.01"
                    value={splitAmounts[g.id]}
                    onChange={(e) => setSplitAmounts({ ...splitAmounts, [g.id]: e.target.value })}
                  />
                </Field>
              ))}
            </div>
            <p className="muted">Must add up to exactly {formatMoney(totalAmount)}.</p>
            <div className="action-row">
              <Button variant="danger" onClick={handleSplitResolve} disabled={submitting}>
                {submitting ? 'Applying…' : 'Apply split'}
              </Button>
              <Button variant="secondary" onClick={() => setSplitMode(false)}>Back</Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

function sign(type) {
  return ['income', 'borrow'].includes(type) ? '+' : ['expense', 'lend'].includes(type) ? '−' : '';
}
function signClass(type) {
  return ['income', 'borrow'].includes(type) ? 'positive' : ['expense', 'lend'].includes(type) ? 'negative' : 'neutral';
}

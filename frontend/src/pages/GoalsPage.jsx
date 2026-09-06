import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchGoals, createGoal, addFundsToGoal, deleteGoal, fetchGullakSummary } from '../api/endpoints';
import { formatMoney, toApiAmount } from '../utils/money';
import { Card, Field, Input, Button, Banner, EmptyState, Spinner } from '../components/ui';
import GullakMark from '../components/GullakMark';
import './GoalsPage.css';

export default function GoalsPage() {
  const [goals, setGoals] = useState(null);
  const [summary, setSummary] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const load = async () => {
    const [goalsRes, summaryRes] = await Promise.all([fetchGoals(), fetchGullakSummary()]);
    setGoals(goalsRes.data.results ?? goalsRes.data);
    setSummary(summaryRes.data);
  };

  useEffect(() => { load(); }, []);

  if (goals === null || summary === null) return <Spinner label="Loading goals" />;

  const gullakTotal = Number(summary.gullak_total);
  const allocated = Number(summary.allocated);
  const unallocated = Number(summary.unallocated);

  return (
    <div>
      <div className="goals-head">
        <div className="goals-head__actions">
          <Link to="/goals/split-suggestion"><Button size="sm" variant="secondary">Smart split</Button></Link>
          <Button size="sm" onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : '+ New goal'}</Button>
        </div>
      </div>

      <Card className="goals-hero">
        <p className="goals-hero__label">Gullak total</p>
        <p className="goals-hero__amount">{formatMoney(gullakTotal)}</p>
        <div className="goals-hero__split">
          <div className="goals-hero__stat">
            <span className="goals-hero__stat-dot goals-hero__stat-dot--allocated" />
            <div>
              <p className="goals-hero__stat-label">Allocated</p>
              <p className="goals-hero__stat-value">{formatMoney(allocated)}</p>
            </div>
          </div>
          <div className="goals-hero__stat">
            <span className="goals-hero__stat-dot goals-hero__stat-dot--unallocated" />
            <div>
              <p className="goals-hero__stat-label">Unallocated</p>
              <p className="goals-hero__stat-value">{formatMoney(unallocated)}</p>
            </div>
          </div>
        </div>
        <div className="goals-hero__track">
          <div
            className="goals-hero__track-fill"
            style={{ width: `${gullakTotal > 0 ? Math.min(100, (allocated / gullakTotal) * 100) : 0}%` }}
          />
        </div>
      </Card>

      {showForm && <NewGoalForm onCreated={() => { setShowForm(false); load(); }} />}

      {goals.length === 0 ? (
        <EmptyState
          icon={<GullakMark size={56} />}
          title="No goals yet"
          message="Set a savings goal and add funds toward it from your Gullak."
        />
      ) : (
        <div className="goals-list">
          {goals.map((g) => (
            <GoalCard key={g.id} goal={g} onChange={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function NewGoalForm({ onCreated }) {
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [deadline, setDeadline] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await createGoal({ name, target_amount: toApiAmount(target), deadline: deadline || null });
      onCreated();
    } catch (err) {
      setError(err.response?.data?.target_amount?.[0] || 'Could not create goal.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card style={{ marginBottom: 16 }}>
      {error && <Banner tone="warn">{error}</Banner>}
      <form onSubmit={handleSubmit}>
        <Field label="Goal name" htmlFor="goal_name">
          <Input id="goal_name" required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Target amount (₹)" htmlFor="goal_target">
          <Input id="goal_target" type="number" min="1" step="0.01" required value={target}
            onChange={(e) => setTarget(e.target.value)} />
        </Field>
        <Field label="Deadline (optional)" htmlFor="goal_deadline">
          <Input id="goal_deadline" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </Field>
        <Button type="submit" disabled={submitting}>{submitting ? 'Creating…' : 'Create goal'}</Button>
      </form>
    </Card>
  );
}

function GoalCard({ goal, onChange }) {
  const [addingFunds, setAddingFunds] = useState(false);
  const [addAmount, setAddAmount] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleAddFunds = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await addFundsToGoal(goal.id, toApiAmount(addAmount));
      setAddingFunds(false);
      setAddAmount('');
      onChange();
    } catch (err) {
      setError(err.response?.data?.add_amount?.[0] || 'Could not add funds.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete goal "${goal.name}"? Its allocated funds return to unallocated Gullak.`)) return;
    await deleteGoal(goal.id);
    onChange();
  };

  return (
    <Card className={`goal-card${goal.status === 'underfunded' ? ' goal-card--underfunded' : ''}`}>
      <div className="goal-card__head">
        <div>
          <p className="goal-card__name">{goal.name}</p>
          {goal.deadline && <p className="goal-card__deadline">By {goal.deadline}</p>}
        </div>
        {goal.funding_source === 'shared_account' && (
          <Link to={`/goals/shared/${goal.id}`} className="goal-badge goal-badge--shared">Shared →</Link>
        )}
        {goal.status === 'underfunded' && <span className="goal-badge">Underfunded</span>}
        {goal.is_achieved && <span className="goal-badge goal-badge--success">Achieved 🎉</span>}
      </div>

      <div className="goal-progress-track">
        <div className="goal-progress-fill" style={{ width: `${goal.progress_percent}%` }} />
      </div>
      <p className="goal-card__figures">
        {formatMoney(goal.allocated_amount)} of {formatMoney(goal.target_amount)} ({goal.progress_percent}%)
      </p>

      {addingFunds ? (
        <form onSubmit={handleAddFunds} className="goal-allocate-form">
          {error && <Banner tone="warn">{error}</Banner>}
          <Field label="Add funds (₹)" htmlFor={`add-${goal.id}`} hint="Comes out of your unallocated Gullak.">
            <Input id={`add-${goal.id}`} type="number" min="0.01" step="0.01" value={addAmount}
              onChange={(e) => setAddAmount(e.target.value)} autoFocus />
          </Field>
          <div className="action-row">
            <Button size="sm" type="submit" disabled={submitting || !addAmount}>
              {submitting ? 'Adding…' : 'Add'}
            </Button>
            <Button size="sm" variant="secondary" type="button" onClick={() => { setAddingFunds(false); setError(''); }}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="action-row">
          <Button size="sm" variant="secondary" onClick={() => setAddingFunds(true)}>Add funds</Button>
          <Button size="sm" variant="ghost" onClick={handleDelete}>Delete</Button>
        </div>
      )}
    </Card>
  );
}

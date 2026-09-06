import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchSharedGoalDetail } from '../api/endpoints';
import { formatMoney } from '../utils/money';
import { Card, Spinner, Banner } from '../components/ui';
import './SharedGoalDetailPage.css';

export default function SharedGoalDetailPage() {
  const { id } = useParams();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSharedGoalDetail(id)
      .then(({ data }) => setDetail(data))
      .catch((err) => setError(err.response?.data?.detail || 'Could not load this goal.'));
  }, [id]);

  if (error) return <Banner tone="warn">{error}</Banner>;
  if (!detail) return <Spinner label="Loading goal" />;

  const { goal, progress, member_count, shared_account_id } = detail;
  const target = Number(progress.target_amount);
  const allocated = Number(progress.allocated_amount);
  const remaining = Number(progress.remaining_amount);
  const own = Number(progress.own_contribution);
  const others = Number(progress.others_aggregate);
  const percent = target > 0 ? Math.min(100, Math.round((allocated / target) * 100)) : 0;

  return (
    <div>
      <p className="page-subtitle">{goal.name}</p>
      <p className="shared-goal__sub">
        Shared with {member_count} member{member_count > 1 ? 's' : ''} ·{' '}
        <Link to={`/shared-accounts/${shared_account_id}`}>View shared account</Link>
      </p>

      <Card className="shared-goal__hero">
        <div className="shared-goal__progress-row">
          <span>{formatMoney(allocated)} of {formatMoney(target)}</span>
          <span>{percent}%</span>
        </div>
        <div className="shared-goal__bar">
          <div className="shared-goal__bar-fill" style={{ width: `${percent}%` }} />
        </div>
        <p className="shared-goal__remaining">{formatMoney(remaining)} remaining</p>
      </Card>

      <Card className="shared-goal__breakdown">
        <p className="shared-goal__breakdown-title">Who's funded this goal</p>
        <div className="shared-goal__breakdown-row">
          <span className="dot dot--mine" /> You contributed
          <strong>{formatMoney(own)}</strong>
        </div>
        <div className="shared-goal__breakdown-row">
          <span className="dot dot--others" /> Everyone else (combined)
          <strong>{formatMoney(others)}</strong>
        </div>
        <p className="shared-goal__hint">
          Other members' individual contributions toward this goal are never shown separately — only this combined total.
        </p>
      </Card>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchSplitGroups } from '../../../api/endpoints';
import { formatMoneyPrecise } from '../../../utils/money';
import { Card, Button, Banner, EmptyState, Spinner } from '../../../components/ui';
import './SplitGroupsPage.css';

export default function SplitGroupsPage() {
  const [groups, setGroups] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSplitGroups()
      .then(({ data }) => setGroups(data))
      .catch(() => { setError('Could not load your split groups.'); setGroups([]); });
  }, []);

  if (groups === null) return <Spinner label="Loading split groups" />;

  return (
    <div className="split-groups">
      <p className="page-subtitle">Split expenses with anyone — no shared wallet needed.</p>
      <div className="split-groups__head">
        <Link to="/splits/settings" className="split-groups__settings-link">UPI settings</Link>
        <Link to="/splits/new"><Button size="sm">+ New Group</Button></Link>
      </div>

      {error && <Banner tone="warn">{error}</Banner>}

      {groups.length === 0 ? (
        <EmptyState
          icon={<SplitIcon />}
          title="No split groups yet"
          message="Create a group to start splitting expenses with friends."
          action={<Link to="/splits/new"><Button>Create a group</Button></Link>}
        />
      ) : (
        <div className="split-groups__list">
          {groups.map((g) => {
            const pending = Number(g.pending_settlement_total || 0);
            return (
              <Link key={g.id} to={`/splits/${g.id}`} className="split-group-card-link">
                <Card className="split-group-card">
                  <div>
                    <p className="split-group-card__name">{g.name}</p>
                    <p className="split-group-card__meta">{g.member_count} member{g.member_count === 1 ? '' : 's'}</p>
                  </div>
                  <p className={`split-group-card__pending${pending > 0 ? ' split-group-card__pending--active' : ''}`}>
                    {pending > 0 ? `${formatMoneyPrecise(pending)} pending` : 'Settled up'}
                  </p>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SplitIcon() {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
      <path d="M4 7h16M4 7l3-3M4 7l3 3M20 17H4M20 17l-3-3M20 17l-3 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

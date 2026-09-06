import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchSharedAccounts } from '../api/endpoints';
import { formatMoney } from '../utils/money';
import { Card, Button, EmptyState, Spinner } from '../components/ui';
import './SharedAccountsPage.css';

export default function SharedAccountsPage() {
  const [accounts, setAccounts] = useState(null);

  useEffect(() => {
    fetchSharedAccounts().then(({ data }) => setAccounts(data.results ?? data));
  }, []);

  if (accounts === null) return <Spinner label="Loading shared accounts" />;

  return (
    <div>
      <div className="shared-head">
        <Link to="/shared-accounts/new"><Button size="sm">+ New</Button></Link>
      </div>
      <p className="shared-sub">Save with a partner, or pool money with family and friends for something specific.</p>

      {accounts.length === 0 ? (
        <EmptyState
          icon={<PeopleIcon />}
          title="No shared accounts yet"
          message="Start a two-person savings account, or create a group for a trip, gift, or event."
          action={<Link to="/shared-accounts/new"><Button>Create one</Button></Link>}
        />
      ) : (
        <div className="shared-list">
          {accounts.map((acc) => (
            <Link key={acc.id} to={`/shared-accounts/${acc.id}`} className="shared-card-link">
              <Card className="shared-card">
                <div className="shared-card__row">
                  <div>
                    <p className="shared-card__name">{acc.name}</p>
                    <p className="shared-card__type">
                      {acc.owner_type === 'shared_pair' ? 'Relationship (2 people)' : 'Group'}
                    </p>
                  </div>
                  <p className="shared-card__amount">{formatMoney(Number(acc.block_balance || 0))}</p>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function PeopleIcon() {
  return <svg width="40" height="40" viewBox="0 0 24 24" fill="none"><circle cx="8.5" cy="8" r="3" stroke="currentColor" strokeWidth="1.6"/><circle cx="17" cy="9" r="2.2" stroke="currentColor" strokeWidth="1.6"/><path d="M2.5 20c1.2-3.6 4-5.2 6-5.2s4.8 1.6 6 5.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/><path d="M14.5 15.2c2.4.3 4.3 1.8 5.2 4.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>;
}

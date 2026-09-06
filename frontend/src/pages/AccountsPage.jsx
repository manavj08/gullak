import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchAccounts } from '../api/endpoints';
import { formatMoney, accountCategoryLabel } from '../utils/money';
import { getSetting, setSetting } from '../utils/settings';
import { Card, Spinner, EmptyState, Button } from '../components/ui';
import GullakMark from '../components/GullakMark';
import './AccountsPage.css';

const CATEGORY_ORDER = ['daily_transaction', 'savings', 'revenue_generation', 'loan_debt'];
const VIEW_KEY = 'accounts_view_mode';

export default function AccountsPage() {
  const [accounts, setAccounts] = useState(null);
  const [viewMode, setViewMode] = useState(() => getSetting(VIEW_KEY, 'grid'));

  useEffect(() => {
    fetchAccounts({ is_archived: false }).then((res) => {
      setAccounts(res.data.results ?? res.data);
    });
  }, []);

  const changeView = (mode) => {
    setViewMode(mode);
    setSetting(VIEW_KEY, mode);
  };

  if (accounts === null) return <Spinner label="Loading accounts" />;

  const gullak = accounts.find((a) => a.category === 'gullak');
  const otherAccounts = accounts.filter((a) => a.category !== 'gullak');

  if (otherAccounts.length === 0) {
    return (
      <div className="accounts-page">
        {gullak && <GullakCard account={gullak} />}
        <EmptyState
          icon={<GullakMark size={56} />}
          title="No accounts yet"
          message="Add your first account — a UPI wallet, savings account, investment, or credit card."
          action={<Link to="/accounts/new"><Button>Add an account</Button></Link>}
        />
      </div>
    );
  }

  const grouped = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: otherAccounts.filter((a) => a.category === cat),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="accounts-page">
      <div className="accounts-page__head">
        <Link to="/accounts/new"><Button size="sm">+ Add account</Button></Link>
      </div>

      {gullak && <GullakCard account={gullak} />}

      <div className="view-toggle" role="group" aria-label="Change accounts layout">
        <button
          type="button"
          className={`view-toggle__btn${viewMode === 'grid' ? ' active' : ''}`}
          onClick={() => changeView('grid')}
          aria-pressed={viewMode === 'grid'}
        >
          <GridIcon /> Grid
        </button>
        <button
          type="button"
          className={`view-toggle__btn${viewMode === 'scroll' ? ' active' : ''}`}
          onClick={() => changeView('scroll')}
          aria-pressed={viewMode === 'scroll'}
        >
          <ScrollIcon /> Scroll
        </button>
      </div>

      {grouped.map((group) => (
        <section key={group.cat} className="accounts-group">
          <h2>{accountCategoryLabel(group.cat)}</h2>
          {viewMode === 'grid' ? (
            <div className="accounts-grid">
              {group.items.map((a) => <AccountTile key={a.id} account={a} />)}
            </div>
          ) : (
            <div className="accounts-scroll">
              {group.items.map((a) => <AccountTile key={a.id} account={a} />)}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

function GullakCard({ account }) {
  return (
    <Link to={`/accounts/${account.id}`} className="gullak-account-link">
      <Card className="gullak-account-card">
        <GullakMark size={30} color="#fff" />
        <div className="gullak-account-card__text">
          <p className="gullak-account-card__label">Gullak</p>
          <p className="gullak-account-card__amount">{formatMoney(account.unblock_balance)}</p>
        </div>
        <ChevronIcon />
      </Card>
    </Link>
  );
}

function AccountTile({ account: a }) {
  return (
    <Link to={`/accounts/${a.id}`} className="account-tile-link">
      <Card className="account-tile">
        <p className="account-tile__type">{a.account_type}</p>
        <p className="account-tile__name">{a.name}</p>
        <div className="account-tile__figures">{renderFigures(a)}</div>
      </Card>
    </Link>
  );
}

function renderFigures(a) {
  if (a.is_block_capable) {
    return (
      <>
        <p className="figure figure--unblock">{formatMoney(a.unblock_balance)}</p>
        <p className="figure-label">{formatMoney(a.block_balance)} saved</p>
      </>
    );
  }
  if (a.category === 'revenue_generation') {
    return <p className="figure figure--block">{formatMoney(a.current_value)}</p>;
  }
  if (a.category === 'loan_debt') {
    return <p className="figure figure--warn">{formatMoney(a.amount_owed)} owed</p>;
  }
  return null;
}

function ChevronIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}
function ScrollIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="6" width="7" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="10.5" y="6" width="7" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="19" y="6" width="3" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.8" opacity="0.5" />
    </svg>
  );
}

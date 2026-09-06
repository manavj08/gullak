import { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { fetchUnreadNotificationCount } from '../api/endpoints';
import './PageHeader.css';

// Root-level pages (bottom-nav destinations) show no back arrow — there's nowhere
// "back" to go within the app from these. Every other page gets one.
const ROOT_PATHS = new Set(['/home', '/accounts', '/goals', '/profile']);

const TITLES = {
  '/home': 'Home',
  '/accounts': 'Accounts',
  '/accounts/new': 'Add Account',
  '/add': 'Add Transaction',
  '/transactions': 'Transactions',
  '/goals': 'Goals',
  '/goals/split-suggestion': 'Smart Split',
  '/profile': 'Profile',
  '/notifications': 'Notifications',
  '/shared-accounts': 'Shared Accounts',
  '/shared-accounts/new': 'New Shared Account',
  '/splits': 'Split Groups',
  '/splits/new': 'Create Group',
  '/splits/settings': 'UPI Settings',
};

function resolveTitle(pathname) {
  if (TITLES[pathname]) return TITLES[pathname];
  if (/^\/accounts\/\d+$/.test(pathname)) return 'Account';
  if (/^\/shared-accounts\/\d+$/.test(pathname)) return 'Shared Account';
  if (/^\/shared-accounts\/\d+\/expenses$/.test(pathname)) return 'Group Expenses';
  if (/^\/shared-accounts\/\d+\/settlements$/.test(pathname)) return 'Settlements';
  if (/^\/goals\/shared\/\d+$/.test(pathname)) return 'Goal Progress';
  if (/^\/splits\/\d+\/expenses\/new$/.test(pathname)) return 'Add Expense';
  if (/^\/splits\/\d+\/settlements$/.test(pathname)) return 'Settlement';
  if (/^\/splits\/\d+$/.test(pathname)) return 'Group Detail';
  return 'Gullak';
}

export default function PageHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // Refresh-on-navigation: re-checked on every route change so the badge stays
    // current as the user moves through the app, without any polling/socket.
    fetchUnreadNotificationCount()
      .then(({ data }) => { if (!cancelled) setUnread(data.unread_count); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [location.pathname]);

  const showBack = !ROOT_PATHS.has(location.pathname);
  const title = resolveTitle(location.pathname);

  return (
    <header className="page-header">
      <div className="page-header__side">
        {showBack && (
          <button className="page-header__back" onClick={() => navigate(-1)} aria-label="Go back">
            <BackIcon />
          </button>
        )}
      </div>
      <h1 className="page-header__title">{title}</h1>
      <div className="page-header__side page-header__side--right">
        <Link to="/notifications" className="page-header__bell" aria-label="Notifications">
          <BellIcon />
          {unread > 0 && <span className="page-header__badge">{unread > 9 ? '9+' : unread}</span>}
        </Link>
      </div>
    </header>
  );
}

function BackIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
function BellIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 13 6 9Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><path d="M9.5 17a2.5 2.5 0 0 0 5 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>;
}

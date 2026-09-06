import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import GullakMark from './GullakMark';
import PageHeader from './PageHeader';
import { useAuth } from '../context/AuthContext';
import './Layout.css';

const NAV_ITEMS = [
  { to: '/home', label: 'Home', icon: HomeIcon },
  { to: '/accounts', label: 'Accounts', icon: WalletIcon },
  { to: '/add', label: 'Add', icon: PlusIcon, isAction: true },
  { to: '/goals', label: 'Goals', icon: TargetIcon },
  { to: '/profile', label: 'Profile', icon: UserIcon },
];

export default function Layout() {
  return (
    <div className="app-shell">
      <SideRail />
      <main className="app-main">
        <PageHeader />
        <Outlet />
      </main>
      <BottomNav />
    </div>
  );
}

function SideRail() {
  const { lock } = useAuth();
  const navigate = useNavigate();
  return (
    <nav className="side-rail" aria-label="Main navigation">
      <div className="side-rail__brand">
        <GullakMark size={28} />
        <span>Gullak</span>
      </div>
      <ul className="side-rail__list">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} className={({ isActive }) => `side-rail__link${isActive ? ' active' : ''}`}>
              <item.icon />
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
        <li>
          <NavLink to="/shared-accounts" className={({ isActive }) => `side-rail__link${isActive ? ' active' : ''}`}>
            <PeopleIcon />
            <span>Shared</span>
          </NavLink>
        </li>
        <li>
          <NavLink to="/splits" className={({ isActive }) => `side-rail__link${isActive ? ' active' : ''}`}>
            <SplitIcon />
            <span>Splits</span>
          </NavLink>
        </li>
      </ul>
      <button
        className="side-rail__lock"
        onClick={() => { lock(); navigate('/unlock'); }}
      >
        <LockIcon /> Lock app
      </button>
    </nav>
  );
}

function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="Main navigation">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `bottom-nav__item${isActive ? ' active' : ''}${item.isAction ? ' bottom-nav__item--action' : ''}`
          }
        >
          <item.icon />
          <span>{item.label}</span>
        </NavLink>
      ))}
      <NavLink
        to="/shared-accounts"
        className={({ isActive }) => `bottom-nav__item${isActive ? ' active' : ''}`}
      >
        <PeopleIcon />
        <span>Shared</span>
      </NavLink>
      <NavLink
        to="/splits"
        className={({ isActive }) => `bottom-nav__item${isActive ? ' active' : ''}`}
      >
        <SplitIcon />
        <span>Splits</span>
      </NavLink>
    </nav>
  );
}

function HomeIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1v-9Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/></svg>;
}
function WalletIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="6" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.8"/><path d="M3 10h18" stroke="currentColor" strokeWidth="1.8"/><circle cx="16" cy="14" r="1.2" fill="currentColor"/></svg>;
}
function PlusIcon() {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/></svg>;
}
function TargetIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.8"/><circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8"/><circle cx="12" cy="12" r="1" fill="currentColor"/></svg>;
}
function UserIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8"/><path d="M4.5 20c1.5-4 5-5.5 7.5-5.5s6 1.5 7.5 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>;
}
function LockIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.8"/><path d="M8 11V8a4 4 0 0 1 8 0v3" stroke="currentColor" strokeWidth="1.8"/></svg>;
}
function PeopleIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="8.5" cy="8" r="3" stroke="currentColor" strokeWidth="1.8"/><circle cx="17" cy="9" r="2.2" stroke="currentColor" strokeWidth="1.8"/><path d="M2.5 20c1.2-3.6 4-5.2 6-5.2s4.8 1.6 6 5.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/><path d="M14.5 15.2c2.4.3 4.3 1.8 5.2 4.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>;
}
function SplitIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 7h13M16 7l-3-3M16 7l-3 3M21 17H8M8 17l3-3M8 17l3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

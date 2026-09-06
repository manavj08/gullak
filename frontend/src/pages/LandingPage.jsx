import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import GullakMark from '../components/GullakMark';
import { Button, Spinner } from '../components/ui';
import './LandingPage.css';

const FEATURES = [
  {
    title: 'Block & unblock savings',
    body: 'Move money into your Gullak with one tap. It stays protected from everyday spending, but a real emergency is always one unblock away.',
    icon: LockIcon,
  },
  {
    title: 'Goals',
    body: 'Split your Gullak across the things you\u2019re saving for, track progress, and get a smart suggestion for how to split new deposits based on urgency.',
    icon: TargetIcon,
  },
  {
    title: 'Shared accounts',
    body: 'Save with a partner in a simple two-person account, or pool money with family and friends for a trip, gift, or event \u2014 with an admin to manage members.',
    icon: PeopleIcon,
  },
  {
    title: 'Streaks',
    body: 'Build a daily habit of checking in on your money. See your streak grow the more consistent you are.',
    icon: FlameIcon,
  },
  {
    title: 'Notifications',
    body: 'Invites, admin changes, and account activity land in one place, so nothing about a shared account happens without you knowing.',
    icon: BellIcon,
  },
  {
    title: 'Private by design',
    body: 'In a shared or group account, you always see your own contribution in full. Everyone else\u2019s is only ever shown as a combined total.',
    icon: ShieldIcon,
  },
];

export default function LandingPage() {
  const { user, loading, locked } = useAuth();

  if (loading) return <Spinner label="Loading" />;
  // Already-authenticated users skip the marketing page entirely.
  if (user) return <Navigate to={locked && user.has_mpin ? '/unlock' : '/home'} replace />;

  return (
    <div className="landing">
      <header className="landing-hero">
        <nav className="landing-nav">
          <div className="landing-brand">
            <GullakMark size={30} />
            <span>Gullak</span>
          </div>
          <div className="landing-nav__links">
            <Link to="/login" className="landing-nav__link">Sign in</Link>
            <Link to="/register"><Button size="sm">Get started</Button></Link>
          </div>
        </nav>

        <div className="landing-hero__content">
          <h1>Save on your own. <br />Save together.</h1>
          <p>
            Gullak helps you set aside money without losing access to it in an emergency,
            hit your goals faster, and now, save toward something with the people who matter \u2014
            a partner, family, or friends.
          </p>
          <div className="landing-hero__cta">
            <Link to="/register"><Button size="lg">Create free account</Button></Link>
            <Link to="/login"><Button size="lg" variant="secondary">I already have an account</Button></Link>
          </div>
        </div>
      </header>

      <section className="landing-features">
        <h2>Everything in one place</h2>
        <div className="landing-features__grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="landing-feature-card">
              <div className="landing-feature-card__icon"><f.icon /></div>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-footer-cta">
        <h2>Ready to start your Gullak?</h2>
        <Link to="/register"><Button size="lg">Create free account</Button></Link>
      </section>

      <footer className="landing-footer">
        <div className="landing-brand">
          <GullakMark size={20} />
          <span>Gullak</span>
        </div>
        <p>A personal and shared savings tracker. Not a bank \u2014 no real money moves through Gullak.</p>
      </footer>
    </div>
  );
}

function LockIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.8"/><path d="M8 11V8a4 4 0 0 1 8 0v3" stroke="currentColor" strokeWidth="1.8"/></svg>;
}
function TargetIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.8"/><circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8"/><circle cx="12" cy="12" r="1" fill="currentColor"/></svg>;
}
function PeopleIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><circle cx="8.5" cy="8" r="3" stroke="currentColor" strokeWidth="1.8"/><circle cx="17" cy="9" r="2.4" stroke="currentColor" strokeWidth="1.8"/><path d="M2.5 20c1.2-3.6 4-5.2 6-5.2s4.8 1.6 6 5.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/><path d="M14.5 15.2c2.6.3 4.6 1.8 5.5 4.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>;
}
function FlameIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M12 3c1 3-3 4-3 8a3 3 0 0 0 6 0c0-1.5-1-2-1-3.5 1.5 1 3 3 3 5.5a5 5 0 0 1-10 0C7 8 11 7 12 3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/></svg>;
}
function BellIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 13 6 9Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><path d="M9.5 17a2.5 2.5 0 0 0 5 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>;
}
function ShieldIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

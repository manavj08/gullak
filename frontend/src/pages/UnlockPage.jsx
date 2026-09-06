import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { verifyMpin } from '../api/endpoints';
import GullakMark from '../components/GullakMark';
import { Banner, Button } from '../components/ui';
import './AuthPages.css';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'back'];

export default function UnlockPage() {
  const { user, unlock, logout } = useAuth();
  const navigate = useNavigate();
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(false);

  const press = (key) => {
    setError('');
    if (key === 'back') return setPin(pin.slice(0, -1));
    if (key === '' || pin.length >= 6) return;
    setPin(pin + key);
  };

  const submit = async (value) => {
    setChecking(true);
    try {
      await verifyMpin(value);
      unlock();
      navigate('/home');
    } catch {
      setError('Incorrect MPIN. Try again.');
      setPin('');
    } finally {
      setChecking(false);
    }
  };

  const handleSubmit = () => {
    if (pin.length >= 4) submit(pin);
  };

  const useFullLogin = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand"><GullakMark size={40} /><h1>Welcome back</h1></div>
        <p className="auth-tagline">{user?.username ? `Hi ${user.username}, enter` : 'Enter'} your MPIN to continue.</p>

        {error && <Banner tone="warn">{error}</Banner>}

        <div className="mpin-dots" aria-live="polite">
          {Array.from({ length: Math.max(pin.length, 4) }).map((_, i) => (
            <span key={i} className={`mpin-dot${i < pin.length ? ' filled' : ''}`} />
          ))}
        </div>

        <div className="mpin-keypad">
          {KEYS.map((k, i) => (
            <button
              key={i}
              type="button"
              className={`mpin-key${k === '' ? ' mpin-key--ghost' : ''}`}
              onClick={() => press(k)}
              disabled={k === '' || checking}
              aria-label={k === 'back' ? 'Backspace' : k}
            >
              {k === 'back' ? '⌫' : k}
            </button>
          ))}
        </div>

        <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Button size="lg" onClick={handleSubmit} disabled={pin.length < 4 || checking}>
            {checking ? 'Checking…' : 'Unlock'}
          </Button>
          <Button variant="ghost" size="lg" onClick={useFullLogin}>Use password instead</Button>
        </div>
      </div>
    </div>
  );
}

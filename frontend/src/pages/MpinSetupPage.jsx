import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { setMpin } from '../api/endpoints';
import GullakMark from '../components/GullakMark';
import { Banner, Button } from '../components/ui';
import './AuthPages.css';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'back'];

export default function MpinSetupPage() {
  const navigate = useNavigate();
  const [stage, setStage] = useState('create'); // create -> confirm
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const current = stage === 'create' ? pin : confirmPin;
  const setCurrent = stage === 'create' ? setPin : setConfirmPin;

  const press = (key) => {
    setError('');
    if (key === 'back') return setCurrent(current.slice(0, -1));
    if (key === '' || current.length >= 6) return;
    const next = current + key;
    setCurrent(next);
    if (next.length === 4 || next.length === 6) {
      // Auto-advance once a plausible pin length is reached; user can add up to 6 digits.
    }
  };

  const handleContinue = async () => {
    if (stage === 'create') {
      if (pin.length < 4) return setError('MPIN must be at least 4 digits.');
      setStage('confirm');
      return;
    }
    if (confirmPin !== pin) {
      setError('MPINs do not match. Try again.');
      setConfirmPin('');
      return;
    }
    setSaving(true);
    try {
      await setMpin(pin);
      navigate('/home');
    } catch (err) {
      setError(err.response?.data?.mpin?.[0] || 'Could not set MPIN.');
    } finally {
      setSaving(false);
    }
  };

  const skip = () => navigate('/home');

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand"><GullakMark size={40} /><h1>Set up MPIN</h1></div>
        <p className="auth-tagline">
          {stage === 'create'
            ? 'Choose a 4–6 digit MPIN for quick unlock.'
            : 'Enter your MPIN again to confirm.'}
        </p>

        {error && <Banner tone="warn">{error}</Banner>}

        <div className="mpin-dots" aria-live="polite">
          {Array.from({ length: Math.max(current.length, 4) }).map((_, i) => (
            <span key={i} className={`mpin-dot${i < current.length ? ' filled' : ''}`} />
          ))}
        </div>

        <div className="mpin-keypad">
          {KEYS.map((k, i) => (
            <button
              key={i}
              type="button"
              className={`mpin-key${k === '' ? ' mpin-key--ghost' : ''}`}
              onClick={() => press(k)}
              disabled={k === ''}
              aria-label={k === 'back' ? 'Backspace' : k}
            >
              {k === 'back' ? '⌫' : k}
            </button>
          ))}
        </div>

        <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Button size="lg" onClick={handleContinue} disabled={current.length < 4 || saving}>
            {saving ? 'Saving…' : stage === 'create' ? 'Continue' : 'Confirm MPIN'}
          </Button>
          <Button variant="ghost" size="lg" onClick={skip}>Skip for now</Button>
        </div>
      </div>
    </div>
  );
}

import { Link } from 'react-router-dom';
import GullakMark from '../components/GullakMark';
import { Button } from '../components/ui';

export default function NotFoundPage() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16, padding: 24, textAlign: 'center' }}>
      <GullakMark size={56} />
      <h1 style={{ fontSize: '1.3rem' }}>Page not found</h1>
      <p style={{ color: 'var(--color-ink-muted)', maxWidth: 320 }}>
        The page you're looking for doesn't exist or may have moved.
      </p>
      <Link to="/home"><Button>Back to home</Button></Link>
    </div>
  );
}

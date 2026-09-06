import { useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { saveSplitUpiId } from '../../../api/endpoints';
import { Card, Field, Input, Button, Banner } from '../../../components/ui';
import './SplitSettingsPage.css';

export default function SplitSettingsPage() {
  const { user, refreshUser } = useAuth();
  const [upiId, setUpiId] = useState(user.upi_id || '');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSaved(false); setSubmitting(true);
    try {
      await saveSplitUpiId(upiId.trim());
      await refreshUser();
      setSaved(true);
    } catch (err) {
      setError(err.response?.data?.upi_id || 'Could not save your UPI ID.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="split-settings">
      <p className="page-subtitle">Used to build your "Pay via UPI" link and QR code in settlements.</p>
      <Card>
        {error && <Banner tone="warn">{error}</Banner>}
        {saved && <Banner tone="success">UPI ID saved.</Banner>}
        <form onSubmit={handleSubmit}>
          <Field label="UPI ID" htmlFor="split_upi_id" hint="e.g. yourname@okhdfcbank">
            <Input
              id="split_upi_id" value={upiId} onChange={(e) => setUpiId(e.target.value)}
              placeholder="manav@upi" required
            />
          </Field>
          <Button type="submit" disabled={submitting || !upiId.trim()}>
            {submitting ? 'Saving…' : 'Save'}
          </Button>
        </form>
      </Card>
    </div>
  );
}

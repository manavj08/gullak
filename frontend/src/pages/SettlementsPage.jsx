import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchSharedAccountDetail, fetchSettlements, generateSettlements, markSettlementPaid } from '../api/endpoints';
import { formatMoneyPrecise } from '../utils/money';
import { useAuth } from '../context/AuthContext';
import { Card, Button, Banner, Spinner, EmptyState } from '../components/ui';
import './SettlementsPage.css';

export default function SettlementsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [account, setAccount] = useState(null);
  const [settlements, setSettlements] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [detailRes, settlementsRes] = await Promise.all([
      fetchSharedAccountDetail(id), fetchSettlements(id),
    ]);
    setAccount(detailRes.data.account);
    setSettlements(settlementsRes.data);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!settlements || !account) return <Spinner label="Loading settlements" />;

  const pending = settlements.filter((s) => s.status === 'pending');
  const paid = settlements.filter((s) => s.status === 'paid');

  const handleGenerate = async () => {
    setError(''); setMessage(''); setBusy(true);
    try {
      await generateSettlements(id);
      await load();
      setMessage('Settlements recalculated from current expenses.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not generate settlements.');
    } finally { setBusy(false); }
  };

  const handleMarkPaid = async (settlementId) => {
    setError(''); setBusy(true);
    try {
      await markSettlementPaid(id, settlementId);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Only the person owed money can confirm payment.');
    } finally { setBusy(false); }
  };

  return (
    <div className="settlements">
      <p className="page-subtitle" style={{ marginBottom: 4 }}>{account.name}</p>
      <div className="settlements__head">
        <Link to={`/shared-accounts/${id}/expenses`} className="settlements__back-link">← Group expenses</Link>
      </div>

      {error && <Banner tone="warn">{error}</Banner>}
      {message && <Banner tone="success">{message}</Banner>}

      <Button onClick={handleGenerate} disabled={busy} className="settlements__generate-btn">
        {busy ? 'Calculating…' : 'Recalculate settlements'}
      </Button>
      <p className="settlements__hint">
        Recalculates the minimum set of payments needed to settle all logged expenses. Safe to run any time —
        already-confirmed payments are kept as history.
      </p>

      <h2 className="settlements__section-title">Pending</h2>
      {pending.length === 0 ? (
        <EmptyState title="All settled up" message="No pending payments right now." />
      ) : (
        <div className="settlements__list">
          {pending.map((s) => {
            const youOwe = s.payer.id === user.id;
            const youAreOwed = s.payee.id === user.id;
            return (
              <Card key={s.id} className="settlements__row">
                <div>
                  <p className="settlements__desc">
                    <strong>{s.payer.username}{youOwe && ' (you)'}</strong> owes{' '}
                    <strong>{s.payee.username}{youAreOwed && ' (you)'}</strong>
                  </p>
                  <p className="settlements__amount">{formatMoneyPrecise(s.amount)}</p>
                </div>
                <div className="settlements__row-actions">
                  {youOwe && s.upi_link && (
                    <a href={s.upi_link} className="settlements__pay-btn">Pay via UPI</a>
                  )}
                  {youOwe && !s.upi_link && (
                    <p className="settlements__no-upi">{s.payee.username} hasn't added a UPI ID yet.</p>
                  )}
                  {youAreOwed && (
                    <Button size="sm" onClick={() => handleMarkPaid(s.id)} disabled={busy}>
                      Confirm received
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {paid.length > 0 && (
        <>
          <h2 className="settlements__section-title">Settled</h2>
          <div className="settlements__list">
            {paid.map((s) => (
              <Card key={s.id} className="settlements__row settlements__row--paid">
                <div>
                  <p className="settlements__desc">
                    {s.payer.username} paid {s.payee.username}
                  </p>
                  <p className="settlements__amount settlements__amount--paid">{formatMoneyPrecise(s.amount)}</p>
                </div>
                <span className="settlements__paid-badge">Paid</span>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

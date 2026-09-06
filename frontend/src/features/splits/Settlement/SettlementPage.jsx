import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  fetchSplitGroupDetail, fetchSplitExpenses, fetchSplitSettlements,
  recalculateSplitSettlements, markSplitSettlementPaid, fetchSplitSettlementPaymentInfo,
} from '../../../api/endpoints';
import { formatMoneyPrecise } from '../../../utils/money';
import { useAuth } from '../../../context/AuthContext';
import { Card, Button, Banner, Spinner, EmptyState } from '../../../components/ui';
import { buildPairwiseCalculation, buildOverallNet } from '../shared/splitMath';
import QrCode from '../shared/QrCode';
import './SettlementPage.css';

export default function SettlementPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [group, setGroup] = useState(null);
  const [expenses, setExpenses] = useState(null);
  const [settlements, setSettlements] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [groupRes, expensesRes, settlementsRes] = await Promise.all([
      fetchSplitGroupDetail(id), fetchSplitExpenses(id), fetchSplitSettlements(id),
    ]);
    setGroup(groupRes.data);
    setExpenses(expensesRes.data);
    setSettlements(settlementsRes.data);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!group || !expenses || !settlements) return <Spinner label="Loading settlement" />;

  const pending = settlements.filter((s) => s.status === 'pending');
  const paid = settlements.filter((s) => s.status === 'paid');

  const handleRecalculate = async () => {
    setError(''); setMessage(''); setBusy(true);
    try {
      await recalculateSplitSettlements(id);
      await load();
      setMessage('Settlements recalculated from current expenses.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not recalculate settlements.');
    } finally { setBusy(false); }
  };

  const handleMarkPaid = async (settlementId) => {
    setError(''); setBusy(true);
    try {
      await markSplitSettlementPaid(id, settlementId);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Only the person owed money can confirm payment.');
    } finally { setBusy(false); }
  };

  return (
    <div className="settlement-page">
      <p className="page-subtitle">{group.name}</p>
      <Link to={`/splits/${id}`} className="settlement-page__back-link">← Group detail</Link>

      {error && <Banner tone="warn">{error}</Banner>}
      {message && <Banner tone="success">{message}</Banner>}

      <Button onClick={handleRecalculate} disabled={busy} className="settlement-page__recalc-btn">
        {busy ? 'Calculating…' : 'Recalculate settlements'}
      </Button>

      <h2 className="settlement-page__section-title">Settlement</h2>
      {pending.length === 0 ? (
        <EmptyState title="All settled up" message="No pending payments right now." />
      ) : (
        <div className="settlement-page__list">
          {pending.map((s) => (
            <SettlementCard
              key={s.id} settlement={s} groupId={id} group={group} expenses={expenses}
              currentUserId={user.id} busy={busy} onMarkPaid={() => handleMarkPaid(s.id)}
            />
          ))}
        </div>
      )}

      {paid.length > 0 && (
        <>
          <h2 className="settlement-page__section-title">Settled</h2>
          <div className="settlement-page__list">
            {paid.map((s) => (
              <Card key={s.id} className="settlement-card settlement-card--paid">
                <p className="settlement-card__pair">{s.payer.username} paid {s.payee.username}</p>
                <p className="settlement-card__amount">{formatMoneyPrecise(s.amount)}</p>
                <span className="settlement-card__paid-badge">Paid</span>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function SettlementCard({ settlement, groupId, group, expenses, currentUserId, busy, onMarkPaid }) {
  const [showCalc, setShowCalc] = useState(false);
  const [showQr, setShowQr] = useState(false);
  const [paymentInfo, setPaymentInfo] = useState(null);
  const [payError, setPayError] = useState('');
  const [loadingPayInfo, setLoadingPayInfo] = useState(false);

  const youOwe = settlement.payer.id === currentUserId;
  const youAreOwed = settlement.payee.id === currentUserId;

  const ensurePaymentInfo = async () => {
    if (paymentInfo) return paymentInfo;
    setLoadingPayInfo(true); setPayError('');
    try {
      const { data } = await fetchSplitSettlementPaymentInfo(groupId, settlement.id);
      setPaymentInfo(data);
      return data;
    } catch {
      setPayError("Couldn't load payment info.");
      return null;
    } finally {
      setLoadingPayInfo(false);
    }
  };

  const handlePayViaUpi = async () => {
    const info = await ensurePaymentInfo();
    if (info?.upi_link) window.location.href = info.upi_link;
  };

  const handleToggleQr = async () => {
    if (!showQr) await ensurePaymentInfo();
    setShowQr((v) => !v);
  };

  const calcLines = group.settlement_mode === 'pairwise'
    ? buildPairwiseCalculation(expenses, settlement.payer.id, settlement.payee.id)
    : null;
  const payerNet = group.settlement_mode === 'global' ? buildOverallNet(expenses, settlement.payer.id) : null;
  const payeeNet = group.settlement_mode === 'global' ? buildOverallNet(expenses, settlement.payee.id) : null;

  return (
    <Card className="settlement-card">
      <p className="settlement-card__pair">
        <strong>{settlement.payer.username}{youOwe && ' (you)'}</strong> pays{' '}
        <strong>{settlement.payee.username}{youAreOwed && ' (you)'}</strong>
      </p>
      <p className="settlement-card__amount">{formatMoneyPrecise(settlement.amount)}</p>

      <div className="settlement-card__actions">
        {youOwe && (
          <Button size="sm" onClick={handlePayViaUpi} disabled={loadingPayInfo}>Pay via UPI</Button>
        )}
        <Button size="sm" variant="secondary" onClick={handleToggleQr} disabled={loadingPayInfo}>
          {showQr ? 'Hide QR' : 'QR'}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setShowCalc((v) => !v)}>
          {showCalc ? 'Hide Calculation' : 'Show Calculation'}
        </Button>
        {youAreOwed && (
          <Button size="sm" variant="success" onClick={onMarkPaid} disabled={busy}>Mark as Paid</Button>
        )}
      </div>

      {payError && <p className="settlement-card__pay-error">{payError}</p>}

      {showQr && (
        <div className="settlement-card__qr">
          {paymentInfo?.upi_link ? (
            <QrCode value={paymentInfo.upi_link} size={180} />
          ) : (
            <p className="settlement-card__no-upi">
              {loadingPayInfo ? 'Loading…' : `${settlement.payee.username} hasn't added a UPI ID yet.`}
            </p>
          )}
        </div>
      )}

      {showCalc && (
        <div className="settlement-card__calc">
          {group.settlement_mode === 'pairwise' ? (
            calcLines.length === 0 ? (
              <p className="settlement-card__calc-note">No direct expenses found between these two members.</p>
            ) : (
              <>
                {calcLines.map((line) => (
                  <p key={line.id} className="settlement-card__calc-row">
                    <span>{line.description} ({line.date})</span>
                    <span>
                      {line.owedByPayer
                        ? `${settlement.payer.username} owes ${formatMoneyPrecise(line.amount)}`
                        : `${settlement.payee.username} owes ${formatMoneyPrecise(line.amount)}`}
                    </span>
                  </p>
                ))}
                <p className="settlement-card__calc-note">Net direct balance between these two members.</p>
              </>
            )
          ) : (
            <>
              <p className="settlement-card__calc-row">
                <span>{settlement.payer.username}: paid {formatMoneyPrecise(payerNet.paid)}, owes {formatMoneyPrecise(payerNet.share)}</span>
                <span>net {formatMoneyPrecise(payerNet.net)}</span>
              </p>
              <p className="settlement-card__calc-row">
                <span>{settlement.payee.username}: paid {formatMoneyPrecise(payeeNet.paid)}, owes {formatMoneyPrecise(payeeNet.share)}</span>
                <span>net {formatMoneyPrecise(payeeNet.net)}</span>
              </p>
              <p className="settlement-card__calc-note">
                This group uses fewest-payments mode: the amount above is a simplified group-wide settlement,
                not necessarily tied to a single expense between these two people.
              </p>
            </>
          )}
        </div>
      )}
    </Card>
  );
}

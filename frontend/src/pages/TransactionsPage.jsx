import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchTransactions, exportTransactionsCsv } from '../api/endpoints';
import { formatMoney, categoryLabel } from '../utils/money';
import { Card, Spinner, EmptyState, Button, Banner } from '../components/ui';
import GullakMark from '../components/GullakMark';
import './TransactionsPage.css';

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'income', label: 'Income' },
  { value: 'expense', label: 'Expense' },
  { value: 'lend', label: 'Lend' },
  { value: 'borrow', label: 'Borrow' },
  { value: 'transfer', label: 'Transfer' },
];

export default function TransactionsPage() {
  const navigate = useNavigate();
  const [txns, setTxns] = useState(null);
  const [filter, setFilter] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const load = (type) => {
    setTxns(null);
    const params = { ordering: '-timestamp' };
    if (type) params.type = type;
    fetchTransactions(params).then((res) => {
      setTxns(res.data.results ?? res.data);
    });
  };

  useEffect(() => { load(filter); }, [filter]);

  const handleExport = async () => {
    setExportError(''); setExporting(true);
    try {
      const params = {};
      if (filter) params.type = filter;
      const response = await exportTransactionsCsv(params);
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = url;
      const match = /filename="(.+)"/.exec(response.headers['content-disposition'] || '');
      link.download = match ? match[1] : 'gullak_transactions.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setExportError('Could not export transactions. Try again.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="transactions-page">
      <div className="filter-row" role="group" aria-label="Filter by transaction type">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            className={`filter-chip${filter === f.value ? ' active' : ''}`}
            onClick={() => setFilter(f.value)}
            aria-pressed={filter === f.value}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="transactions-page__actions">
        <Button variant="secondary" size="sm" onClick={handleExport} disabled={exporting || txns === null}>
          {exporting ? 'Exporting…' : 'Export CSV'}
        </Button>
      </div>

      {exportError && <Banner tone="warn">{exportError}</Banner>}

      {txns === null ? (
        <Spinner label="Loading transactions" />
      ) : txns.length === 0 ? (
        <EmptyState
          icon={<GullakMark size={56} />}
          title="No transactions"
          message={filter ? `No ${filter} transactions yet.` : 'Nothing logged yet — add your first transaction.'}
          action={<Button onClick={() => navigate('/add')}>Add transaction</Button>}
        />
      ) : (
        <Card className="txn-list">
          {txns.map((t) => (
            <div className="txn-row" key={t.id}>
              <div>
                <p className="txn-row__note">{t.note || categoryLabel(t.category)}</p>
                <p className="txn-row__meta">
                  <span className={`txn-type-badge txn-type-badge--${t.type}`}>{t.type}</span>
                  {' · '}{new Date(t.timestamp).toLocaleDateString()}
                  {t.type === 'lend' || t.type === 'borrow' ? (t.settled ? ' · Settled' : ' · Unsettled') : ''}
                </p>
              </div>
              <p className={`txn-row__amount txn-row__amount--${signClass(t.type)}`}>
                {sign(t.type)}{formatMoney(t.amount)}
              </p>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

function sign(type) {
  return ['income', 'borrow'].includes(type) ? '+' : ['expense', 'lend'].includes(type) ? '−' : '';
}
function signClass(type) {
  return ['income', 'borrow'].includes(type) ? 'positive' : ['expense', 'lend'].includes(type) ? 'negative' : 'neutral';
}

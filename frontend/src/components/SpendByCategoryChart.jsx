import { useEffect, useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';
import { fetchSpendByCategory } from '../api/endpoints';
import { formatMoney, formatMoneyPrecise } from '../utils/money';
import { Card, Spinner, Banner } from './ui';
import './SpendByCategoryChart.css';

// One consistent color per category, cycling if more categories appear later.
const PALETTE = ['#2C5F8A', '#1F8A5F', '#C0552E', '#8A5FA6', '#A67C1F', '#5C6A64'];

export default function SpendByCategoryChart() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSpendByCategory(30)
      .then(({ data: rows }) => setData(rows.map((r) => ({ category: r.category, amount: Number(r.amount) }))))
      .catch(() => { setError('Could not load spend by category.'); setData([]); });
  }, []);

  const total = data ? data.reduce((sum, r) => sum + r.amount, 0) : 0;

  return (
    <Card className="spend-category-chart">
      <div className="spend-category-chart__head">
        <p className="spend-category-chart__title">Spend by Category</p>
        <p className="spend-category-chart__sub">Last 30 days</p>
      </div>

      {error && <Banner tone="warn">{error}</Banner>}

      {data === null ? (
        <Spinner label="Loading spend by category" />
      ) : data.length === 0 ? (
        <p className="spend-category-chart__empty">No expenses logged in the last 30 days.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={Math.max(120, data.length * 34)}>
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis
                type="category" dataKey="category" width={90}
                tick={{ fontSize: 12, fill: '#1E2A28' }} tickLine={false} axisLine={false}
              />
              <Tooltip
                formatter={(value) => [formatMoneyPrecise(value), 'Spent']}
                contentStyle={{ borderRadius: 10, borderColor: '#E8E2D3', fontSize: 13 }}
                cursor={{ fill: '#F3EEE2' }}
              />
              <Bar dataKey="amount" radius={[0, 6, 6, 0]} barSize={18}>
                {data.map((entry, i) => (
                  <Cell key={entry.category} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="spend-category-chart__total">Total: {formatMoney(total)}</p>
        </>
      )}
    </Card>
  );
}

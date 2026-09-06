import { useEffect, useState } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
import { fetchNetWorthHistory } from '../api/endpoints';
import { formatMoney, formatMoneyPrecise } from '../utils/money';
import { Card, Spinner, Banner } from './ui';
import './NetWorthChart.css';

const RANGE_OPTIONS = [
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: '1y', days: 365 },
];

export default function NetWorthChart() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setData(null);
    fetchNetWorthHistory(days)
      .then(({ data: rows }) => {
        if (cancelled) return;
        setData(rows.map((r) => ({ date: r.date, net_worth: Number(r.net_worth) })));
      })
      .catch(() => { if (!cancelled) { setError('Could not load net worth history.'); setData([]); } });
    return () => { cancelled = true; };
  }, [days]);

  const trend = data && data.length >= 2 ? data[data.length - 1].net_worth - data[0].net_worth : 0;

  return (
    <Card className="net-worth-chart">
      <div className="net-worth-chart__head">
        <div>
          <p className="net-worth-chart__title">Net Worth</p>
          {data && data.length > 0 && (
            <p className="net-worth-chart__current">
              {formatMoney(data[data.length - 1].net_worth)}
              {data.length >= 2 && (
                <span className={`net-worth-chart__trend net-worth-chart__trend--${trend >= 0 ? 'up' : 'down'}`}>
                  {trend >= 0 ? '▲' : '▼'} {formatMoney(Math.abs(trend))}
                </span>
              )}
            </p>
          )}
        </div>
        <div className="net-worth-chart__range">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days} type="button"
              className={`net-worth-chart__range-btn${days === opt.days ? ' active' : ''}`}
              onClick={() => setDays(opt.days)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error && <Banner tone="warn">{error}</Banner>}

      {data === null ? (
        <Spinner label="Loading net worth history" />
      ) : data.length === 0 ? (
        <p className="net-worth-chart__empty">Not enough history yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="netWorthFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2C5F8A" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#2C5F8A" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E8E2D3" vertical={false} />
            <XAxis
              dataKey="date" tick={{ fontSize: 11, fill: '#5C6A64' }} tickLine={false} axisLine={false}
              tickFormatter={(d) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
              minTickGap={30}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#5C6A64' }} tickLine={false} axisLine={false} width={44}
              tickFormatter={(v) => formatMoney(v)}
            />
            <Tooltip
              formatter={(value) => [formatMoneyPrecise(value), 'Net worth']}
              labelFormatter={(d) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
              contentStyle={{ borderRadius: 10, borderColor: '#E8E2D3', fontSize: 13 }}
            />
            <Area
              type="monotone" dataKey="net_worth" stroke="#2C5F8A" strokeWidth={2}
              fill="url(#netWorthFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

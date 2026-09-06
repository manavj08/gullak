import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createAccount } from '../api/endpoints';
import { toApiAmount } from '../utils/money';
import { Card, Field, Input, Select, Button, Banner } from '../components/ui';

const TYPE_SUGGESTIONS = {
  daily_transaction: ['UPI', 'Cash', 'Digital Wallet'],
  savings: ['Savings Account', 'Current Account'],
  revenue_generation: ['Fixed Deposit', 'Mutual Fund', 'Stocks'],
  loan_debt: ['Credit Card', 'Education Loan', 'Car Loan'],
};

export default function AddAccountPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState('daily_transaction');
  const [name, setName] = useState('');
  const [accountType, setAccountType] = useState(TYPE_SUGGESTIONS.daily_transaction[0]);
  const [startingBalance, setStartingBalance] = useState('');
  const [principal, setPrincipal] = useState('');
  const [currentValue, setCurrentValue] = useState('');
  const [amountOwed, setAmountOwed] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleCategoryChange = (cat) => {
    setCategory(cat);
    setAccountType(TYPE_SUGGESTIONS[cat][0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const payload = { name, category, account_type: accountType };
      if (category === 'daily_transaction' || category === 'savings') {
        payload.unblock_balance = toApiAmount(startingBalance || 0);
        payload.block_balance = '0.00';
      } else if (category === 'revenue_generation') {
        payload.principal = toApiAmount(principal || 0);
        payload.current_value = toApiAmount(currentValue || principal || 0);
      } else if (category === 'loan_debt') {
        payload.amount_owed = toApiAmount(amountOwed || 0);
      }
      const { data } = await createAccount(payload);
      navigate(`/accounts/${data.id}`);
    } catch (err) {
      const data = err.response?.data;
      const firstError = data && typeof data === 'object' ? Object.values(data)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || 'Could not create account.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: '1.3rem', marginBottom: 16 }}>Add account</h1>
      <Card>
        {error && <Banner tone="warn">{error}</Banner>}
        <form onSubmit={handleSubmit}>
          <Field label="Category" htmlFor="category">
            <Select id="category" value={category} onChange={(e) => handleCategoryChange(e.target.value)}>
              <option value="daily_transaction">Daily Transaction</option>
              <option value="savings">Savings</option>
              <option value="revenue_generation">Revenue Generation</option>
              <option value="loan_debt">Loan/Debt</option>
            </Select>
          </Field>

          <Field label="Account type" htmlFor="account_type">
            <Select id="account_type" value={accountType} onChange={(e) => setAccountType(e.target.value)}>
              {TYPE_SUGGESTIONS[category].map((t) => <option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>

          <Field label="Name" htmlFor="name" hint="e.g. PhonePe UPI, SBI Savings">
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </Field>

          {(category === 'daily_transaction' || category === 'savings') && (
            <Field label="Starting balance (₹)" htmlFor="starting_balance">
              <Input id="starting_balance" type="number" min="0" step="0.01" value={startingBalance}
                onChange={(e) => setStartingBalance(e.target.value)} />
            </Field>
          )}

          {category === 'revenue_generation' && (
            <>
              <Field label="Principal invested (₹)" htmlFor="principal">
                <Input id="principal" type="number" min="0" step="0.01" value={principal}
                  onChange={(e) => setPrincipal(e.target.value)} />
              </Field>
              <Field label="Current value (₹)" htmlFor="current_value" hint="Leave blank to match principal.">
                <Input id="current_value" type="number" min="0" step="0.01" value={currentValue}
                  onChange={(e) => setCurrentValue(e.target.value)} />
              </Field>
            </>
          )}

          {category === 'loan_debt' && (
            <Field label="Amount owed (₹)" htmlFor="amount_owed">
              <Input id="amount_owed" type="number" min="0" step="0.01" value={amountOwed}
                onChange={(e) => setAmountOwed(e.target.value)} />
            </Field>
          )}

          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? 'Adding…' : 'Add account'}
          </Button>
        </form>
      </Card>
    </div>
  );
}

// Money is Decimal rupees end-to-end (backend returns/accepts decimal strings like "1234.50").
// No paise conversion anywhere — keep amounts as strings/numbers with at most 2 decimal places.

export function formatMoney(amount) {
  const num = Number(amount ?? 0);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num);
}

export function formatMoneyPrecise(amount) {
  const num = Number(amount ?? 0);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(num);
}

// Normalizes a raw text-input value into a clean 2-decimal string for the API.
// e.g. "45.5" -> "45.50", "" -> "0.00"
export function toApiAmount(value) {
  const num = parseFloat(value || 0);
  if (Number.isNaN(num)) return '0.00';
  return num.toFixed(2);
}

export function todayLocalISO() {
  const d = new Date();
  const offset = d.getTimezoneOffset();
  const local = new Date(d.getTime() - offset * 60000);
  return local.toISOString().slice(0, 10);
}

export function categoryLabel(cat) {
  const map = {
    food: 'Food', transport: 'Transport', bills: 'Bills',
    shopping: 'Shopping', other: 'Other', uncategorized: 'Uncategorized',
  };
  return map[cat] || cat;
}

export function accountCategoryLabel(cat) {
  const map = {
    gullak: 'Gullak', daily_transaction: 'Daily Transaction', savings: 'Savings',
    revenue_generation: 'Revenue Generation', loan_debt: 'Loan/Debt',
  };
  return map[cat] || cat;
}

export function expenseCategoryLabel(cat) {
  const map = {
    food: 'Food', travel: 'Travel', accommodation: 'Accommodation', shopping: 'Shopping',
    entertainment: 'Entertainment', utilities: 'Utilities', other: 'Other',
  };
  return map[cat] || cat;
}

// Client-side mirrors of the backend split math (splits/services.py), used
// only for a live preview before submit. The backend re-validates and
// recomputes everything server-side with Decimal — this never has the final say.

export function previewEqualShares(amount, participantIds) {
  const amt = Number(amount) || 0;
  const n = participantIds.length;
  if (n === 0) return {};
  const totalCents = Math.round(amt * 100);
  const baseCents = Math.floor(totalCents / n);
  const remainderCents = totalCents - baseCents * n;
  const ordered = [...participantIds].sort((a, b) => a - b);
  const shares = {};
  ordered.forEach((uid, i) => {
    shares[uid] = (baseCents + (i < remainderCents ? 1 : 0)) / 100;
  });
  return shares;
}

export function previewPercentageShares(amount, percentages) {
  const amt = Number(amount) || 0;
  const ids = Object.keys(percentages).map(Number).sort((a, b) => a - b);
  const rawCents = {};
  ids.forEach((uid) => {
    rawCents[uid] = Math.floor((amt * (Number(percentages[uid]) || 0) * 100) / 100);
  });
  const totalCents = Math.round(amt * 100);
  const rawTotal = ids.reduce((sum, uid) => sum + rawCents[uid], 0);
  const remainderCents = totalCents - rawTotal;
  const shares = {};
  ids.forEach((uid, i) => {
    shares[uid] = (rawCents[uid] + (i < remainderCents ? 1 : 0)) / 100;
  });
  return shares;
}

export function sumValues(obj) {
  return Object.values(obj).reduce((sum, v) => sum + (Number(v) || 0), 0);
}

// PAIRWISE settlements are literally the net of direct expenses between two
// people, so we can list exactly which expenses produced the balance.
export function buildPairwiseCalculation(expenses, payerId, payeeId) {
  const lines = [];
  expenses.forEach((exp) => {
    const paidById = exp.paid_by.id;
    if (paidById !== payerId && paidById !== payeeId) return;
    const other = paidById === payerId ? payeeId : payerId;
    const otherShare = exp.shares.find((s) => s.user.id === other);
    if (!otherShare || Number(otherShare.share_amount) === 0) return;
    lines.push({
      id: exp.id,
      description: exp.description,
      date: exp.expense_date,
      owedByPayer: paidById === payeeId, // true if this line adds to what payer owes payee
      amount: Number(otherShare.share_amount),
    });
  });
  return lines;
}

// GLOBAL settlements are a simplified, group-wide result (a debt can be
// routed through a third person), so instead we show each person's overall
// net position across the whole group's expenses.
export function buildOverallNet(expenses, userId) {
  let paid = 0;
  let share = 0;
  expenses.forEach((exp) => {
    if (exp.paid_by.id === userId) paid += Number(exp.amount);
    const mine = exp.shares.find((s) => s.user.id === userId);
    if (mine) share += Number(mine.share_amount);
  });
  return { paid, share, net: paid - share };
}

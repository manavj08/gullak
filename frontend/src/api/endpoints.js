import api from './client';

// ---- Auth ----
export const registerUser = (data) => api.post('/auth/register/', data);
export const loginUser = (data) => api.post('/auth/login/', data);
export const logoutUser = (refresh) => api.post('/auth/logout/', { refresh });
export const fetchMe = () => api.get('/auth/me/');
export const updateMe = (data) => api.patch('/auth/me/', data);
export const setMpin = (mpin) => api.post('/auth/mpin/set/', { mpin });
export const verifyMpin = (mpin) => api.post('/auth/mpin/verify/', { mpin });
export const changePassword = (data) => api.post('/auth/password/change/', data);
export const requestPasswordReset = (email) => api.post('/auth/password/reset/', { email });
export const confirmPasswordReset = (data) => api.post('/auth/password/reset/confirm/', data);

// ---- Wallet: Accounts ----
export const fetchAccounts = (params) => api.get('/wallet/accounts/', { params });
export const fetchAccount = (id) => api.get(`/wallet/accounts/${id}/`);
export const createAccount = (data) => api.post('/wallet/accounts/', data);
export const updateAccount = (id, data) => api.patch(`/wallet/accounts/${id}/`, data);
export const deleteAccount = (id) => api.delete(`/wallet/accounts/${id}/`);
export const blockFunds = (id, amount, client_request_id) =>
  api.post(`/wallet/accounts/${id}/block/`, { amount, client_request_id });
export const emergencyUnblock = (id, amount, client_request_id) =>
  api.post(`/wallet/accounts/${id}/emergency-unblock/`, { amount, client_request_id });

// ---- Wallet: Transactions ----
// include_gullak=true is used only by the Gullak account detail page.
export const fetchTransactions = (params) => api.get('/wallet/transactions/', { params });
export const exportTransactionsCsv = (params) =>
  api.get('/wallet/transactions/export/', { params, responseType: 'blob' });
export const createTransaction = (data) => api.post('/wallet/transactions/create/', data);
export const createTransfer = (data) => api.post('/wallet/transactions/transfer/', data);
export const settleTransaction = (id, settled) => api.patch(`/wallet/transactions/${id}/settle/`, { settled });

// ---- Gullak ----
export const fetchGullakSummary = () => api.get('/wallet/gullak/');
export const fetchNetWorthHistory = (days = 30) => api.get('/wallet/analytics/net-worth-history/', { params: { days } });
export const fetchSpendByCategory = (days = 30) => api.get('/wallet/analytics/spend-by-category/', { params: { days } });

// ---- Goals ----
export const fetchGoals = () => api.get('/goals/');
export const createGoal = (data) => api.post('/goals/', data);
export const deleteGoal = (id) => api.delete(`/goals/${id}/`);
export const addFundsToGoal = (id, add_amount) => api.post(`/goals/${id}/add-funds/`, { add_amount });

// ---- Goals: Pending deductions (emergency-unblock overage resolution) ----
export const fetchPendingDeductions = () => api.get('/goals/pending-deductions/');
export const resolvePendingDeduction = (id, allocations) =>
  api.post(`/goals/pending-deductions/${id}/resolve/`, { allocations });

// ---- Streaks ----
export const checkIn = (date) => api.post('/streaks/check-in/', { date });
export const fetchStreakSummary = (date) => api.get('/streaks/summary/', { params: { date } });

// ---- Social (V2): Shared & Group Accounts ----
export const fetchSharedAccounts = () => api.get('/social/shared-accounts/');
export const fetchSharedAccountDetail = (id) => api.get(`/social/shared-accounts/${id}/`);
export const createSharedPair = (name) => api.post('/social/shared-accounts/pair/', { name });
export const createSharedGroup = (data) => api.post('/social/shared-accounts/group/', data);
export const contributeToShared = (id, data) => api.post(`/social/shared-accounts/${id}/contribute/`, data);
export const sharedEmergencyUnblock = (id, data) => api.post(`/social/shared-accounts/${id}/emergency-unblock/`, data);
export const sendGroupInvite = (accountId, invited_username) =>
  api.post(`/social/shared-accounts/${accountId}/invite/`, { invited_username });
export const leaveSharedAccount = (id) => api.post(`/social/shared-accounts/${id}/leave/`);
export const removeGroupMember = (accountId, username) =>
  api.post(`/social/shared-accounts/${accountId}/remove-member/`, { username });
export const requestAdminTransfer = (accountId, target_username) =>
  api.post(`/social/shared-accounts/${accountId}/request-admin-transfer/`, { target_username });
export const lookupUsername = (username) => api.get('/auth/username-lookup/', { params: { username } });

// ---- Social (V2): Invites & Admin Transfers (received) ----
export const fetchMyInvites = () => api.get('/social/invites/');
export const respondToInvite = (id, accept) => api.post(`/social/invites/${id}/respond/`, { accept });
export const respondToAdminTransfer = (id, accept) => api.post(`/social/admin-transfers/${id}/respond/`, { accept });

// ---- Social (V2): Notifications ----
export const fetchNotifications = () => api.get('/social/notifications/');
export const fetchUnreadNotificationCount = () => api.get('/social/notifications/unread-count/');

// ---- Social (V2): Smart Gullak-Split Suggestion ----
export const fetchSplitSuggestion = (new_amount, shared_account_ids = []) =>
  api.post('/social/split-suggestion/', { new_amount, shared_account_ids });
export const applySplitSuggestion = (allocations) => api.post('/social/split-suggestion/apply/', { allocations });
export const fetchMySharedAccountsForSplit = () => api.get('/social/split-suggestion/my-shared-accounts/');

// ---- Social (V2): Shared/common goal detail ----
export const fetchSharedGoalDetail = (goalId) => api.get(`/social/goals/${goalId}/`);

// ---- Expenses (V2): Group Expense Split & UPI Settlement ----
export const fetchGroupExpenses = (accountId) => api.get(`/expenses/groups/${accountId}/expenses/`);
export const logGroupExpense = (accountId, data) => api.post(`/expenses/groups/${accountId}/expenses/`, data);
export const deleteGroupExpense = (accountId, expenseId) =>
  api.delete(`/expenses/groups/${accountId}/expenses/${expenseId}/`);
export const fetchSettlements = (accountId) => api.get(`/expenses/groups/${accountId}/settlements/`);
export const generateSettlements = (accountId) => api.post(`/expenses/groups/${accountId}/settlements/generate/`);
export const markSettlementPaid = (accountId, settlementId) =>
  api.post(`/expenses/groups/${accountId}/settlements/${settlementId}/mark-paid/`);

// ---- Splits (V2.3): standalone Split Groups app — independent of wallet accounts ----
export const fetchSplitGroups = () => api.get('/splits/groups/');
export const fetchSplitGroupDetail = (groupId) => api.get(`/splits/groups/${groupId}/`);
export const createSplitGroup = (data) => api.post('/splits/groups/', data);
export const updateSplitGroupSettlementMode = (groupId, settlement_mode) =>
  api.patch(`/splits/groups/${groupId}/`, { settlement_mode });
export const addSplitGroupMember = (groupId, user_id) => api.post(`/splits/groups/${groupId}/members/`, { user_id });
export const removeSplitGroupMember = (groupId, userId) => api.delete(`/splits/groups/${groupId}/members/${userId}/`);
export const lookupSplitUser = (username) => api.get('/splits/users/lookup/', { params: { username } });

export const fetchSplitExpenses = (groupId) => api.get(`/splits/groups/${groupId}/expenses/`);
export const createSplitExpense = (groupId, data) => api.post(`/splits/groups/${groupId}/expenses/`, data);
export const deleteSplitExpense = (groupId, expenseId) => api.delete(`/splits/groups/${groupId}/expenses/${expenseId}/`);

export const fetchSplitSettlements = (groupId) => api.get(`/splits/groups/${groupId}/settlements/`);
export const recalculateSplitSettlements = (groupId) => api.post(`/splits/groups/${groupId}/settlements/recalculate/`);
export const markSplitSettlementPaid = (groupId, settlementId) =>
  api.post(`/splits/groups/${groupId}/settlements/${settlementId}/mark-paid/`);
export const fetchSplitSettlementPaymentInfo = (groupId, settlementId) =>
  api.get(`/splits/groups/${groupId}/settlements/${settlementId}/payment-info/`);
export const saveSplitUpiId = (upi_id) => api.post('/splits/upi/save/', { upi_id });

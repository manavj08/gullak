import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import MpinSetupPage from './pages/MpinSetupPage';
import UnlockPage from './pages/UnlockPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import HomePage from './pages/HomePage';
import AccountsPage from './pages/AccountsPage';
import AddAccountPage from './pages/AddAccountPage';
import AccountDetailPage from './pages/AccountDetailPage';
import AddTransactionPage from './pages/AddTransactionPage';
import TransactionsPage from './pages/TransactionsPage';
import GoalsPage from './pages/GoalsPage';
import ProfilePage from './pages/ProfilePage';
import NotFoundPage from './pages/NotFoundPage';
import NotificationsPage from './pages/NotificationsPage';
import SharedAccountsPage from './pages/SharedAccountsPage';
import CreateSharedAccountPage from './pages/CreateSharedAccountPage';
import SharedAccountDetailPage from './pages/SharedAccountDetailPage';
import SplitSuggestionPage from './pages/SplitSuggestionPage';
import SharedGoalDetailPage from './pages/SharedGoalDetailPage';
import GroupExpensesPage from './pages/GroupExpensesPage';
import SettlementsPage from './pages/SettlementsPage';
import SplitGroupsPage from './features/splits/SplitGroups/SplitGroupsPage';
import CreateGroupPage from './features/splits/CreateGroup/CreateGroupPage';
import GroupDetailPage from './features/splits/GroupDetail/GroupDetailPage';
import AddExpensePage from './features/splits/AddExpense/AddExpensePage';
import SettlementPage from './features/splits/Settlement/SettlementPage';
import SplitSettingsPage from './features/splits/SplitSettings/SplitSettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/mpin-setup" element={<MpinSetupPage />} />
          <Route path="/unlock" element={<UnlockPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/home" element={<HomePage />} />
              <Route path="/accounts" element={<AccountsPage />} />
              <Route path="/accounts/new" element={<AddAccountPage />} />
              <Route path="/accounts/:id" element={<AccountDetailPage />} />
              <Route path="/add" element={<AddTransactionPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/goals" element={<GoalsPage />} />
              <Route path="/goals/split-suggestion" element={<SplitSuggestionPage />} />
              <Route path="/goals/shared/:id" element={<SharedGoalDetailPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/shared-accounts" element={<SharedAccountsPage />} />
              <Route path="/shared-accounts/new" element={<CreateSharedAccountPage />} />
              <Route path="/shared-accounts/:id" element={<SharedAccountDetailPage />} />
              <Route path="/shared-accounts/:id/expenses" element={<GroupExpensesPage />} />
              <Route path="/shared-accounts/:id/settlements" element={<SettlementsPage />} />
              <Route path="/splits" element={<SplitGroupsPage />} />
              <Route path="/splits/new" element={<CreateGroupPage />} />
              <Route path="/splits/settings" element={<SplitSettingsPage />} />
              <Route path="/splits/:id" element={<GroupDetailPage />} />
              <Route path="/splits/:id/expenses/new" element={<AddExpensePage />} />
              <Route path="/splits/:id/settlements" element={<SettlementPage />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

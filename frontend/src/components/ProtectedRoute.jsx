import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Spinner } from './ui';

export default function ProtectedRoute() {
  const { user, loading, locked } = useAuth();

  if (loading) return <Spinner label="Checking session" />;
  if (!user) return <Navigate to="/login" replace />;
  if (locked && user.has_mpin) return <Navigate to="/unlock" replace />;

  return <Outlet />;
}

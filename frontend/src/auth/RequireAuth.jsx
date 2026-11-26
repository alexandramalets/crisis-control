import { Navigate, Outlet, useLocation, useOutletContext } from 'react-router-dom';
import LoadingState from '../components/ui/LoadingState.jsx';
import { useAuth } from './AuthContext.jsx';

export default function RequireAuth() {
  const { user, ready } = useAuth();
  const location = useLocation();
  const outletContext = useOutletContext();
  if (!ready) {
    return <LoadingState title="Проверка сеанса" />;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet context={outletContext} />;
}

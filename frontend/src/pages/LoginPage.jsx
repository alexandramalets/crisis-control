import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/httpClient.js';
import { useAuth } from '../auth/AuthContext.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import './pages.css';

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || '/';
  const [loginName, setLoginName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const profile = await login(loginName, password);
      const home = profile.role === 'admin' ? '/admin' : '/';
      const target = from && from !== '/' && from !== '/login' ? from : home;
      navigate(target, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Вход</h1>
          <p className="page__lead">
            Учётную запись выдаёт администратор.
          </p>
        </div>
      </div>
      {user ? (
        <p className="muted">Вы уже вошли как {user.full_name}. <Link to={user.role === 'admin' ? '/admin' : '/'}>К панели</Link></p>
      ) : (
        <form className="card login-form" onSubmit={onSubmit}>
          <div className="card__body form-grid">
            <label className="field">
              <span className="field__label">Логин или почта</span>
              <input className="input" value={loginName} onChange={(event) => setLoginName(event.target.value)} required autoComplete="username" />
            </label>
            <label className="field">
              <span className="field__label">Пароль</span>
              <input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" />
            </label>
          </div>
          {error ? <div className="card__body"><ErrorMessage message={error} /></div> : null}
          <div className="card__body">
            <button type="submit" className="button" disabled={pending}>{pending ? 'Вход…' : 'Войти'}</button>
            <p className="muted"><Link to="/privacy">Политика конфиденциальности</Link></p>
          </div>
        </form>
      )}
    </div>
  );
}

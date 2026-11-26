import { useEffect, useState } from 'react';
import { changePassword } from '../api/authApi.js';
import { errorMessage } from '../api/httpClient.js';
import { fetchOrganizations } from '../api/organizationsApi.js';
import { useAuth } from '../auth/AuthContext.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import './pages.css';

export default function SettingsPage() {
  const { user } = useAuth();
  const [organizations, setOrganizations] = useState([]);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [formError, setFormError] = useState(null);
  const [formInfo, setFormInfo] = useState(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    fetchOrganizations()
      .then((page) => setOrganizations(page.items || []))
      .catch((error) => setFormError(errorMessage(error)));
  }, []);

  async function onPassword(event) {
    event.preventDefault();
    if (!currentPassword || !newPassword) {
      setFormError('Заполните текущий и новый пароль.');
      return;
    }
    setPending(true);
    setFormError(null);
    setFormInfo(null);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setFormInfo('Пароль изменён. Остальные сеансы завершены.');
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  const roleLabel = { analyst: 'Аналитик', admin: 'Администратор' }[user?.role] || user?.role;

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Настройки</h1>
          <p className="page__lead">Профиль, пароль и организации.</p>
        </div>
      </div>

      {formError ? <ErrorMessage message={formError} /> : null}
      {formInfo ? <p className="muted">{formInfo}</p> : null}

      <section className="card">
        <header className="card__header"><h2 className="card__title">Профиль</h2></header>
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Пользователь</span>
            <input className="input" value={user?.full_name || ''} disabled />
          </label>
          <label className="field">
            <span className="field__label">Логин</span>
            <input className="input" value={user?.username || ''} disabled />
          </label>
          <label className="field">
            <span className="field__label">Почта</span>
            <input className="input" value={user?.email || ''} disabled />
          </label>
          <label className="field">
            <span className="field__label">Роль</span>
            <input className="input" value={roleLabel || ''} disabled />
          </label>
        </div>
      </section>

      <form className="card" onSubmit={onPassword}>
        <header className="card__header"><h2 className="card__title">Смена пароля</h2></header>
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Текущий пароль</span>
            <input className="input" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required autoComplete="current-password" />
          </label>
          <label className="field">
            <span className="field__label">Новый пароль</span>
            <input className="input" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required minLength={8} autoComplete="new-password" />
          </label>
        </div>
        <div className="card__body">
          <button type="submit" className="button" disabled={pending}>Сохранить пароль</button>
        </div>
      </form>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Организации</h2></header>
        <div className="card__body">
          {organizations.length ? (
            <ul className="help-list">
              {organizations.map((item) => <li key={item.id}><strong>{item.name}</strong></li>)}
            </ul>
          ) : <p className="muted">Организаций пока нет.</p>}
        </div>
        {user?.role === 'admin' ? (
          <p className="card__body muted">
            Создавать организации и назначать доступ удобнее в разделе «Организации» панели управления.
          </p>
        ) : (
          <p className="card__body muted">
            Показаны организации, к которым вам открыт доступ. Уровень прав задаёт администратор.
          </p>
        )}
      </section>

    </div>
  );
}

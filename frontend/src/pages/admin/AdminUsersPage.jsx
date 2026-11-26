import { useEffect, useState } from 'react';
import {
  createAdminUser, fetchAdminUsers, resetAdminUserPassword,
  unlockAdminUser, updateAdminUser,
} from '../../api/adminApi.js';
import { assignOrganizationMember, fetchOrganizations, revokeOrganizationMember } from '../../api/organizationsApi.js';
import { errorMessage } from '../../api/httpClient.js';
import ConfirmDialog from '../../components/ui/ConfirmDialog.jsx';
import DataTable from '../../components/ui/DataTable.jsx';
import ErrorMessage from '../../components/ui/ErrorMessage.jsx';
import LoadingState from '../../components/ui/LoadingState.jsx';
import { formatDateTime } from '../../lib/format.js';
import '../pages.css';

const EMPTY_FORM = {
  username: '', email: '', full_name: '', password: '', role: 'analyst',
  organization_ids: [], organization_access_level: 'view',
};

export default function AdminUsersPage() {
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [organizations, setOrganizations] = useState([]);
  const [query, setQuery] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const [info, setInfo] = useState(null);
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [passwordReset, setPasswordReset] = useState({ userId: null, password: '' });

  function load() {
    setState((current) => ({ ...current, loading: true, error: null }));
    Promise.all([fetchAdminUsers({ q: query || undefined, limit: 100 }), fetchOrganizations({ limit: 100 })])
      .then(([users, orgs]) => {
        setState({ loading: false, error: null, items: users.items || [] });
        setOrganizations(orgs.items || []);
      })
      .catch((error) => setState({ loading: false, error, items: [] }));
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(event) {
    event.preventDefault();
    setPending(true);
    setInfo(null);
    try {
      await createAdminUser({
        ...form,
        organization_ids: form.organization_ids.map(Number),
        organization_access_level: form.organization_access_level,
      });
      setForm(EMPTY_FORM);
      setInfo('Учётная запись создана. Сообщите сотруднику логин и пароль лично. Затем при необходимости выдайте право редактирования.');
      load();
    } catch (error) {
      setState((current) => ({ ...current, error }));
    } finally {
      setPending(false);
    }
  }

  async function toggleActive(user) {
    setPending(true);
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active });
      setConfirm(null);
      load();
    } catch (error) {
      setState((current) => ({ ...current, error }));
    } finally {
      setPending(false);
    }
  }

  async function onResetPassword(event) {
    event.preventDefault();
    setPending(true);
    try {
      await resetAdminUserPassword(passwordReset.userId, passwordReset.password);
      setPasswordReset({ userId: null, password: '' });
      setInfo('Пароль сброшен. Действующие сеансы сотрудника завершены.');
    } catch (error) {
      setState((current) => ({ ...current, error }));
    } finally {
      setPending(false);
    }
  }

  function toggleOrg(id) {
    setForm((current) => {
      const value = String(id);
      const selected = current.organization_ids.includes(value)
        ? current.organization_ids.filter((item) => item !== value)
        : [...current.organization_ids, value];
      return { ...current, organization_ids: selected };
    });
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Пользователи</h1>
          <p className="page__lead">Учётные записи, роли и доступ к организациям.</p>
        </div>
      </div>
      {state.error ? <ErrorMessage message={errorMessage(state.error)} onRetry={load} /> : null}
      {info ? <p className="muted">{info}</p> : null}

      <form className="card" onSubmit={onCreate}>
        <header className="card__header"><h2 className="card__title">Новая учётная запись</h2></header>
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Логин</span>
            <input className="input" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} required />
          </label>
          <label className="field">
            <span className="field__label">Почта</span>
            <input className="input" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required />
          </label>
          <label className="field">
            <span className="field__label">ФИО</span>
            <input className="input" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required />
          </label>
          <label className="field">
            <span className="field__label">Временный пароль</span>
            <input className="input" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required minLength={8} />
          </label>
          <label className="field">
            <span className="field__label">Роль</span>
            <select className="select" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
              <option value="analyst">Аналитик</option>
              <option value="admin">Администратор</option>
            </select>
          </label>
        </div>
        {organizations.length ? (
          <div className="card__body">
            <div className="field__label">Доступ к организациям</div>
            <div className="checkbox-grid">
              {organizations.map((item) => (
                <label key={item.id} className="check">
                  <input
                    type="checkbox"
                    checked={form.organization_ids.includes(String(item.id))}
                    onChange={() => toggleOrg(item.id)}
                  />
                  {item.name}
                </label>
              ))}
            </div>
            <label className="field">
              <span className="field__label">Уровень доступа к отмеченным организациям</span>
              <select
                className="select"
                value={form.organization_access_level}
                onChange={(event) => setForm({ ...form, organization_access_level: event.target.value })}
              >
                <option value="view">Просмотр</option>
                <option value="edit">Редактирование (загрузка и анализ)</option>
              </select>
            </label>
          </div>
        ) : null}
        <div className="card__body">
          <button type="submit" className="button" disabled={pending}>Создать учётную запись</button>
        </div>
      </form>

      <section className="card">
        <header className="card__header">
          <h2 className="card__title">Учётные записи</h2>
          <form onSubmit={(event) => { event.preventDefault(); load(); }}>
            <input className="input" placeholder="Поиск" value={query} onChange={(event) => setQuery(event.target.value)} />
          </form>
        </header>
        {state.loading ? <LoadingState title="Загрузка списка" /> : (
          <DataTable
            filterable
            sortable
            columns={[
              { key: 'username', title: 'Логин' },
              { key: 'full_name', title: 'Имя' },
              { key: 'role', title: 'Роль', render: (row) => (row.role === 'admin' ? 'Администратор' : 'Аналитик') },
              { key: 'is_active', title: 'Статус', render: (row) => (row.is_active ? 'Активна' : 'Заблокирована') },
              {
                key: 'organizations',
                title: 'Организации',
                render: (row) => row.organizations?.map((item) => item.name).join(', ') || '—',
              },
              { key: 'created_at', title: 'Создана', render: (row) => formatDateTime(row.created_at) },
              { key: 'last_login_at', title: 'Последний вход', render: (row) => (row.last_login_at ? formatDateTime(row.last_login_at) : '—') },
              {
                key: 'actions',
                title: '',
                render: (row) => (
                  <span className="table-actions">
                    <button type="button" className="button button--ghost" onClick={() => setConfirm(row)}>
                      {row.is_active ? 'Заблокировать' : 'Разблокировать'}
                    </button>
                    <button type="button" className="button button--ghost" onClick={() => setPasswordReset({ userId: row.id, password: '' })}>
                      Сброс пароля
                    </button>
                    {row.locked_until ? (
                      <button type="button" className="button button--ghost" onClick={() => unlockAdminUser(row.id).then(load)}>
                        Снять lock
                      </button>
                    ) : null}
                  </span>
                ),
              },
            ]}
            rows={state.items}
            emptyTitle="Нет пользователей"
          />
        )}
      </section>

      {passwordReset.userId ? (
        <form className="card" onSubmit={onResetPassword}>
          <header className="card__header"><h2 className="card__title">Новый пароль</h2></header>
          <div className="card__body form-grid">
            <label className="field">
              <span className="field__label">Пароль</span>
              <input className="input" type="password" value={passwordReset.password} onChange={(event) => setPasswordReset({ ...passwordReset, password: event.target.value })} required minLength={8} />
            </label>
          </div>
          <div className="card__body">
            <button type="submit" className="button" disabled={pending}>Сохранить</button>
            <button type="button" className="button button--ghost" onClick={() => setPasswordReset({ userId: null, password: '' })}>Отмена</button>
          </div>
        </form>
      ) : null}

      <AccessEditor organizations={organizations} users={state.items} onChanged={load} />

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.is_active ? 'Заблокировать учётную запись?' : 'Разблокировать учётную запись?'}
        message={confirm ? `${confirm.full_name} (${confirm.username})` : ''}
        danger={Boolean(confirm?.is_active)}
        confirmLabel={confirm?.is_active ? 'Заблокировать' : 'Разблокировать'}
        onCancel={() => setConfirm(null)}
        onConfirm={() => toggleActive(confirm)}
      />
    </div>
  );
}

function AccessEditor({ organizations, users, onChanged }) {
  const analysts = users.filter((item) => item.role === 'analyst' || item.role === 'admin');
  const [organizationId, setOrganizationId] = useState('');
  const [userId, setUserId] = useState('');
  const [accessLevel, setAccessLevel] = useState('edit');
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    if (organizations[0] && !organizationId) {
      setOrganizationId(String(organizations[0].id));
    }
  }, [organizations, organizationId]);

  useEffect(() => {
    if (users[0] && !userId) {
      setUserId(String(users[0].id));
    }
  }, [users, userId]);

  if (!organizations.length || !analysts.length) {
    return null;
  }

  async function grant() {
    setError(null);
    try {
      await assignOrganizationMember(organizationId, Number(userId), accessLevel);
      setInfo(accessLevel === 'edit'
        ? 'Сотрудник может загружать данные и запускать анализ.'
        : 'Сотруднику открыт только просмотр.');
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function revoke() {
    setError(null);
    try {
      await revokeOrganizationMember(organizationId, Number(userId));
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="card">
      <header className="card__header"><h2 className="card__title">Назначение доступа к организации</h2></header>
      {error ? <div className="card__body"><ErrorMessage message={error} /></div> : null}
      <div className="card__body form-grid">
        <label className="field">
          <span className="field__label">Организация</span>
          <select className="select" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
            {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Сотрудник</span>
          <select className="select" value={userId} onChange={(event) => setUserId(event.target.value)}>
            {analysts.map((item) => <option key={item.id} value={item.id}>{item.full_name} ({item.username})</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Уровень</span>
          <select className="select" value={accessLevel} onChange={(event) => setAccessLevel(event.target.value)}>
            <option value="view">Просмотр</option>
            <option value="edit">Редактирование</option>
          </select>
        </label>
      </div>
      {info ? <p className="card__body muted">{info}</p> : null}
      <div className="card__body table-actions">
        <button type="button" className="button" onClick={grant}>Назначить доступ</button>
        <button type="button" className="button button--ghost" onClick={revoke}>Отозвать</button>
      </div>
    </section>
  );
}

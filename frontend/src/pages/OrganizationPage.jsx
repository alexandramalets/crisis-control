import { useEffect, useState } from 'react';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import { createAdminUser, fetchAdminUsers } from '../api/adminApi.js';
import { fetchAnalyses } from '../api/analysesApi.js';
import { fetchDatasets } from '../api/datasetsApi.js';
import { errorMessage } from '../api/httpClient.js';
import {
  assignOrganizationMember, clearOrganizationWorkspace, createOrganizationEmployee, fetchOrganization,
  fetchOrganizationMembers, revokeOrganizationMember, updateOrganization,
} from '../api/organizationsApi.js';
import { useAuth } from '../auth/AuthContext.jsx';
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx';
import DataTable from '../components/ui/DataTable.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import Hint from '../components/ui/Hint.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import Notice from '../components/ui/Notice.jsx';
import { accessLevelLabel, analysisStatusLabel, formatDateTime } from '../lib/format.js';
import './pages.css';

const EMPTY_EMPLOYEE = {
  username: '', email: '', full_name: '', password: '', role: 'analyst', access_level: 'view',
};

export default function OrganizationPage() {
  const { organizationId } = useParams();
  const { user } = useAuth();
  const { setOrganizationId } = useOutletContext() ?? {};
  const [org, setOrg] = useState(null);
  const [members, setMembers] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [runs, setRuns] = useState([]);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [pending, setPending] = useState(false);
  const [existingUserId, setExistingUserId] = useState('');
  const [existingLogin, setExistingLogin] = useState('');
  const [existingLevel, setExistingLevel] = useState('view');
  const [employee, setEmployee] = useState(EMPTY_EMPLOYEE);
  const [confirm, setConfirm] = useState(null);

  const canManage = user?.role === 'admin' || (org && user && Number(org.owner_id) === Number(user.id));

  function load() {
    setError(null);
    Promise.all([
      fetchOrganization(organizationId),
      fetchOrganizationMembers(organizationId),
      fetchDatasets({ organizationId, limit: 50 }),
      fetchAnalyses({ organizationId, limit: 50 }),
    ]).then(([detail, memberList, sets, analyses]) => {
      setOrg(detail);
      setMembers(memberList || []);
      setDatasets(sets.items || []);
      setRuns(analyses.items || []);
      setOrganizationId?.(String(detail.id));
    }).catch((err) => setError(errorMessage(err)));
  }

  useEffect(() => {
    load();
  }, [organizationId]);

  useEffect(() => {
    if (!canManage) {
      return undefined;
    }
    fetchAdminUsers({ limit: 100 })
      .then((page) => setUsers(page.items || []))
      .catch(() => setUsers([]));
    return undefined;
  }, [canManage]);

  async function onAssignExisting(event) {
    event.preventDefault();
    if (!existingUserId && !existingLogin) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const saved = await assignOrganizationMember(
        organizationId,
        existingUserId ? Number(existingUserId) : null,
        existingLevel,
        existingLogin.trim() || undefined,
      );
      setInfo(`Сотрудник «${saved.full_name}» назначен (${saved.access_level === 'edit' ? 'редактирование' : 'просмотр'}).`);
      setExistingUserId('');
      setExistingLogin('');
      setMembers((current) => {
        const rest = current.filter((item) => item.user_id !== saved.user_id);
        return [...rest, saved];
      });
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onCreateEmployee(event) {
    event.preventDefault();
    setPending(true);
    try {
      const saved = user?.role === 'admin'
        ? await createAdminUser({
          ...employee,
          organization_ids: [Number(organizationId)],
          organization_access_level: employee.access_level,
        })
        : await createOrganizationEmployee(organizationId, {
          username: employee.username,
          email: employee.email,
          full_name: employee.full_name,
          password: employee.password,
          access_level: employee.access_level,
        });
      setEmployee(EMPTY_EMPLOYEE);
      const login = saved.username || saved.full_name;
      setInfo(`Создана учётная запись «${login}». Сообщите пароль сотруднику лично.`);
      if (saved.user_id) {
        setMembers((current) => {
          const rest = current.filter((item) => item.user_id !== saved.user_id);
          return [...rest, saved];
        });
      }
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  if (!org && !error) {
    return <LoadingState title="Загрузка организации" />;
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>{org?.name || 'Организация'}</h1>
          <p className="page__lead">{org?.description || 'Наборы, исследования и сотрудники.'}</p>
        </div>
        <div className="page-actions">
          <Link to="/organizations" className="button button--ghost">К списку</Link>
          {org?.can_edit ? <Link to="/data" className="button">Наборы данных</Link> : null}
        </div>
      </div>
      {error ? <ErrorMessage message={error} onRetry={load} /> : null}
      {info ? <Notice tone="success" title="Готово">{info}</Notice> : null}

      {org ? (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Сводка</h2></header>
          <div className="card__body workspace-meta">
            <span>Ваш доступ: {accessLevelLabel(org.can_edit ? 'edit' : org.access_level)}</span>
            <span>Сотрудников: {org.members_count}</span>
            <span>Наборов: {org.datasets_count}</span>
            <span>Исследований: {org.analyses_count}</span>
            <span>Последний анализ: {org.last_analysis_at ? formatDateTime(org.last_analysis_at) : 'ещё не проводился'}</span>
          </div>
          {canManage ? (
            <div className="card__body page-actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={async () => {
                  const next = window.prompt('Описание организации', org.description || '');
                  if (next == null) {
                    return;
                  }
                  await updateOrganization(org.id, { description: next.trim() || null });
                  load();
                }}
              >
                Изменить описание
              </button>
              <button type="button" className="button button--danger" onClick={() => setConfirm('clear')}>
                Очистить рабочее пространство
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="card">
        <header className="card__header"><h2 className="card__title">Сотрудники</h2></header>
        <DataTable
          columns={[
            { key: 'full_name', title: 'ФИО' },
            { key: 'username', title: 'Логин' },
            { key: 'email', title: 'Почта' },
            { key: 'role', title: 'Роль' },
            {
              key: 'access_level',
              title: 'Доступ',
              render: (row) => (row.is_owner ? 'Владелец' : accessLevelLabel(row.access_level)),
            },
            {
              key: 'actions',
              title: '',
              render: (row) => (
                canManage && !row.is_owner ? (
                  <span className="table-actions">
                    <button
                      type="button"
                      className="button button--ghost button--compact"
                      onClick={async () => {
                        const next = row.access_level === 'edit' ? 'view' : 'edit';
                        await assignOrganizationMember(organizationId, row.user_id, next);
                        load();
                      }}
                    >
                      {row.access_level === 'edit' ? 'Только просмотр' : 'Дать редактирование'}
                    </button>
                    <button
                      type="button"
                      className="button button--danger button--compact"
                      onClick={() => setConfirm({ type: 'revoke', user: row })}
                    >
                      Отозвать
                    </button>
                  </span>
                ) : null
              ),
            },
          ]}
          rows={members}
          rowKey="user_id"
          emptyTitle="Сотрудники не назначены"
        />
      </section>

      {canManage ? (
        <>
          <form className="card" onSubmit={onAssignExisting}>
            <header className="card__header"><h2 className="card__title">Назначить существующего пользователя</h2></header>
            <div className="card__body form-grid">
              {user?.role === 'admin' && users.length ? (
                <label className="field">
                  <span className="field__label">Пользователь</span>
                  <select className="select" value={existingUserId} onChange={(event) => setExistingUserId(event.target.value)}>
                    <option value="">Выберите учётную запись</option>
                    {users.map((item) => (
                      <option key={item.id} value={item.id}>{item.full_name} ({item.username})</option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="field">
                <span className="field__label">Или логин / почта</span>
                <input className="input" value={existingLogin} onChange={(event) => setExistingLogin(event.target.value)} placeholder="analyst" />
              </label>
              <label className="field">
                <span className="field__label">Уровень доступа</span>
                <select className="select" value={existingLevel} onChange={(event) => setExistingLevel(event.target.value)}>
                  <option value="view">Просмотр</option>
                  <option value="edit">Редактирование</option>
                </select>
              </label>
            </div>
            <div className="card__body">
              <Hint>Если сотрудник уже есть в системе, новая учётная запись не создаётся.</Hint>
              <button type="submit" className="button" disabled={pending}>Назначить</button>
            </div>
          </form>

          {canManage ? (
            <form className="card" onSubmit={onCreateEmployee}>
              <header className="card__header"><h2 className="card__title">Создать учётную запись и сразу назначить</h2></header>
              <div className="card__body form-grid">
                <label className="field">
                  <span className="field__label">ФИО</span>
                  <input className="input" value={employee.full_name} onChange={(event) => setEmployee((current) => ({ ...current, full_name: event.target.value }))} required />
                </label>
                <label className="field">
                  <span className="field__label">Логин</span>
                  <input className="input" value={employee.username} onChange={(event) => setEmployee((current) => ({ ...current, username: event.target.value }))} required />
                </label>
                <label className="field">
                  <span className="field__label">Электронная почта</span>
                  <input className="input" type="email" value={employee.email} onChange={(event) => setEmployee((current) => ({ ...current, email: event.target.value }))} required />
                </label>
                <label className="field">
                  <span className="field__label">Пароль</span>
                  <input className="input" type="password" value={employee.password} onChange={(event) => setEmployee((current) => ({ ...current, password: event.target.value }))} required />
                </label>
                {user?.role === 'admin' ? (
                  <label className="field">
                    <span className="field__label">Роль</span>
                    <select className="select" value={employee.role} onChange={(event) => setEmployee((current) => ({ ...current, role: event.target.value }))}>
                      <option value="analyst">Аналитик</option>
                      <option value="admin">Администратор</option>
                    </select>
                  </label>
                ) : (
                  <p className="muted">Новому сотруднику выдаётся роль аналитика этой организации.</p>
                )}
                <label className="field">
                  <span className="field__label">Доступ к этой организации</span>
                  <select className="select" value={employee.access_level} onChange={(event) => setEmployee((current) => ({ ...current, access_level: event.target.value }))}>
                    <option value="view">Просмотр</option>
                    <option value="edit">Редактирование</option>
                  </select>
                </label>
              </div>
              <div className="card__body">
                <button type="submit" className="button" disabled={pending}>Создать сотрудника</button>
              </div>
            </form>
          ) : null}
        </>
      ) : null}

      <section className="card">
        <header className="card__header">
          <h2 className="card__title">Наборы данных</h2>
          <Link to="/data" className="button button--ghost button--compact">Открыть</Link>
        </header>
        <DataTable
          columns={[
            { key: 'name', title: 'Набор', render: (row) => <Link to={`/data/${row.id}`}>{row.name}</Link> },
            { key: 'created_at', title: 'Загружен', render: (row) => formatDateTime(row.created_at) },
          ]}
          rows={datasets}
          emptyTitle="Наборов нет"
        />
      </section>

      <section className="card">
        <header className="card__header">
          <h2 className="card__title">Исследования</h2>
          <Link to="/reports" className="button button--ghost button--compact">История</Link>
        </header>
        <DataTable
          columns={[
            { key: 'id', title: '№' },
            { key: 'dataset_name', title: 'Набор' },
            { key: 'status', title: 'Статус', render: (row) => analysisStatusLabel(row.status) },
            { key: 'created_at', title: 'Запуск', render: (row) => formatDateTime(row.created_at) },
            { key: 'open', title: '', render: (row) => <Link to={`/analysis/${row.id}`}>Открыть</Link> },
          ]}
          rows={runs}
          emptyTitle="Исследований нет"
        />
      </section>

      <ConfirmDialog
        open={Boolean(confirm)}
        danger
        title={confirm === 'clear' ? 'Очистить рабочее пространство?' : 'Отозвать доступ?'}
        message={confirm === 'clear'
          ? 'Будут удалены все наборы данных этой организации, связанные исследования и отчёты. Карточка организации и список сотрудников сохранятся. Данные других организаций не затрагиваются.'
          : `Сотрудник ${confirm?.user?.full_name || ''} потеряет доступ к этой организации.`}
        confirmLabel={confirm === 'clear' ? 'Удалить данные организации' : 'Отозвать доступ'}
        onCancel={() => setConfirm(null)}
        onConfirm={async () => {
          setPending(true);
          try {
            if (confirm === 'clear') {
              await clearOrganizationWorkspace(organizationId);
              setInfo('Рабочее пространство очищено. Можно загрузить новый набор и провести анализ заново.');
            } else if (confirm?.user) {
              await revokeOrganizationMember(organizationId, confirm.user.user_id);
            }
            setConfirm(null);
            load();
          } catch (err) {
            setError(errorMessage(err));
            setConfirm(null);
          } finally {
            setPending(false);
          }
        }}
      />
    </div>
  );
}

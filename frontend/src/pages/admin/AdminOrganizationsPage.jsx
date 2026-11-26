import { useEffect, useState } from 'react';
import { fetchOrganizationMembers } from '../../api/adminApi.js';
import { createOrganization, fetchOrganizations, updateOrganization } from '../../api/organizationsApi.js';
import { errorMessage } from '../../api/httpClient.js';
import DataTable from '../../components/ui/DataTable.jsx';
import ErrorMessage from '../../components/ui/ErrorMessage.jsx';
import LoadingState from '../../components/ui/LoadingState.jsx';
import { formatDateTime } from '../../lib/format.js';
import '../pages.css';

export default function AdminOrganizationsPage() {
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [members, setMembers] = useState([]);
  const [pending, setPending] = useState(false);

  function load() {
    setState((current) => ({ ...current, loading: true, error: null }));
    fetchOrganizations()
      .then((page) => setState({ loading: false, error: null, items: page.items || [] }))
      .catch((error) => setState({ loading: false, error, items: [] }));
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setMembers([]);
      return undefined;
    }
    let active = true;
    fetchOrganizationMembers(selectedId)
      .then((memberList) => {
        if (active) {
          setMembers(memberList || []);
        }
      })
      .catch((error) => setState((current) => ({ ...current, error })));
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function onCreate(event) {
    event.preventDefault();
    setPending(true);
    try {
      const created = await createOrganization({ name: name.trim(), description: description.trim() || null });
      setName('');
      setDescription('');
      setSelectedId(created.id);
      load();
    } catch (error) {
      setState((current) => ({ ...current, error }));
    } finally {
      setPending(false);
    }
  }

  async function onRename(organization) {
    const next = window.prompt('Название организации', organization.name);
    if (!next || next.trim() === organization.name) {
      return;
    }
    try {
      await updateOrganization(organization.id, { name: next.trim() });
      load();
    } catch (error) {
      setState((current) => ({ ...current, error }));
    }
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Организации</h1>
          <p className="page__lead">
            Создайте организацию и назначьте доступ на странице «Пользователи».
          </p>
        </div>
      </div>
      {state.error ? <ErrorMessage message={errorMessage(state.error)} onRetry={load} /> : null}

      <form className="card" onSubmit={onCreate}>
        <header className="card__header"><h2 className="card__title">Новая организация</h2></header>
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Название</span>
            <input className="input" value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label className="field">
            <span className="field__label">Описание</span>
            <input className="input" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
        </div>
        <div className="card__body">
          <button type="submit" className="button" disabled={pending}>Создать</button>
        </div>
      </form>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Список</h2></header>
        {state.loading ? <LoadingState title="Загрузка организаций" /> : (
          <DataTable
            columns={[
              { key: 'name', title: 'Название' },
              { key: 'created_at', title: 'Создана', render: (row) => formatDateTime(row.created_at) },
              {
                key: 'open',
                title: '',
                render: (row) => (
                  <span className="table-actions">
                    <button type="button" className="button button--ghost" onClick={() => setSelectedId(row.id)}>Сотрудники</button>
                    <button type="button" className="button button--ghost" onClick={() => onRename(row)}>Изменить</button>
                  </span>
                ),
              },
            ]}
            rows={state.items}
            emptyTitle="Организаций нет"
          />
        )}
      </section>

      {selectedId ? (
        <>
          <section className="card">
            <header className="card__header"><h2 className="card__title">Сотрудники с доступом</h2></header>
            <DataTable
              columns={[
                { key: 'username', title: 'Логин' },
                { key: 'full_name', title: 'Имя' },
                { key: 'role', title: 'Роль' },
                {
                  key: 'access_level',
                  title: 'Доступ',
                  render: (row) => (row.is_owner ? 'Владелец' : row.access_level === 'edit' ? 'Редактирование' : 'Просмотр'),
                },
                { key: 'granted_at', title: 'Назначен', render: (row) => formatDateTime(row.granted_at) },
              ]}
              rows={members}
              rowKey="user_id"
              emptyTitle="Доступ никому не назначен"
            />
          </section>
        </>
      ) : null}
    </div>
  );
}

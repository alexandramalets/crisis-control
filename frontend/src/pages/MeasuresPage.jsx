import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { createMeasure, deleteMeasure, fetchMeasureEvents, fetchMeasures, updateMeasure } from '../api/governanceApi.js';
import { errorMessage } from '../api/httpClient.js';
import DataTable from '../components/ui/DataTable.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import Notice from '../components/ui/Notice.jsx';
import { formatDate, formatDateTime } from '../lib/format.js';
import './pages.css';

const STATUSES = [
  { id: 'planned', label: 'Запланировано' },
  { id: 'in_progress', label: 'В работе' },
  { id: 'done', label: 'Выполнено' },
  { id: 'overdue', label: 'Просрочено' },
  { id: 'cancelled', label: 'Отменено' },
];

export default function MeasuresPage() {
  const { organizationId, selectedOrganization, canEdit } = useOutletContext() ?? {};
  const [items, setItems] = useState([]);
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ title: '', description: '', due_at: '', priority: 'medium' });
  const [pending, setPending] = useState(false);
  const [filter, setFilter] = useState('');
  const [confirmId, setConfirmId] = useState(null);

  function reload() {
    if (!organizationId) {
      setItems([]);
      setLoading(false);
      return Promise.resolve();
    }
    setLoading(true);
    return fetchMeasures(organizationId)
      .then(setItems)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    setError(null);
    reload();
  }, [organizationId]);

  useEffect(() => {
    if (!selected) {
      setEvents([]);
      return undefined;
    }
    fetchMeasureEvents(selected)
      .then(setEvents)
      .catch(() => setEvents([]));
    return undefined;
  }, [selected]);

  async function onCreate(event) {
    event.preventDefault();
    if (!canEdit) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await createMeasure(organizationId, {
        title: form.title,
        description: form.description || form.title,
        due_at: form.due_at || null,
        priority: form.priority,
      });
      setForm({ title: '', description: '', due_at: '', priority: 'medium' });
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onStatus(id, status) {
    setPending(true);
    setError(null);
    try {
      await updateMeasure(id, { status });
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onDelete(id) {
    setPending(true);
    setError(null);
    try {
      await deleteMeasure(id);
      if (selected === id) {
        setSelected(null);
      }
      setConfirmId(null);
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  if (!organizationId) {
    return (
      <div className="page">
        <EmptyState title="Выберите организацию" description="Мероприятия хранятся отдельно для каждой организации." />
      </div>
    );
  }

  if (loading) {
    return <div className="page"><LoadingState title="Загрузка мероприятий" /></div>;
  }

  const rows = items.filter((item) => {
    if (!filter) {
      return true;
    }
    const blob = `${item.title} ${item.status} ${item.priority}`.toLowerCase();
    return blob.includes(filter.toLowerCase());
  });

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Антикризисные мероприятия</h1>
          <p className="page__lead">
            {selectedOrganization?.name}. Контроль исполнения. Выполненные записи сохраняются.
          </p>
        </div>
      </div>
      {error ? <ErrorMessage message={error} /> : null}
      {canEdit ? (
        <form className="card" onSubmit={onCreate}>
          <header className="card__header"><h2 className="card__title">Новое мероприятие</h2></header>
          <div className="card__body form-grid">
            <label className="field">
              <span className="field__label">Название</span>
              <input className="input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Срок</span>
              <input className="input" type="date" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Приоритет</span>
              <select className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                <option value="low">Низкий</option>
                <option value="medium">Средний</option>
                <option value="high">Высокий</option>
              </select>
            </label>
          </div>
          <div className="card__body">
            <label className="field">
              <span className="field__label">Описание</span>
              <textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>
          </div>
          <div className="card__body page-actions">
            <button type="submit" className="button" disabled={pending}>{pending ? 'Сохранение…' : 'Создать'}</button>
          </div>
        </form>
      ) : (
        <Notice tone="warning" title="Только просмотр">Изменение мероприятий недоступно при праве «просмотр».</Notice>
      )}
      <section className="card">
        <header className="card__header">
          <h2 className="card__title">Список</h2>
          <input className="input" placeholder="Поиск" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </header>
        <DataTable
          sortable
          columns={[
            { key: 'title', title: 'Название' },
            { key: 'status', title: 'Статус', render: (row) => STATUSES.find((s) => s.id === row.status)?.label || row.status },
            { key: 'priority', title: 'Приоритет' },
            { key: 'due_at', title: 'Срок', render: (row) => formatDate(row.due_at) },
            { key: 'updated_at', title: 'Изменено', render: (row) => formatDateTime(row.updated_at) },
            {
              key: 'open',
              title: '',
              render: (row) => (
                <span className="table-actions">
                  {canEdit ? (
                    <select
                      className="select"
                      value={row.status}
                      disabled={pending}
                      onChange={(event) => onStatus(row.id, event.target.value)}
                    >
                      {STATUSES.filter((s) => !(row.status === 'done' && s.id === 'cancelled')).map((s) => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  ) : null}
                  <button type="button" className="button button--ghost button--compact" onClick={() => setSelected(row.id)}>История</button>
                  {canEdit ? (
                    <button type="button" className="button button--danger button--compact" disabled={pending} onClick={() => setConfirmId(row.id)}>Удалить</button>
                  ) : null}
                </span>
              ),
            },
          ]}
          rows={rows}
          emptyTitle="Мероприятий нет"
        />
      </section>
      {selected ? (
        <section className="card">
          <header className="card__header"><h2 className="card__title">История мероприятия №{selected}</h2></header>
          <DataTable
            columns={[
              { key: 'created_at', title: 'Время', render: (row) => formatDateTime(row.created_at) },
              { key: 'event_type', title: 'Событие' },
              { key: 'comment', title: 'Комментарий' },
            ]}
            rows={events}
            emptyTitle="Записей нет"
          />
        </section>
      ) : null}
      <ConfirmDialog
        open={Boolean(confirmId)}
        danger
        title="Удалить мероприятие?"
        message="Запись и её история будут удалены только в этой организации."
        confirmLabel="Удалить"
        onCancel={() => setConfirmId(null)}
        onConfirm={() => onDelete(confirmId)}
      />
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchAdminOverview } from '../../api/adminApi.js';
import { errorMessage } from '../../api/httpClient.js';
import DataTable from '../../components/ui/DataTable.jsx';
import ErrorMessage from '../../components/ui/ErrorMessage.jsx';
import LoadingState from '../../components/ui/LoadingState.jsx';
import MetricCard from '../../components/ui/MetricCard.jsx';
import { formatDateTime } from '../../lib/format.js';
import '../pages.css';

export default function AdminOverviewPage() {
  const [state, setState] = useState({ loading: true, error: null, overview: null });

  function load() {
    setState((current) => ({ ...current, loading: true, error: null }));
    fetchAdminOverview()
      .then((overview) => setState({ loading: false, error: null, overview }))
      .catch((error) => setState({ loading: false, error, overview: null }));
  }

  useEffect(() => {
    load();
  }, []);

  if (state.loading) {
    return <LoadingState title="Загрузка обзора системы" />;
  }
  if (state.error) {
    return <ErrorMessage message={errorMessage(state.error)} onRetry={load} />;
  }

  const data = state.overview;
  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Обзор системы</h1>
          <p className="page__lead">Учётные записи и организации. Аналитические данные администратору недоступны.</p>
        </div>
        <button type="button" className="button button--ghost" onClick={load}>Обновить</button>
      </div>
      <div className="page-actions">
        <Link className="button" to="/admin/organizations">Создать организацию</Link>
        <Link className="button button--ghost" to="/admin/users">Добавить пользователя</Link>
      </div>

      <div className="home-metrics">
        <MetricCard title="Пользователи" value={data.users_total} />
        <MetricCard title="Активные учётные записи" value={data.users_active} />
        <MetricCard title="Организации" value={data.organizations_total} />
      </div>

      <section className="card">
        <header className="card__header">
          <h2 className="card__title">Последние события</h2>
          <Link to="/admin/users" className="button button--ghost">Пользователи</Link>
        </header>
        <DataTable
          columns={[
            { key: 'created_at', title: 'Время', render: (row) => formatDateTime(row.created_at) },
            { key: 'action', title: 'Действие' },
            { key: 'object_type', title: 'Объект' },
            { key: 'object_id', title: 'Ид.' },
            { key: 'user_id', title: 'Пользователь' },
          ]}
          rows={data.recent_events || []}
          emptyTitle="Журнал пуст"
          emptyDescription="События появятся после входа, создания учёток и назначения доступа."
        />
      </section>
    </div>
  );
}

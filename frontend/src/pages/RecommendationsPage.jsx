import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { convertRecommendation, fetchRecommendations, updateRecommendation } from '../api/governanceApi.js';
import { errorMessage } from '../api/httpClient.js';
import DataTable from '../components/ui/DataTable.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import { formatDateTime } from '../lib/format.js';
import './pages.css';

const STATUS = {
  proposed: 'Предложена',
  accepted: 'Принята',
  rejected: 'Отклонена',
  converted: 'Преобразована в мероприятие',
};

export default function RecommendationsPage() {
  const { organizationId, selectedOrganization, canEdit } = useOutletContext() ?? {};
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  function reload() {
    if (!organizationId) {
      setItems([]);
      setLoading(false);
      return Promise.resolve();
    }
    setLoading(true);
    return fetchRecommendations(organizationId)
      .then(setItems)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    setError(null);
    reload();
  }, [organizationId]);

  async function act(id, status) {
    setBusy(id);
    setError(null);
    try {
      await updateRecommendation(id, { status });
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function convert(id) {
    setBusy(id);
    setError(null);
    try {
      await convertRecommendation(id, {});
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  if (!organizationId) {
    return (
      <div className="page">
        <EmptyState title="Выберите организацию" description="Рекомендации формируются по результатам исследования выбранной организации." />
      </div>
    );
  }

  if (loading) {
    return <div className="page"><LoadingState title="Загрузка рекомендаций" /></div>;
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Рекомендации</h1>
          <p className="page__lead">
            {selectedOrganization?.name}. Предложения по правилам на основе выявленных проблем.
          </p>
        </div>
      </div>
      {error ? <ErrorMessage message={error} /> : null}
      <section className="card">
        <DataTable
          sortable
          filterable
          columns={[
            { key: 'title', title: 'Рекомендация' },
            { key: 'problem', title: 'Проблема' },
            { key: 'priority', title: 'Приоритет' },
            { key: 'status', title: 'Статус', render: (row) => STATUS[row.status] || row.status },
            { key: 'created_at', title: 'Создана', render: (row) => formatDateTime(row.created_at) },
            {
              key: 'actions',
              title: '',
              render: (row) => (
                <span className="table-actions">
                  {row.run_id ? <Link to={`/analysis/${row.run_id}`}>Исследование</Link> : null}
                  {canEdit && row.status === 'proposed' ? (
                    <>
                      <button type="button" className="button button--ghost button--compact" disabled={busy === row.id} onClick={() => act(row.id, 'accepted')}>Принять</button>
                      <button type="button" className="button button--ghost button--compact" disabled={busy === row.id} onClick={() => act(row.id, 'rejected')}>Отклонить</button>
                      <button type="button" className="button button--compact" disabled={busy === row.id} onClick={() => convert(row.id)}>В мероприятие</button>
                    </>
                  ) : null}
                </span>
              ),
            },
          ]}
          rows={items}
          emptyTitle="Рекомендаций нет"
          emptyDescription="Появятся после исследования, если сработают правила."
        />
      </section>
      {items.map((row) => (
        <section className="card" key={`detail-${row.id}`}>
          <header className="card__header"><h2 className="card__title">{row.title}</h2></header>
          <div className="card__body">
            <p>{row.basis}</p>
            <p>{row.actions}</p>
            {row.expected_result ? <p className="muted">Ожидаемый результат: {row.expected_result}</p> : null}
            {row.limitations ? <p className="muted">{row.limitations}</p> : null}
          </div>
        </section>
      ))}
    </div>
  );
}

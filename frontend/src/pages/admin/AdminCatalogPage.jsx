import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchAnalyses } from '../../api/analysesApi.js';
import { fetchDatasets } from '../../api/datasetsApi.js';
import { errorMessage } from '../../api/httpClient.js';
import DataTable from '../../components/ui/DataTable.jsx';
import ErrorMessage from '../../components/ui/ErrorMessage.jsx';
import LoadingState from '../../components/ui/LoadingState.jsx';
import { analysisStatusLabel, formatDateTime } from '../../lib/format.js';
import '../pages.css';

export function AdminDataPage() {
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  useEffect(() => {
    fetchDatasets({ limit: 100 })
      .then((page) => setState({ loading: false, error: null, items: page.items || [] }))
      .catch((error) => setState({ loading: false, error, items: [] }));
  }, []);
  if (state.loading) {
    return <LoadingState title="Загрузка наборов" />;
  }
  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Данные</h1>
          <p className="page__lead">Загруженные наборы. Правка значений — повторным импортом.</p>
        </div>
      </div>
      {state.error ? <ErrorMessage message={errorMessage(state.error)} /> : null}
      <section className="card">
        <DataTable
          filterable
          sortable
          columns={[
            { key: 'name', title: 'Набор', render: (row) => <Link to={`/data/${row.id}`}>{row.name}</Link> },
            { key: 'organization_id', title: 'Организация' },
            { key: 'created_at', title: 'Загружен', render: (row) => formatDateTime(row.created_at) },
            { key: 'source_filename', title: 'Файл' },
          ]}
          rows={state.items}
          emptyTitle="Наборов нет"
        />
      </section>
    </div>
  );
}

export function AdminAnalysesPage() {
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  useEffect(() => {
    fetchAnalyses({ limit: 100 })
      .then((page) => setState({ loading: false, error: null, items: page.items || [] }))
      .catch((error) => setState({ loading: false, error, items: [] }));
  }, []);
  if (state.loading) {
    return <LoadingState title="Загрузка исследований" />;
  }
  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Исследования</h1>
          <p className="page__lead">Запуски по всем организациям.</p>
        </div>
      </div>
      {state.error ? <ErrorMessage message={errorMessage(state.error)} /> : null}
      <section className="card">
        <DataTable
          filterable
          sortable
          columns={[
            { key: 'id', title: '№' },
            { key: 'dataset_name', title: 'Набор' },
            { key: 'status', title: 'Статус', render: (row) => analysisStatusLabel(row.status) },
            { key: 'created_at', title: 'Запуск', render: (row) => formatDateTime(row.created_at) },
            { key: 'open', title: '', render: (row) => <Link to={`/analysis/${row.id}`}>Открыть</Link> },
          ]}
          rows={state.items}
          emptyTitle="Исследований нет"
        />
      </section>
    </div>
  );
}

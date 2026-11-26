import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { fetchAnalyses } from '../api/analysesApi.js';
import { createScenario, fetchScenarios } from '../api/governanceApi.js';
import { errorMessage } from '../api/httpClient.js';
import DataTable from '../components/ui/DataTable.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import { formatDateTime, formatNumber } from '../lib/format.js';
import './pages.css';

export default function ScenariosPage() {
  const { organizationId, selectedOrganization, canEdit } = useOutletContext() ?? {};
  const [runs, setRuns] = useState([]);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [form, setForm] = useState({
    base_run_id: '',
    name: '',
    indicator_code: 'revenue',
    percent_change: '-10',
  });

  function reload() {
    if (!organizationId) {
      setItems([]);
      setRuns([]);
      setLoading(false);
      return Promise.resolve();
    }
    setLoading(true);
    return Promise.all([
      fetchScenarios(organizationId),
      fetchAnalyses({ organizationId, limit: 50 }),
    ])
      .then(([scenarios, analyses]) => {
        setItems(scenarios);
        setRuns(analyses.items || []);
        setForm((current) => ({
          ...current,
          base_run_id: current.base_run_id || String(analyses.items?.[0]?.id || ''),
        }));
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    setError(null);
    reload();
  }, [organizationId]);

  async function onCreate(event) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await createScenario(organizationId, {
        base_run_id: Number(form.base_run_id),
        name: form.name,
        description: 'Условный расчёт. Исходные данные не изменены.',
        adjustments: [{ indicator_code: form.indicator_code, percent_change: Number(form.percent_change) }],
      });
      setForm((current) => ({ ...current, name: '' }));
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  if (!organizationId) {
    return <div className="page"><EmptyState title="Выберите организацию" /></div>;
  }
  if (loading) {
    return <div className="page"><LoadingState title="Загрузка сценариев" /></div>;
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Сценарии</h1>
          <p className="page__lead">
            {selectedOrganization?.name}. Условное изменение показателя. Исходные данные не меняются.
          </p>
        </div>
      </div>
      {error ? <ErrorMessage message={error} /> : null}
      {canEdit ? (
        <form className="card" onSubmit={onCreate}>
          <header className="card__header"><h2 className="card__title">Новый сценарий</h2></header>
          <div className="card__body form-grid">
            <label className="field">
              <span className="field__label">Исходное исследование</span>
              <select className="select" required value={form.base_run_id} onChange={(e) => setForm({ ...form, base_run_id: e.target.value })}>
                <option value="">Выберите</option>
                {runs.map((run) => (
                  <option key={run.id} value={run.id}>#{run.id} · {run.dataset_name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Название</span>
              <input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Показатель</span>
              <input className="input" required value={form.indicator_code} onChange={(e) => setForm({ ...form, indicator_code: e.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Изменение, %</span>
              <input className="input" type="number" step="0.1" required value={form.percent_change} onChange={(e) => setForm({ ...form, percent_change: e.target.value })} />
            </label>
          </div>
          <div className="card__body page-actions">
            <button type="submit" className="button" disabled={pending || !form.base_run_id}>{pending ? 'Расчёт…' : 'Рассчитать'}</button>
          </div>
        </form>
      ) : null}
      <section className="card">
        <header className="card__header"><h2 className="card__title">Сохранённые сценарии</h2></header>
        <DataTable
          columns={[
            { key: 'name', title: 'Название' },
            { key: 'base_run_id', title: 'Исследование', render: (row) => <Link to={`/analysis/${row.base_run_id}`}>#{row.base_run_id}</Link> },
            { key: 'created_at', title: 'Создан', render: (row) => formatDateTime(row.created_at) },
            {
              key: 'delta',
              title: 'Результат',
              render: (row) => row.result?.error
                ? row.result.error
                : (row.result?.disclaimer || 'Рассчитан'),
            },
          ]}
          rows={items}
          emptyTitle="Сценариев нет"
        />
      </section>
      {items.map((item) => {
        const ratios = item.result?.procedures?.ratios?.result?.items || [];
        return ratios.length ? (
          <section className="card" key={`sc-${item.id}`}>
            <header className="card__header"><h2 className="card__title">{item.name}: коэффициенты сценария</h2></header>
            <DataTable
              columns={[
                { key: 'name', title: 'Коэффициент' },
                { key: 'last_value', title: 'Значение', render: (row) => formatNumber(row.last_value) },
                { key: 'reason', title: 'Ограничение', render: (row) => row.payload?.reason || row.reason || '—' },
              ]}
              rows={ratios}
            />
          </section>
        ) : null;
      })}
    </div>
  );
}

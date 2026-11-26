import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { createAnalysisPdf, downloadReportContent, fetchAnalyses, fetchAnalysisResults } from '../api/analysesApi.js';
import { compareRuns } from '../api/governanceApi.js';
import { fetchOrganizations } from '../api/organizationsApi.js';
import { errorMessage } from '../api/httpClient.js';
import DataTable from '../components/ui/DataTable.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import { downloadBlob, downloadText, toCsv } from '../lib/csv.js';
import { analysisStatusLabel, formatDateTime, formatNumber } from '../lib/format.js';
import './pages.css';

function resultsToCsv(payload) {
  const lines = [];
  const run = payload.run;
  lines.push(toCsv(
    [{ key: 'field', title: 'Поле' }, { key: 'value', title: 'Значение' }],
    [
      { field: 'id', value: run.id },
      { field: 'organization', value: run.organization_name },
      { field: 'dataset', value: run.dataset_name },
      { field: 'status', value: run.status },
      { field: 'score', value: payload.assessment?.score ?? '' },
      { field: 'history_score', value: payload.assessment?.history_score ?? '' },
      { field: 'compliance_score', value: payload.assessment?.compliance_score ?? '' },
    ],
  ));
  lines.push('\n\nАномалии\n');
  lines.push(toCsv(
    [
      { key: 'indicator_name', title: 'Показатель' },
      { key: 'period_start', title: 'Период' },
      { key: 'value', title: 'Факт' },
      { key: 'score', title: 'Оценка' },
    ],
    payload.anomalies?.items || [],
  ));
  lines.push('\n\nКорреляции\n');
  lines.push(toCsv(
    [
      { key: 'indicator_a', title: 'A' },
      { key: 'indicator_b', title: 'B' },
      { key: 'coefficient', title: 'Коэффициент' },
    ],
    payload.correlation?.pairs || [],
  ));
  lines.push('\n\nКластеры\n');
  lines.push(toCsv(
    [{ key: 'cluster', title: 'Кластер' }, { key: 'label', title: 'Подпись' }, { key: 'size', title: 'Размер' }],
    payload.clustering?.clusters || [],
  ));
  const forecastRows = (payload.forecast?.series || []).flatMap((series) => (
    (series.points || []).map((point) => ({ ...point, indicator: series.indicator }))
  ));
  lines.push('\n\nКоэффициенты\n');
  lines.push(toCsv(
    [
      { key: 'name', title: 'Коэффициент' },
      { key: 'last_value', title: 'Факт' },
      { key: 'pct_change', title: 'Изменение' },
    ],
    payload.ratios?.items || [],
  ));
  lines.push('\n\nТенденции\n');
  lines.push(toCsv(
    [
      { key: 'indicator', title: 'Показатель' },
      { key: 'label', title: 'Описание' },
      { key: 'pct_change', title: 'Изменение' },
    ],
    payload.trends?.items || [],
  ));
  lines.push('\n\nПроблемы\n');
  lines.push(toCsv(
    [{ key: 'title', title: 'Проблема' }, { key: 'severity', title: 'Уровень' }, { key: 'confidence', title: 'Уверенность' }],
    payload.findings || [],
  ));
  lines.push('\n\nПрогноз\n');
  lines.push(toCsv(
    [
      { key: 'indicator', title: 'Показатель' },
      { key: 'period_start', title: 'Период' },
      { key: 'value', title: 'Значение' },
      { key: 'lower_bound', title: 'Нижняя' },
      { key: 'upper_bound', title: 'Верхняя' },
    ],
    forecastRows,
  ));
  return lines.join('');
}

export default function ReportsPage() {
  const { organizationId: workspaceOrgId } = useOutletContext() ?? {};
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [organizations, setOrganizations] = useState([]);
  const [organizationId, setOrganizationId] = useState(workspaceOrgId || '');
  const [busyId, setBusyId] = useState(null);
  const [pair, setPair] = useState({ left: '', right: '' });
  const [compare, setCompare] = useState(null);
  const [comparePending, setComparePending] = useState(false);
  const [compareError, setCompareError] = useState(null);

  useEffect(() => {
    fetchOrganizations()
      .then((page) => setOrganizations(page.items || []))
      .catch(() => setOrganizations([]));
  }, []);

  useEffect(() => {
    if (workspaceOrgId) {
      setOrganizationId(String(workspaceOrgId));
    }
  }, [workspaceOrgId]);

  useEffect(() => {
    setState((current) => ({ ...current, loading: true, error: null }));
    fetchAnalyses({ limit: 50, organizationId: organizationId || undefined })
      .then((page) => setState({ loading: false, error: null, items: page.items || [] }))
      .catch((error) => setState({ loading: false, error, items: [] }));
  }, [organizationId]);

  async function exportPdf(runId) {
    setBusyId(runId);
    try {
      const report = await createAnalysisPdf(runId);
      const response = await downloadReportContent(report.id);
      downloadBlob(`crisis-control-${runId}.pdf`, response.data);
    } catch (error) {
      setState((current) => ({ ...current, error }));
    } finally {
      setBusyId(null);
    }
  }

  async function onCompare(event) {
    event.preventDefault();
    if (!pair.left || !pair.right || pair.left === pair.right) {
      setCompareError('Выберите два разных исследования.');
      return;
    }
    setComparePending(true);
    setCompareError(null);
    try {
      setCompare(await compareRuns(Number(pair.left), Number(pair.right)));
    } catch (error) {
      setCompareError(errorMessage(error));
    } finally {
      setComparePending(false);
    }
  }

  async function exportCsv(runId) {
    setBusyId(runId);
    try {
      const payload = await fetchAnalysisResults(runId);
      downloadText(`analysis-${runId}.csv`, resultsToCsv(payload));
    } catch (error) {
      setState((current) => ({ ...current, error }));
    } finally {
      setBusyId(null);
    }
  }

  if (state.loading) {
    return <LoadingState title="Загрузка исследований" />;
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>История исследований</h1>
          <p className="page__lead">Сохранённые запуски. Можно открыть, сравнить, выгрузить CSV или PDF.</p>
        </div>
      </div>
      {state.error ? <ErrorMessage message={errorMessage(state.error)} /> : null}
      {compareError ? <ErrorMessage message={compareError} /> : null}
      <form className="card" onSubmit={onCompare}>
        <header className="card__header"><h2 className="card__title">Сравнение двух исследований</h2></header>
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Первое</span>
            <select className="select" required value={pair.left} onChange={(event) => setPair({ ...pair, left: event.target.value })}>
              <option value="">Выберите</option>
              {state.items.map((run) => (
                <option key={run.id} value={run.id}>#{run.id} · {run.dataset_name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Второе</span>
            <select className="select" required value={pair.right} onChange={(event) => setPair({ ...pair, right: event.target.value })}>
              <option value="">Выберите</option>
              {state.items.map((run) => (
                <option key={`r-${run.id}`} value={run.id}>#{run.id} · {run.dataset_name}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="card__body page-actions">
          <button className="button" type="submit" disabled={comparePending}>Сравнить</button>
        </div>
        {compare ? (
          <div className="card__body">
            <p>
              Исследование №{compare.left?.id}: оценка {formatNumber(compare.left?.score)},
              проблем {compare.left?.findings ?? '—'}, предупреждений {compare.left?.alerts ?? '—'}.
            </p>
            <p>
              Исследование №{compare.right?.id}: оценка {formatNumber(compare.right?.score)},
              проблем {compare.right?.findings ?? '—'}, предупреждений {compare.right?.alerts ?? '—'}.
            </p>
            {compare.comparable && compare.delta ? (
              <p>
                Изменение оценки: {formatNumber(compare.delta.score)}.
                Изменение числа проблем: {compare.delta.findings}.
                Изменение числа предупреждений: {compare.delta.alerts}.
              </p>
            ) : null}
            <p className="muted">{compare.note || (compare.comparable ? 'Сравнение относится к одному набору и периоду.' : '')}</p>
            <div className="page-actions">
              {compare.left?.id ? <Link to={`/analysis/${compare.left.id}`}>Открыть первое</Link> : null}
              {compare.right?.id ? <Link to={`/analysis/${compare.right.id}`}>Открыть второе</Link> : null}
            </div>
          </div>
        ) : null}
      </form>
      {organizations.length > 1 ? (
        <label className="field">
          <span className="field__label">Организация</span>
          <select className="select" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
            <option value="">Все доступные</option>
            {organizations.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
      ) : null}
      <section className="card">
        <DataTable
          sortable
          filterable
          columns={[
            { key: 'id', title: '№' },
            { key: 'organization_name', title: 'Организация' },
            { key: 'dataset_name', title: 'Набор' },
            { key: 'status', title: 'Статус', render: (row) => analysisStatusLabel(row.status) },
            { key: 'created_at', title: 'Создано', render: (row) => formatDateTime(row.created_at) },
            {
              key: 'actions',
              title: '',
              render: (row) => (
                <span className="table-actions">
                  <Link to={`/analysis/${row.id}`}>Открыть</Link>
                  {' · '}
                  <button
                    type="button"
                    className="button button--ghost"
                    disabled={busyId === row.id || !['completed', 'partially_completed'].includes(row.status)}
                    onClick={() => exportCsv(row.id)}
                  >
                    {busyId === row.id ? 'Выгрузка…' : 'CSV'}
                  </button>
                  <button
                    type="button"
                    className="button button--ghost"
                    disabled={busyId === row.id || !['completed', 'partially_completed'].includes(row.status)}
                    onClick={() => exportPdf(row.id)}
                  >
                    PDF
                  </button>
                </span>
              ),
            },
          ]}
          rows={state.items}
          emptyTitle="Исследований нет"
          emptyDescription="Запустите анализ, чтобы появилась запись для просмотра и выгрузки."
        />
      </section>
    </div>
  );
}

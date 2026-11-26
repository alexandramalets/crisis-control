import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { fetchDashboard } from '../api/dashboardApi.js';
import { errorMessage } from '../api/httpClient.js';
import { useAuth } from '../auth/AuthContext.jsx';
import ChartPanel from '../components/ui/ChartPanel.jsx';
import DataTable from '../components/ui/DataTable.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import MetricCard from '../components/ui/MetricCard.jsx';
import { IconCash, IconProfit, IconReceivables, IconRevenue } from '../icons/Icons.jsx';
import { analysisStatusLabel, formatDateTime, formatMoney, formatNumber, formatPercent } from '../lib/format.js';
import AssessmentPanel from './home/AssessmentPanel.jsx';
import CorrelationHeatmap from './home/CorrelationHeatmap.jsx';
import DynamicsChart from './home/DynamicsChart.jsx';
import RiskFactors from './home/RiskFactors.jsx';
import './pages.css';

const KPI_ICONS = {
  revenue: IconRevenue,
  profit: IconProfit,
  receivables: IconReceivables,
  payables: IconReceivables,
  cash: IconCash,
};

const ANOMALY_COLUMNS = [
  {
    key: 'indicator_name',
    title: 'Показатель',
    render: (row) => <span className="cell-wrap" title={row.indicator_name}>{row.indicator_name}</span>,
  },
  { key: 'value', title: 'Факт', render: (row) => formatNumber(row.value) },
  { key: 'baseline', title: 'База', render: (row) => formatNumber(row.baseline) },
  { key: 'deviation', title: 'Отклонение', render: (row) => formatNumber(row.deviation) },
  { key: 'period_start', title: 'Период', render: (row) => row.period_start },
];

function OrganizationSnapshots({ items, currentId, onSelect }) {
  if (!items?.length) {
    return null;
  }
  return (
    <section className="card">
      <header className="card__header">
        <h2 className="card__title">Организации</h2>
      </header>
      <div className="home-metrics" style={{ padding: '0 16px 16px' }}>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`metric-card card${String(item.id) === String(currentId) ? ' metric-card--accent' : ''}`}
            onClick={() => onSelect?.(String(item.id))}
          >
            <div className="metric-card__label">{item.name}</div>
            <div className="metric-card__value">
              {item.score == null ? '—' : formatNumber(item.score, 0)}
            </div>
            <div className="metric-card__meta">
              {item.interpretation || (item.dataset_name ? `Набор: ${item.dataset_name}` : 'Нет исследования')}
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

export default function HomePage() {
  const { period = '12', organizationId, setOrganizationId } = useOutletContext() ?? {};
  const { user, ready } = useAuth();
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const [indicator, setIndicator] = useState(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!ready) {
      return undefined;
    }
    if (!user) {
      setState({ loading: false, error: null, data: null });
      return undefined;
    }
    const controller = new AbortController();
    let active = true;
    setState((current) => ({ ...current, loading: true, error: null }));
    fetchDashboard({ months: Number(period), organizationId, signal: controller.signal })
      .then((data) => {
        if (!active) {
          return;
        }
        setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (!active || error.code === 'ERR_CANCELED' || error.name === 'CanceledError') {
          return;
        }
        setState({ loading: false, error, data: null });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [period, organizationId, user, ready, retry]);

  const seriesList = state.data?.series || [];
  useEffect(() => {
    if (!seriesList.length) {
      setIndicator(null);
      return;
    }
    setIndicator((current) => (
      seriesList.some((item) => item.code === current) ? current : seriesList[0].code
    ));
  }, [seriesList]);

  const selectedSeries = useMemo(
    () => seriesList.find((item) => item.code === indicator) || null,
    [seriesList, indicator],
  );

  const periodLabel = period === '12' ? '12 месяцев' : period === '6' ? '6 месяцев' : '3 месяца';
  const analysisHref = state.data?.dataset?.id
    ? `/analysis?datasetId=${state.data.dataset.id}`
    : '/analysis';
  const resultsHref = state.data?.analysis_run_id ? `/analysis/${state.data.analysis_run_id}` : null;

  if (!ready || (user && state.loading && !state.data)) {
    return (
      <div className="page">
        <LoadingState title="Загрузка панели" description="Запрос к серверу, без повторных опросов." />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="page">
        <EmptyState
          title="Требуется вход"
          description="Главная панель показывает сохранённые показатели и результаты исследования. Войдите, чтобы загрузить данные."
          action={<Link to="/login" className="button">Войти</Link>}
        />
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="page">
        <ErrorMessage
          message={errorMessage(state.error)}
          onRetry={() => setRetry((value) => value + 1)}
        />
      </div>
    );
  }

  const data = state.data;
  if (!data || data.empty) {
    return (
      <div className="page">
        <div className="page__header">
          <div>
            <h1>Рабочая панель</h1>
            <p className="page__lead">{periodLabel}. Загрузите данные и запустите исследование.</p>
          </div>
        </div>
        <OrganizationSnapshots
          items={data?.organization_snapshots}
          currentId={organizationId}
          onSelect={setOrganizationId}
        />
        <EmptyState
          title="Нет данных"
          description={data?.message || 'Выберите организацию и загрузите таблицу показателей.'}
          action={<Link to="/data" className="button">Загрузить данные</Link>}
        />
      </div>
    );
  }

  const runColumns = [
    { key: 'created_at', title: 'Дата', render: (row) => formatDateTime(row.created_at) },
    { key: 'dataset_name', title: 'Набор', render: (row) => <span className="cell-wrap" title={row.dataset_name}>{row.dataset_name}</span> },
    { key: 'status', title: 'Статус', render: (row) => analysisStatusLabel(row.status) },
    {
      key: 'open',
      title: '',
      render: (row) => <Link to={`/analysis/${row.id}`}>Открыть</Link>,
    },
  ];

  const workspaceLabel = {
    unverified: 'Данные загружены, требуется проверка качества.',
    data_only: 'Данные есть, исследование ещё не запускалось.',
    problems: 'Есть предупреждения высокого уровня.',
    ok: 'Критических предупреждений нет.',
  }[data.workspace_state] || null;
  const selectedCard = (data.cards || []).find((card) => card.code === indicator);
  const chartCaption = selectedCard?.change_percent == null
    ? 'Горизонт по сохранённому прогнозу'
    : `Прирост к предыдущему периоду: ${formatPercent(selectedCard.change_percent, { signed: true })}`;
  const accentCode = (data.cards || []).some((card) => card.code === 'revenue')
    ? 'revenue'
    : data.cards?.[0]?.code;

  return (
    <div className="page">
      <div className="page__header">
        <div>
            <h1>Рабочая панель</h1>
          <p className="page__lead">
            {data.organization?.name || 'Организация не выбрана'}
            {data.dataset?.name ? ` · ${data.dataset.name}` : ''}
            · {periodLabel}
          </p>
        </div>
        <div className="page-actions">
          {resultsHref ? <Link to={resultsHref} className="button button--ghost">Открыть последнее исследование</Link> : null}
          <Link to={analysisHref} className="button">{resultsHref ? 'Новый расчёт этого набора' : 'Запустить исследование'}</Link>
        </div>
      </div>

      <OrganizationSnapshots
        items={data.organization_snapshots}
        currentId={data.organization?.id || organizationId}
        onSelect={setOrganizationId}
      />

      {workspaceLabel ? (
        <p className="workspace-meta">
          <span>{workspaceLabel}</span>
          <span>Проблемы: {data.findings_count ?? 0}</span>
          <span>Предупреждения: {data.alerts_count ?? 0}</span>
          <span>Рекомендации: {data.proposed_recommendations ?? 0}</span>
          <span>Открытые мероприятия: {data.open_measures ?? 0}</span>
          <span>Просрочено: {data.overdue_measures ?? 0}</span>
        </p>
      ) : null}

      <div className="page-actions">
        <Link to="/recommendations" className="button button--ghost">Рекомендации</Link>
        <Link to="/measures" className="button button--ghost">Мероприятия</Link>
        <Link to="/scenarios" className="button button--ghost">Сценарии</Link>
        <Link to="/norms" className="button button--ghost">Нормативы</Link>
      </div>

      <div className="home-metrics">
        {data.cards.map((card) => {
          const Icon = KPI_ICONS[card.code];
          return (
            <MetricCard
              key={card.code}
              accent={card.code === accentCode}
              title={card.name}
              icon={Icon ? <Icon /> : null}
              value={card.value == null ? null : formatMoney(card.value, card.unit)}
              change={card.change_percent == null ? null : formatPercent(card.change_percent, { signed: true })}
              direction={card.change_direction}
              favorable={card.change_favorable}
            />
          );
        })}
      </div>

      <div className="home-workspace">
        <div className="home-primary">
          <section className="card">
            <header className="card__header">
              <h2 className="card__title">Динамика показателя</h2>
            </header>
            <div className="card__body">
              <div className="chart-card__tools">
                <div className="tabs" role="tablist" aria-label="Показатель графика">
                  {seriesList.map((item) => (
                    <button
                      key={item.code}
                      type="button"
                      className={`tab${item.code === indicator ? ' tab--active' : ''}`}
                      title={item.name}
                      onClick={() => setIndicator(item.code)}
                    >
                      <span className="tab__label">{item.name}</span>
                    </button>
                  ))}
                </div>
                <span className="chart-caption">{chartCaption}</span>
              </div>
              {selectedSeries && (selectedSeries.history.length || selectedSeries.forecast.length) ? (
                <DynamicsChart series={selectedSeries} />
              ) : (
                <EmptyState
                  title="График недоступен"
                  description="Загрузите значения показателя."
                />
              )}
            </div>
          </section>

          <RiskFactors factors={data.assessment?.factors} />

          <section className="card">
            <header className="card__header">
              <h2 className="card__title">Аномалии</h2>
            </header>
            <DataTable
              columns={ANOMALY_COLUMNS}
              rows={data.anomalies}
              emptyTitle="Аномалий нет"
            />
          </section>
        </div>

        <aside className="home-rail">
          <ChartPanel title="Сводная оценка">
            <AssessmentPanel assessment={data.assessment} />
          </ChartPanel>
          <ChartPanel
            title="Корреляция"
            emptyTitle="Нет данных"
          >
            {data.correlations?.pairs?.length ? (
              <CorrelationHeatmap correlations={data.correlations} />
            ) : null}
          </ChartPanel>
          <section className="card">
            <header className="card__header">
              <h2 className="card__title">Последние результаты</h2>
            </header>
            <DataTable
              columns={runColumns}
              rows={data.recent_runs}
              emptyTitle="История пуста"
            />
          </section>
        </aside>
      </div>
    </div>
  );
}

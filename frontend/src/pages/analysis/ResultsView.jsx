import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  createAnalysisPdf, deleteAnalysis, downloadReportContent,
} from '../../api/analysesApi.js';
import { fetchDatasetValues } from '../../api/datasetsApi.js';
import { errorMessage } from '../../api/httpClient.js';
import ChartPanel from '../../components/ui/ChartPanel.jsx';
import ConfirmDialog from '../../components/ui/ConfirmDialog.jsx';
import DataTable from '../../components/ui/DataTable.jsx';
import NarrativeBlock from '../../components/ui/NarrativeBlock.jsx';
import Notice from '../../components/ui/Notice.jsx';
import { downloadBlob } from '../../lib/csv.js';
import { analysisStatusLabel, formatDateTime, formatNumber, interpretScore, procedureLabel } from '../../lib/format.js';
import AssessmentPanel from '../home/AssessmentPanel.jsx';
import CorrelationHeatmap, { heatmapFromPairs } from '../home/CorrelationHeatmap.jsx';
import DynamicsChart from '../home/DynamicsChart.jsx';
import ClusterScatter from './ClusterScatter.jsx';

const TABS = [
  { id: 'conclusion', label: 'Заключение' },
  { id: 'assessment', label: 'Оценка' },
  { id: 'ratios', label: 'Коэффициенты' },
  { id: 'trends', label: 'Тенденции' },
  { id: 'findings', label: 'Проблемы' },
  { id: 'anomalies', label: 'Аномалии' },
  { id: 'correlation', label: 'Корреляции' },
  { id: 'clusters', label: 'Кластеры' },
  { id: 'forecast', label: 'Прогноз' },
  { id: 'status', label: 'Ход расчёта' },
];

function indicatorName(run, code) {
  return run?.indicators?.find((item) => item.code === code)?.name || code;
}

function directionLabel(direction) {
  if (direction === 'above') {
    return 'Выше типичного уровня';
  }
  if (direction === 'below') {
    return 'Ниже типичного уровня';
  }
  return direction || '—';
}

function correlationStrength(value) {
  if (value == null) {
    return 'нет оценки';
  }
  const magnitude = Math.abs(Number(value));
  if (magnitude >= 0.7) {
    return 'сильная';
  }
  if (magnitude >= 0.4) {
    return 'умеренная';
  }
  return 'слабая';
}

export default function ResultsView({ data }) {
  const {
    run, anomalies, correlation, clustering, forecast, assessment, conclusion,
    trends, ratios, findings, alerts,
    assessment_narrative: assessmentNarrative,
    anomalies_narrative: anomaliesNarrative,
    correlation_narrative: correlationNarrative,
    clustering_narrative: clusteringNarrative,
    forecast_narrative: forecastNarrative,
  } = data || {};
  const navigate = useNavigate();
  const [tab, setTab] = useState('conclusion');
  const [history, setHistory] = useState([]);
  const [forecastCode, setForecastCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [confirm, setConfirm] = useState(null);

  useEffect(() => {
    if (!run?.dataset_id) {
      setHistory([]);
      return undefined;
    }
    let active = true;
    fetchDatasetValues(run.dataset_id)
      .then((page) => {
        if (active) {
          setHistory(page.items || []);
        }
      })
      .catch(() => {
        if (active) {
          setHistory([]);
        }
      });
    return () => {
      active = false;
    };
  }, [run?.dataset_id]);

  useEffect(() => {
    setForecastCode(forecast?.series?.[0]?.indicator || '');
  }, [forecast]);

  async function onPdf() {
    setBusy(true);
    setNotice(null);
    try {
      const report = await createAnalysisPdf(run.id);
      const response = await downloadReportContent(report.id);
      downloadBlob(`crisis-control-${run.id}.pdf`, response.data);
    } catch (error) {
      setNotice({ tone: 'warning', title: 'PDF не сформирован', text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  const names = useMemo(
    () => Object.fromEntries((run?.indicators || []).map((item) => [item.code, item.name])),
    [run?.indicators],
  );

  const heatmap = useMemo(
    () => heatmapFromPairs(correlation?.pairs, names, correlation?.interpretation),
    [correlation, names],
  );

  const selectedForecast = (forecast?.series || []).find((item) => item.indicator === forecastCode) || forecast?.series?.[0];

  const forecastSeries = useMemo(() => {
    if (!selectedForecast) {
      return null;
    }
    const points = history
      .filter((row) => row.indicator_code === selectedForecast.indicator)
      .sort((a, b) => String(a.period_start).localeCompare(String(b.period_start)))
      .map((row) => ({
        period_start: row.period_start,
        label: row.period_start,
        value: row.value == null ? null : Number(row.value),
        kind: 'history',
      }));
    return {
      code: selectedForecast.indicator,
      name: indicatorName(run, selectedForecast.indicator),
      history: points,
      forecast: (selectedForecast.points || []).map((point) => ({
        period_start: point.period_start,
        label: point.period_start,
        value: Number(point.value),
        lower: point.lower_bound == null ? null : Number(point.lower_bound),
        upper: point.upper_bound == null ? null : Number(point.upper_bound),
        kind: 'forecast',
      })),
    };
  }, [selectedForecast, history, run]);

  if (!run) {
    return (
      <div className="page">
        <Notice tone="warning" title="Нет данных исследования">
          Откройте запуск из истории или выполните расчёт заново.
        </Notice>
        <div className="page-actions">
          <Link to="/analysis" className="button button--ghost">К запуску</Link>
          <Link to="/reports" className="button">К истории</Link>
        </div>
      </div>
    );
  }

  const assessmentView = assessment?.score != null ? {
    score: assessment.score,
    history_score: assessment.history_score,
    compliance_score: assessment.compliance_score,
    completeness: assessment.completeness,
    interpretation: assessment.interpretation || interpretScore(assessment.score) || 'Рассчитано',
    warning: assessment.message,
    methodology: assessment.methodology,
    groups: [],
    factors: (assessment.components || []).map((item) => ({
      code: item.indicator,
      name: item.indicator_name,
      normalized_score: item.normalized_score,
      contribution: item.contribution,
      explanation: item.explanation,
    })),
  } : assessment ? {
    score: null,
    warning: assessment.message || 'Недостаточно данных',
    groups: [],
    factors: [],
  } : null;

  const strongPairs = (correlation?.pairs || [])
    .filter((item) => item.coefficient != null)
    .sort((a, b) => Math.abs(b.coefficient) - Math.abs(a.coefficient));

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Исследование №{run.id}</h1>
          <p className="page__lead">
            {[run.organization_name, run.dataset_name, analysisStatusLabel(run.status)].filter(Boolean).join(' · ')}
            {'. '}
            {run.period_from} — {run.period_to}. {formatDateTime(run.created_at)}.
          </p>
        </div>
        <div className="page-actions">
          <Link to="/reports" className="button button--ghost">История</Link>
          <button type="button" className="button button--ghost" disabled={busy} onClick={onPdf}>
            {busy ? 'Формирование…' : 'PDF-отчёт'}
          </button>
          <Link to={`/analysis?datasetId=${run.dataset_id}`} className="button">Новый запуск этого набора</Link>
          <button type="button" className="button button--danger" onClick={() => setConfirm('delete-run')}>
            Удалить исследование
          </button>
        </div>
      </div>

      {run.error_message ? <Notice tone="warning" title="Сообщение о запуске">{run.error_message}</Notice> : null}
      {notice ? <Notice tone={notice.tone} title={notice.title}>{notice.text}</Notice> : null}

      <div className="tabs" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tab${tab === item.id ? ' tab--active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'conclusion' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Заключение</h2></header>
          <div className="card__body">
            <p>{conclusion?.summary || 'Заключение появится после расчёта процедур.'}</p>
            {(conclusion?.highlights || []).length ? (
              <ul className="issue-list">
                {conclusion.highlights.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : null}
          </div>
          {(conclusion?.limitations || []).length ? (
            <div className="card__body">
              <div className="field__label">Ограничения</div>
              <ul className="issue-list">
                {conclusion.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
        </section>
      )}

      {tab === 'assessment' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Сводная оценка 0–100</h2></header>
          <div className="card__body assessment-layout">
            <div className="assessment-layout__score">
              <AssessmentPanel compact assessment={assessmentView} />
              <NarrativeBlock narrative={assessmentNarrative} hideDetails />
            </div>
            <div className="assessment-layout__table">
              {(assessment?.components || []).length ? (
                <DataTable
                  sortable
                  columns={[
                    { key: 'indicator_name', title: 'Показатель' },
                    { key: 'normalized_score', title: 'Балл 0–100', render: (row) => formatNumber(Number(row.normalized_score) * 100, 0) },
                    { key: 'contribution', title: 'Вклад', render: (row) => formatNumber(row.contribution, 1) },
                    { key: 'explanation', title: 'Пояснение', render: (row) => <span className="cell-wrap" title={row.explanation}>{row.explanation}</span> },
                  ]}
                  rows={assessment.components}
                  rowKey="indicator"
                />
              ) : (
                <p className="muted">{assessment?.message || 'Компоненты оценки не рассчитаны.'}</p>
              )}
            </div>
          </div>
        </section>
      )}

      {tab === 'ratios' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Коэффициенты</h2></header>
          <DataTable
            sortable
            columns={[
              { key: 'name', title: 'Коэффициент' },
              { key: 'category', title: 'Группа' },
              { key: 'last_value', title: 'Факт', render: (row) => formatNumber(row.last_value) },
              { key: 'previous_value', title: 'Предыдущий', render: (row) => formatNumber(row.previous_value) },
              { key: 'pct_change', title: 'Изменение, %', render: (row) => formatNumber(row.pct_change) },
              { key: 'formula', title: 'Формула' },
            ]}
            rows={ratios?.items || []}
            emptyTitle="Нет рассчитанных коэффициентов"
            emptyDescription={ratios?.message || 'Для выбранных рядов исходных данных недостаточно.'}
          />
        </section>
      )}

      {tab === 'trends' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Тенденции</h2></header>
          <DataTable
            sortable
            columns={[
              { key: 'indicator', title: 'Показатель', render: (row) => indicatorName(run, row.indicator) },
              { key: 'label', title: 'Описание' },
              { key: 'pct_change', title: 'Прирост, %', render: (row) => formatNumber(row.pct_change) },
              { key: 'consecutive_worsening', title: 'Непрерывное ухудшение' },
              { key: 'significant', title: 'Значимость', render: (row) => (row.significant ? 'да' : 'нет') },
            ]}
            rows={trends?.items || []}
            emptyTitle="Тенденции не рассчитаны"
            emptyDescription={trends?.message || 'Недостаточно наблюдений или процедура не входила в запуск.'}
          />
        </section>
      )}

      {tab === 'findings' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Проблемы и предупреждения</h2></header>
          <DataTable
            columns={[
              { key: 'title', title: 'Проблема' },
              { key: 'severity', title: 'Уровень' },
              { key: 'confidence', title: 'Уверенность' },
              { key: 'period_label', title: 'Период' },
              { key: 'description', title: 'Основание' },
            ]}
            rows={findings || []}
            emptyTitle="Проблем нет"
          />
          <DataTable
            columns={[
              { key: 'level', title: 'Уровень' },
              { key: 'indicator_code', title: 'Показатель' },
              { key: 'message', title: 'Сообщение' },
              { key: 'basis', title: 'Основание' },
              { key: 'action', title: 'Рекомендуемое действие' },
            ]}
            rows={alerts || []}
            emptyTitle="Предупреждений нет"
          />
        </section>
      )}

      {tab === 'anomalies' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Аномалии</h2></header>
          <div className="card__body">
            <NarrativeBlock narrative={anomaliesNarrative} />
          </div>
          <DataTable
            sortable
            filterable
            columns={[
              { key: 'indicator_name', title: 'Показатель', render: (row) => <span className="cell-wrap" title={row.indicator_name}>{row.indicator_name}</span> },
              { key: 'period_start', title: 'Период' },
              { key: 'value', title: 'Факт', render: (row) => formatNumber(row.value), sortValue: (row) => Number(row.value) },
              { key: 'baseline', title: 'Типичный уровень', render: (row) => formatNumber(row.baseline), sortValue: (row) => Number(row.baseline) },
              { key: 'deviation', title: 'Отклонение', render: (row) => formatNumber(row.deviation), sortValue: (row) => Number(row.deviation) },
              { key: 'direction', title: 'Характер', render: (row) => directionLabel(row.direction) },
              {
                key: 'chart',
                title: '',
                render: (row) => (
                  <button
                    type="button"
                    className="button button--ghost button--compact"
                    onClick={() => {
                      setForecastCode(row.indicator);
                      setTab('forecast');
                    }}
                  >
                    К динамике
                  </button>
                ),
              },
            ]}
            rows={anomalies?.items || []}
            emptyTitle="Аномалии не найдены"
            emptyDescription={anomalies?.message || 'Процедура не нашла статистических выбросов либо не запускалась.'}
          />
        </section>
      )}

      {tab === 'correlation' && (
        <>
          <ChartPanel title="Матрица корреляций" emptyTitle="Корреляции не рассчитаны" emptyDescription={correlation?.message}>
            <NarrativeBlock narrative={correlationNarrative} />
            {heatmap.pairs.length ? <CorrelationHeatmap correlations={heatmap} /> : null}
          </ChartPanel>
          <section className="card">
            <DataTable
              columns={[
                { key: 'indicator_a', title: 'Показатель A', render: (row) => names[row.indicator_a] || row.indicator_a },
                { key: 'indicator_b', title: 'Показатель B', render: (row) => names[row.indicator_b] || row.indicator_b },
                { key: 'coefficient', title: 'Коэффициент', render: (row) => formatNumber(row.coefficient, 2) },
                { key: 'strength', title: 'Выраженность', render: (row) => correlationStrength(row.coefficient) },
              ]}
              rows={strongPairs}
              emptyTitle="Нет пар"
            />
          </section>
        </>
      )}

      {tab === 'clusters' && (
        <>
          <ChartPanel title="Распределение наблюдений" emptyTitle="Кластеры не построены" emptyDescription={clustering?.message || clustering?.interpretation}>
            <NarrativeBlock narrative={clusteringNarrative} />
            {clustering?.members?.length ? (
              <ClusterScatter members={clustering.members} clusters={clustering.clusters} />
            ) : null}
          </ChartPanel>
          <section className="card">
            <header className="card__header"><h2 className="card__title">Группы периодов</h2></header>
            <p className="card__body muted">{clustering?.interpretation}</p>
            <DataTable
              sortable
              columns={[
                { key: 'cluster', title: 'Группа' },
                { key: 'size', title: 'Наблюдений' },
                { key: 'label', title: 'Подпись', render: (row) => row.label || '—' },
              ]}
              rows={clustering?.clusters || []}
              rowKey="cluster"
              emptyTitle="Нет групп"
            />
          </section>
        </>
      )}

      {tab === 'forecast' && (
        <ChartPanel title="История и прогноз" emptyTitle="Прогноз отсутствует" emptyDescription={forecast?.message}>
          <NarrativeBlock narrative={forecastNarrative} />
          {(forecast?.series || []).length > 1 ? (
            <label className="field" style={{ marginBottom: 12 }}>
              <span className="field__label">Показатель</span>
              <select className="select" value={forecastCode} onChange={(event) => setForecastCode(event.target.value)}>
                {forecast.series.map((item) => (
                  <option key={item.indicator} value={item.indicator}>{indicatorName(run, item.indicator)}</option>
                ))}
              </select>
            </label>
          ) : null}
          {forecastSeries ? <DynamicsChart series={forecastSeries} /> : null}
          <p className="muted">Пунктир — прогноз ({selectedForecast?.points?.length || 0} шаг.).</p>
        </ChartPanel>
      )}

      {tab === 'status' && (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Процедуры</h2></header>
          <DataTable
            sortable
            columns={[
              { key: 'procedure_type', title: 'Процедура', render: (row) => procedureLabel(row.procedure_type) },
              { key: 'status', title: 'Статус', render: (row) => procedureLabel(row.status) },
              { key: 'message', title: 'Сообщение' },
            ]}
            rows={run.procedures || []}
            rowKey="id"
            emptyTitle="Нет процедур"
          />
        </section>
      )}

      <ConfirmDialog
        open={confirm === 'delete-run'}
        danger
        title="Удалить это исследование?"
        message="Будут удалены результаты выбранного запуска и связанные отчёты. Набор данных сохранится, его можно проанализировать заново. Другие организации не затрагиваются."
        confirmLabel="Удалить исследование"
        onCancel={() => setConfirm(null)}
        onConfirm={async () => {
          setBusy(true);
          try {
            await deleteAnalysis(run.id);
            navigate('/reports');
          } catch (error) {
            setNotice({ tone: 'warning', title: 'Не удалось удалить', text: errorMessage(error) });
            setConfirm(null);
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';
import { startAnalysis } from '../../api/analysesApi.js';
import { fetchDataset, fetchDatasets } from '../../api/datasetsApi.js';
import { errorDetails, errorMessage } from '../../api/httpClient.js';
import ErrorMessage from '../../components/ui/ErrorMessage.jsx';
import Hint from '../../components/ui/Hint.jsx';
import LoadingState from '../../components/ui/LoadingState.jsx';
import Notice from '../../components/ui/Notice.jsx';

const PROCEDURES = [
  { id: 'ratios', label: 'Коэффициенты', hint: 'Производные показатели по каталогу.' },
  { id: 'anomalies', label: 'Аномалии', hint: 'Значения далеко от типичного уровня ряда.' },
  { id: 'trends', label: 'Тенденции', hint: 'Направление изменения показателя.' },
  { id: 'correlation', label: 'Корреляции', hint: 'Совместное движение рядов.' },
  { id: 'clustering', label: 'Кластеры периодов', hint: 'Группы месяцев с похожим сочетанием показателей.' },
  { id: 'forecast', label: 'Прогноз', hint: 'Короткая экстраполяция ряда.' },
  { id: 'assessment', label: 'Сводная оценка', hint: 'Балл 0–100 по истории и заданным нормативам.' },
];

export default function LaunchForm() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const presetDatasetId = params.get('datasetId') || '';
  const { organizationId, organizations = [], canEdit, selectedOrganization } = useOutletContext() ?? {};
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState(presetDatasetId);
  const [detail, setDetail] = useState(null);
  const [selected, setSelected] = useState([]);
  const [periodFrom, setPeriodFrom] = useState('');
  const [periodTo, setPeriodTo] = useState('');
  const [procedures, setProcedures] = useState(PROCEDURES.map((item) => item.id));
  const [anomalies, setAnomalies] = useState({ method: 'robust_z', threshold: 3, min_observations: 6 });
  const [correlation, setCorrelation] = useState({ method: 'pearson', min_observations: 4 });
  const [clustering, setClustering] = useState({ k: 'auto', k_min: 2, k_max: 6 });
  const [forecast, setForecast] = useState({ horizon: 3, model: 'auto' });
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchDatasets({ organizationId, limit: 100 })
      .then((page) => {
        if (!active) {
          return;
        }
        setDatasets(page.items || []);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [organizationId]);

  const visibleDatasets = useMemo(
    () => (organizationId ? datasets.filter((item) => String(item.organization_id) === String(organizationId)) : datasets),
    [datasets, organizationId],
  );

  useEffect(() => {
    if (presetDatasetId) {
      setDatasetId(presetDatasetId);
      return;
    }
    if (!visibleDatasets.length) {
      setDatasetId('');
      return;
    }
    setDatasetId((current) => (
      visibleDatasets.some((item) => String(item.id) === String(current)) ? current : String(visibleDatasets[0].id)
    ));
  }, [visibleDatasets, presetDatasetId]);

  useEffect(() => {
    if (!datasetId) {
      setDetail(null);
      return undefined;
    }
    let active = true;
    fetchDataset(datasetId)
      .then((data) => {
        if (!active) {
          return;
        }
        setDetail(data);
        setSelected((data.indicators || []).map((item) => item.code));
        setPeriodFrom(data.period_from || '');
        setPeriodTo(data.period_to || '');
      })
      .catch((err) => setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, [datasetId]);

  const canSubmit = useMemo(() => (
    datasetId && selected.length > 0 && procedures.length > 0 && periodFrom && periodTo && !pending && canEdit
  ), [datasetId, selected, procedures, periodFrom, periodTo, pending, canEdit]);

  function toggle(list, value, setter) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!canSubmit) {
      setError('Проверьте набор, период, показатели и выбранные процедуры.');
      return;
    }
    setPending(true);
    setError(null);
    try {
      const payload = {
        dataset_id: Number(datasetId),
        period_from: periodFrom,
        period_to: periodTo,
        indicators: selected.map((code) => ({ code })),
        procedures: ['validate', ...procedures],
        anomalies,
        correlation,
        clustering: {
          k: clustering.k === 'auto' ? 'auto' : Number(clustering.k),
          k_min: Number(clustering.k_min),
          k_max: Number(clustering.k_max),
        },
        forecast: { horizon: Number(forecast.horizon), model: forecast.model },
      };
      const run = await startAnalysis(payload);
      navigate(`/analysis/${run.id}`, { state: { run } });
    } catch (err) {
      const extra = errorDetails(err);
      const hint = extra && typeof extra === 'object' && extra.run_id
        ? ` Сохранён запуск №${extra.run_id} со статусом ошибки.`
        : '';
      setError(`${errorMessage(err)}${hint}`);
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return <LoadingState title="Подготовка запуска" description="Загружаем список наборов выбранной организации." />;
  }
  if (!visibleDatasets.length) {
    return (
      <Notice tone="warning" title="Нет наборов данных">
        Сначала загрузите файл в разделе «Наборы данных».
        <div className="page-actions" style={{ marginTop: 8 }}>
          <Link className="button" to="/data">Перейти к загрузке</Link>
        </div>
      </Notice>
    );
  }

  const locked = Boolean(presetDatasetId);

  return (
    <form onSubmit={onSubmit}>
      {error ? <ErrorMessage message={error} /> : null}
      {!canEdit ? (
        <Notice tone="warning" title="Запуск недоступен">
          Для организации «{selectedOrganization?.name || '—'}» у вас право просмотра. Расчёт может запустить сотрудник с правом редактирования.
        </Notice>
      ) : null}
      {pending ? (
        <Notice tone="info" title="Расчёт выполняется">Дождитесь ответа сервера.</Notice>
      ) : null}

      <section className="card">
        <header className="card__header"><h2 className="card__title">Основные параметры</h2></header>
        {organizations.length > 1 && !locked ? (
          <div className="card__body">
            <p className="muted">Организация задаётся переключателем в шапке.</p>
          </div>
        ) : null}
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Набор данных</span>
            {locked ? (
              <input className="input" value={detail?.name || `Набор №${datasetId}`} readOnly />
            ) : (
              <select className="select" value={datasetId} onChange={(event) => setDatasetId(event.target.value)} required>
                {visibleDatasets.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}{item.version_no ? ` · версия ${item.version_no}` : ''}
                  </option>
                ))}
              </select>
            )}
            <Hint>
              {locked
                ? 'Набор выбран на предыдущем шаге.'
                : 'Нужно не менее трёх периодов. Повторная загрузка с тем же именем создаёт новую версию.'}
            </Hint>
          </label>
          <label className="field">
            <span className="field__label">Начало периода</span>
            <input className="input" type="date" value={periodFrom} onChange={(event) => setPeriodFrom(event.target.value)} required />
          </label>
          <label className="field">
            <span className="field__label">Конец периода</span>
            <input className="input" type="date" value={periodTo} onChange={(event) => setPeriodTo(event.target.value)} required />
          </label>
        </div>
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Показатели</h2></header>
        <div className="card__body checkbox-grid">
          {(detail?.indicators || []).map((item) => (
            <label key={item.code} className="check">
              <input
                type="checkbox"
                checked={selected.includes(item.code)}
                onChange={() => toggle(selected, item.code, setSelected)}
              />
              <span title={item.name}>{item.name}{item.unit ? `, ${item.unit}` : ''}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Процедуры исследования</h2></header>
        <div className="card__body checkbox-grid">
          {PROCEDURES.map((item) => (
            <label key={item.id} className="check">
              <input
                type="checkbox"
                checked={procedures.includes(item.id)}
                onChange={() => toggle(procedures, item.id, setProcedures)}
                disabled={pending}
              />
              <span>
                {item.label}
                <Hint>{item.hint}</Hint>
              </span>
            </label>
          ))}
        </div>
      </section>

      <details className="details-block">
        <summary>Дополнительные настройки</summary>
        <div className="card__body form-grid">
          <label className="field">
            <span className="field__label">Как искать аномалии</span>
            <select className="select" value={anomalies.method} onChange={(event) => setAnomalies({ ...anomalies, method: event.target.value })}>
              <option value="robust_z">Устойчивый метод (рекомендуется)</option>
              <option value="zscore">Отклонение от среднего</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Порог аномалии</span>
            <input className="input" type="number" min="0.1" max="10" step="0.1" value={anomalies.threshold} onChange={(event) => setAnomalies({ ...anomalies, threshold: Number(event.target.value) })} required />
          </label>
          <label className="field">
            <span className="field__label">Минимум точек для аномалий</span>
            <input className="input" type="number" min="3" max="24" value={anomalies.min_observations} onChange={(event) => setAnomalies({ ...anomalies, min_observations: Number(event.target.value) })} required />
          </label>
          <label className="field">
            <span className="field__label">Метод корреляции</span>
            <select className="select" value={correlation.method} onChange={(event) => setCorrelation({ ...correlation, method: event.target.value })}>
              <option value="pearson">Пирсон</option>
              <option value="spearman">Спирмен</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Минимум точек для корреляции</span>
            <input className="input" type="number" min="3" max="24" value={correlation.min_observations} onChange={(event) => setCorrelation({ ...correlation, min_observations: Number(event.target.value) })} required />
          </label>
          <label className="field">
            <span className="field__label">Число групп периодов</span>
            <select className="select" value={clustering.k} onChange={(event) => setClustering({ ...clustering, k: event.target.value })}>
              <option value="auto">Подобрать автоматически</option>
              {[2, 3, 4, 5, 6].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Модель прогноза</span>
            <select className="select" value={forecast.model} onChange={(event) => setForecast({ ...forecast, model: event.target.value })}>
              <option value="auto">Автоматический выбор</option>
              <option value="ses">Экспоненциальное сглаживание</option>
              <option value="holt">Хольт (линейный тренд)</option>
              <option value="seasonal">Сезонная модель</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Горизонт прогноза</span>
            <input className="input" type="number" min="1" max="24" value={forecast.horizon} onChange={(event) => setForecast({ ...forecast, horizon: Number(event.target.value) })} required />
          </label>
        </div>
      </details>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Подтверждение</h2></header>
        <div className="card__body muted">
          {detail?.name || '—'}. {periodFrom} — {periodTo}. Показателей: {selected.length}.
        </div>
      </section>
      <div>
        <button type="submit" className="button" disabled={!canSubmit}>
          {pending ? 'Выполняется расчёт…' : 'Запустить исследование'}
        </button>
      </div>
    </form>
  );
}

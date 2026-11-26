import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { startAnalysis } from '../api/analysesApi.js';
import {
  downloadTemplate, fetchDatasets, fetchDemoInfo, importDataset, importDemoDataset, previewDataset, validatePreview,
} from '../api/datasetsApi.js';
import { errorMessage } from '../api/httpClient.js';
import DataTable from '../components/ui/DataTable.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import Hint from '../components/ui/Hint.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import Notice from '../components/ui/Notice.jsx';
import { downloadBlob } from '../lib/csv.js';
import { formatDateTime } from '../lib/format.js';
import './pages.css';

export default function DataPage() {
  const { organizationId, organizations = [], selectedOrganization, canEdit } = useOutletContext() ?? {};
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const [datasets, setDatasets] = useState([]);
  const [preview, setPreview] = useState(null);
  const [stagingIds, setStagingIds] = useState([]);
  const [periodColumn, setPeriodColumn] = useState('');
  const [indicatorColumns, setIndicatorColumns] = useState([]);
  const [datasetName, setDatasetName] = useState('');
  const [quality, setQuality] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('');
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [demoInfo, setDemoInfo] = useState(null);

  const visibleDatasets = datasets.filter((item) => (
    !organizationId || String(item.organization_id) === String(organizationId)
  ));

  async function reloadLists() {
    const sets = await fetchDatasets({ organizationId, limit: 100 });
    setDatasets(sets.items || []);
  }

  useEffect(() => {
    setLoading(true);
    reloadLists()
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
    fetchDemoInfo().then(setDemoInfo).catch(() => setDemoInfo(null));
  }, [organizationId]);

  async function onDemo() {
    if (!organizationId) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const created = await importDemoDataset(organizationId);
      setStatus('Загружен демонстрационный набор. Запускаем исследование…');
      await reloadLists();
      try {
        const run = await startAnalysis({ dataset_id: created.id });
        navigate(`/analysis/${run.id}`, { state: { run } });
      } catch {
        navigate(`/data/${created.id}`, { state: { justSaved: true } });
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onFiles(fileList) {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) {
      return;
    }
    setPending(true);
    setError(null);
    setQuality(null);
    setStatus(files.length > 1 ? `Проверяем ${files.length} файла…` : 'Проверяем структуру файла…');
    try {
      const previews = [];
      for (const file of files) {
        previews.push(await previewDataset(file));
      }
      const data = previews[0];
      const indicators = [];
      const seen = new Set();
      for (const item of previews) {
        for (const indicator of item.suggested_indicators || []) {
          if (!seen.has(indicator.column)) {
            seen.add(indicator.column);
            indicators.push(indicator);
          }
        }
      }
      const ids = previews.map((item) => item.staging_id);
      setPreview({
        ...data,
        suggested_indicators: indicators,
        source_files: files.map((file) => file.name),
      });
      setStagingIds(ids);
      setPeriodColumn(data.suggested_period_column || '');
      setIndicatorColumns(indicators.map((item) => item.column));
      setDatasetName(files[0].name.replace(/\.(csv|xlsx)$/i, ''));
      setStatus('Файлы загружены. Проверяем качество…');
      const report = await validatePreview({
        staging_id: ids[0],
        period_column: data.suggested_period_column || null,
        indicator_columns: indicators.map((item) => item.column),
      });
      setQuality(report);
      setStatus(report.ready_for_analysis
        ? (files.length > 1
          ? 'Проверка первого файла пройдена. При сохранении таблицы объединятся по периоду и показателю.'
          : 'Проверка пройдена. Можно сохранить набор.')
        : 'Обнаружены ошибки. Исправьте файл и загрузите его снова.');
    } catch (err) {
      setPreview(null);
      setStagingIds([]);
      setStatus('');
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onValidate() {
    if (!preview) {
      setError('Сначала выберите файл.');
      return;
    }
    setPending(true);
    setError(null);
    setStatus('Повторная проверка качества…');
    try {
      const report = await validatePreview({
        staging_id: preview.staging_id,
        period_column: periodColumn || null,
        indicator_columns: indicatorColumns,
      });
      setQuality(report);
      setStatus(report.ready_for_analysis
        ? 'Проверка пройдена. Можно сохранить набор.'
        : 'Файл не готов к сохранению: смотрите список замечаний.');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onImport(event) {
    event.preventDefault();
    if (!preview || !organizationId || !datasetName.trim()) {
      setError('Укажите имя набора и дождитесь разбора файла.');
      return;
    }
    if (quality && quality.ready_for_analysis === false) {
      setError('Исправьте ошибки проверки до сохранения.');
      return;
    }
    setPending(true);
    setError(null);
    setStatus('Сохраняем набор…');
    try {
      const saved = await importDataset(organizationId, {
        staging_id: stagingIds[0] || preview.staging_id,
        staging_ids: stagingIds.length ? stagingIds : undefined,
        name: datasetName.trim(),
        period_column: periodColumn || null,
        indicator_columns: indicatorColumns,
        merge_previous: true,
      });
      setStatus('Набор сохранён только для выбранной организации. Запускаем исследование…');
      try {
        const run = await startAnalysis({ dataset_id: saved.id });
        navigate(`/analysis/${run.id}`, { state: { run } });
      } catch {
        navigate(`/data/${saved.id}`, { state: { justSaved: true } });
      }
    } catch (err) {
      setError(errorMessage(err));
      setStatus('');
    } finally {
      setPending(false);
    }
  }

  async function onTemplate() {
    try {
      const response = await downloadTemplate('csv');
      downloadBlob('template.csv', response.data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const previewColumns = (preview?.columns || []).map((column) => column.name || column);
  const issues = quality?.issues || [];

  if (loading) {
    return <LoadingState title="Загрузка наборов" description="Список файлов выбранной организации." />;
  }

  if (!organizations.length) {
    return (
      <div className="page">
        <h1>Наборы данных</h1>
        <Notice tone="warning" title="Нет организации">
          Администратор должен создать организацию и назначить вам доступ. Самостоятельное создание рабочего пространства не предусмотрено.
        </Notice>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Наборы данных</h1>
          <p className="page__lead">Загрузка и проверка таблицы. Анализ запускается после сохранения набора.</p>
        </div>
        <div className="page-actions">
          <button type="button" className="button button--ghost" onClick={onTemplate}>Скачать шаблон CSV</button>
          {canEdit ? (
            <button type="button" className="button" disabled={pending || !organizationId} onClick={onDemo}>
              Загрузить демонстрационные данные
            </button>
          ) : null}
        </div>
      </div>
      {demoInfo ? (
        <Notice tone="info" title="Демонстрационные данные">
          {demoInfo.note} Показатели: {(demoInfo.indicators || []).join(', ')}. Периодов: {demoInfo.periods}.
        </Notice>
      ) : null}

      {selectedOrganization ? (
        <p className="workspace-meta">
          <span>Организация: {selectedOrganization.name}</span>
          <span>Доступ: {canEdit ? 'редактирование' : 'просмотр'}</span>
        </p>
      ) : null}

      {error ? <ErrorMessage message={error} /> : null}
      {status ? <Notice tone={quality && !quality.ready_for_analysis ? 'warning' : 'info'} title={status} /> : null}

      {!canEdit ? (
        <Notice tone="warning" title="Загрузка недоступна">
          У вас право только просматривать эту организацию. Попросите администратора выдать право «редактирование».
        </Notice>
      ) : (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Новый файл</h2></header>
          <div className="card__body">
            <Hint>
              CSV и XLSX до 10 МБ. Можно выбрать несколько файлов или книгу с несколькими листами:
              одинаковые периоды и показатели объединяются, разные показатели дополняют набор.
              Повторная загрузка с тем же именем дописывает недостающие точки к предыдущей версии.
            </Hint>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              hidden
              onChange={(event) => onFiles(event.target.files)}
            />
            <button
              type="button"
              className="dropzone"
              disabled={pending}
              onClick={() => fileInput.current?.click()}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                onFiles(event.dataTransfer.files);
              }}
            >
              {pending ? 'Обработка файла…' : 'Перетащите один или несколько CSV/XLSX или нажмите, чтобы выбрать.'}
            </button>
            {preview?.source_files?.length ? (
              <p className="muted">Файлы: {preview.source_files.join(', ')}</p>
            ) : null}
          </div>
        </section>
      )}

      {preview ? (
        <form className="card" onSubmit={onImport}>
          <header className="card__header"><h2 className="card__title">Просмотр и проверка</h2></header>
          <div className="card__body form-grid">
            <label className="field">
              <span className="field__label">Имя набора</span>
              <input className="input" value={datasetName} onChange={(event) => setDatasetName(event.target.value)} required />
            </label>
            <label className="field">
              <span className="field__label">Столбец периода</span>
              <select className="select" value={periodColumn} onChange={(event) => setPeriodColumn(event.target.value)} required>
                {previewColumns.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              <Hint>Ожидается начало периода: ГГГГ-ММ, ГГГГ-Qn или ГГГГ.</Hint>
            </label>
          </div>
          <div className="card__body workspace-meta">
            <span>Строк: {preview.rows ?? '—'}</span>
            <span>Столбцов: {previewColumns.length}</span>
            <span>Формат: {preview.format === 'long' ? 'длинный' : 'широкий'}</span>
            {quality?.period_from ? (
              <span>Период: {quality.period_from} — {quality.period_to}</span>
            ) : null}
          </div>
          <div className="card__body">
            <div className="field__label">Показатели, которые система узнала</div>
            <div className="checkbox-grid">
              {(preview.suggested_indicators || []).map((item) => (
                <label key={item.column} className="check">
                  <input
                    type="checkbox"
                    checked={indicatorColumns.includes(item.column)}
                    onChange={() => setIndicatorColumns((current) => (
                      current.includes(item.column)
                        ? current.filter((name) => name !== item.column)
                        : [...current, item.column]
                    ))}
                  />
                  <span title={item.name}>{item.name} ({item.column})</span>
                </label>
              ))}
            </div>
            {(preview.unmapped_numeric_columns || []).length ? (
              <Hint>
                Не распознаны и не будут сохранены: {(preview.unmapped_numeric_columns || []).join(', ')}.
                Используйте коды справочника (revenue, profit, cash и др.) или русские названия из шаблона.
              </Hint>
            ) : null}
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>{previewColumns.map((name) => <th key={name}>{name}</th>)}</tr>
              </thead>
              <tbody>
                {(preview.preview || []).map((row, index) => (
                  <tr key={index}>
                    {previewColumns.map((name) => <td key={name}>{row[name]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {quality ? (
            <div className="card__body">
              <p>
                Готов к сохранению: {quality.ready_for_analysis ? 'да' : 'нет'}.
                Значений: {quality.values_count}, пропусков: {quality.missing_count},
                периодов: {quality.distinct_periods}.
              </p>
              {quality.time_analysis?.reason ? <p className="muted">{quality.time_analysis.reason}</p> : null}
              {issues.length ? (
                <ul className="issue-list">
                  {issues.slice(0, 20).map((item, index) => (
                    <li key={`${item.code}-${index}`}>
                      {item.severity === 'error' ? 'Ошибка' : 'Предупреждение'}: {item.message}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          <div className="card__body page-actions">
            <button type="button" className="button button--ghost" onClick={onValidate} disabled={pending}>
              Проверить ещё раз
            </button>
            <button type="submit" className="button" disabled={pending || !organizationId || quality?.ready_for_analysis === false}>
              {pending ? 'Сохранение…' : 'Сохранить набор'}
            </button>
          </div>
        </form>
      ) : null}

      <section className="card">
        <header className="card__header"><h2 className="card__title">Сохранённые наборы</h2></header>
        <DataTable
          sortable
          filterable
          columns={[
            { key: 'name', title: 'Набор', render: (row) => <Link to={`/data/${row.id}`}>{row.name}</Link> },
            { key: 'version_no', title: 'Версия', render: (row) => row.version_no || 1 },
            { key: 'source_filename', title: 'Файл' },
            { key: 'granularity', title: 'Периодичность' },
            { key: 'created_at', title: 'Загружен', render: (row) => formatDateTime(row.created_at) },
          ]}
          rows={visibleDatasets}
          emptyTitle="Наборы не загружены"
          emptyDescription="После сохранения файла список появится здесь."
        />
      </section>
    </div>
  );
}

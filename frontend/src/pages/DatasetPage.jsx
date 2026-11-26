import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { deleteDataset, fetchDataset, fetchDatasetQuality, fetchDatasetValues } from '../api/datasetsApi.js';
import { errorMessage } from '../api/httpClient.js';
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx';
import DataTable from '../components/ui/DataTable.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import Notice from '../components/ui/Notice.jsx';
import { formatNumber } from '../lib/format.js';
import './pages.css';

export default function DatasetPage() {
  const { datasetId } = useParams();
  const location = useLocation();
  const { canEdit, selectedOrganization } = useOutletContext() ?? {};
  const navigate = useNavigate();
  const [dataset, setDataset] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [quality, setQuality] = useState(null);
  const [values, setValues] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetchDataset(datasetId),
      fetchDatasetQuality(datasetId).catch(() => null),
      fetchDatasetValues(datasetId),
    ]).then(([item, report, page]) => {
      if (!active) {
        return;
      }
      setDataset(item);
      setQuality(report);
      setValues(page.items || []);
    }).catch((err) => {
      if (active) {
        setError(errorMessage(err));
      }
    });
    return () => {
      active = false;
    };
  }, [datasetId]);

  if (error) {
    return (
      <div className="page">
        <ErrorMessage message={error} />
        <Link to="/data" className="button button--ghost">К списку наборов</Link>
      </div>
    );
  }
  if (!dataset) {
    return <LoadingState title="Загрузка набора" />;
  }

  const analysisHref = `/analysis?datasetId=${dataset.id}`;

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>{dataset.name}</h1>
          <p className="page__lead">
            {selectedOrganization?.name ? `${selectedOrganization.name}. ` : ''}
            {dataset.source_filename || 'Без имени файла'}. Периодов: {dataset.periods_count}.
            {quality?.time_analysis?.possible === false ? ` ${quality.time_analysis.reason}` : ''}
          </p>
        </div>
        <div className="page-actions">
          <Link to="/data" className="button button--ghost">К списку</Link>
          {canEdit ? (
            <>
              <Link to={analysisHref} className="button">Запустить исследование</Link>
              <button type="button" className="button button--danger" onClick={() => setConfirmDelete(true)}>
                Удалить набор
              </button>
            </>
          ) : (
            <span className="muted">Запуск недоступен: нужен доступ «редактирование».</span>
          )}
        </div>
      </div>

      {location.state?.justSaved ? (
        <Notice tone="success" title="Набор сохранён">
          Проверьте показатели и периоды. Если всё верно, запустите исследование — набор уже будет выбран.
        </Notice>
      ) : null}

      {selectedOrganization && !canEdit ? (
        <Notice tone="warning" title="Только просмотр">
          Вы можете читать значения, но не запускать расчёт.
        </Notice>
      ) : null}

      <section className="card">
        <header className="card__header"><h2 className="card__title">Показатели</h2></header>
        <DataTable
          sortable
          filterable
          columns={[
            { key: 'name', title: 'Показатель' },
            { key: 'code', title: 'Код' },
            { key: 'unit', title: 'Ед.' },
            { key: 'values_count', title: 'Значений' },
            { key: 'missing_count', title: 'Пропусков' },
          ]}
          rows={dataset.indicators || []}
          rowKey="code"
        />
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Значения</h2></header>
        <DataTable
          sortable
          filterable
          columns={[
            { key: 'indicator_code', title: 'Показатель' },
            { key: 'period_start', title: 'Период' },
            { key: 'value', title: 'Значение', render: (row) => formatNumber(row.value), sortValue: (row) => Number(row.value) },
          ]}
          rows={values}
          emptyTitle="Нет значений"
        />
      </section>
      <ConfirmDialog
        open={confirmDelete}
        danger
        title="Удалить набор данных?"
        message="Будут удалены этот набор, все его исследования и отчёты. Операция затрагивает только выбранную организацию. После удаления можно загрузить файл заново."
        confirmLabel="Удалить набор"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          try {
            await deleteDataset(dataset.id);
            navigate('/data');
          } catch (err) {
            setError(errorMessage(err));
            setConfirmDelete(false);
          }
        }}
      />
    </div>
  );
}

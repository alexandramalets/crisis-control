import { useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchOrgAudit, fetchProfile, importProfileFile, upsertTarget, upsertThreshold } from '../api/governanceApi.js';
import { errorMessage } from '../api/httpClient.js';
import DataTable from '../components/ui/DataTable.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import Hint from '../components/ui/Hint.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import Notice from '../components/ui/Notice.jsx';
import { auditActionLabel, formatDateTime, formatNumber } from '../lib/format.js';
import './pages.css';

export default function NormsPage() {
  const { organizationId, selectedOrganization, canEdit } = useOutletContext() ?? {};
  const [profile, setProfile] = useState({ targets: [], thresholds: [] });
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [target, setTarget] = useState({ indicator_code: 'revenue', kind: 'plan', value: '', source: '' });
  const [bound, setBound] = useState({ indicator_code: 'cash', lower_bound: '', upper_bound: '', source: '', methodology: '' });
  const [info, setInfo] = useState('');
  const fileInput = useRef(null);

  function reload({ silent = false } = {}) {
    if (!organizationId) {
      setLoading(false);
      return Promise.resolve();
    }
    if (!silent) {
      setLoading(true);
    }
    return Promise.all([
      fetchProfile(organizationId),
      fetchOrgAudit(organizationId),
    ])
      .then(([nextProfile, nextAudit]) => {
        setProfile(nextProfile);
        setAudit(nextAudit);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    setError(null);
    reload();
  }, [organizationId]);

  async function onTarget(event) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await upsertTarget(organizationId, { ...target, value: Number(target.value) });
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onImportFile(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }
    if (!organizationId) {
      setError('Выберите организацию в шапке, затем загрузите файл.');
      return;
    }
    setPending(true);
    setError(null);
    setInfo('');
    try {
      const result = await importProfileFile(organizationId, file);
      const skipped = result.skipped?.length ? `. Не распознаны: ${result.skipped.join(', ')}` : '';
      setInfo(`Из файла «${file.name}» сохранено записей: ${result.imported}${skipped}`);
      await reload({ silent: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function onBound(event) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await upsertThreshold(organizationId, {
        indicator_code: bound.indicator_code,
        lower_bound: bound.lower_bound === '' ? null : Number(bound.lower_bound),
        upper_bound: bound.upper_bound === '' ? null : Number(bound.upper_bound),
        source: bound.source || null,
        methodology: bound.methodology || null,
      });
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
    return <div className="page"><LoadingState title="Загрузка профиля" /></div>;
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Нормативы и планы</h1>
          <p className="page__lead">
            {selectedOrganization?.name}. План — целевое значение, граница — допустимый интервал.
            Можно задать вручную или загрузить CSV/XLSX.
          </p>
        </div>
      </div>
      {error ? <ErrorMessage message={error} /> : null}
      {info ? <Notice tone="info" title="Файл обработан">{info}</Notice> : null}
      {canEdit ? (
        <>
          <section className="card">
            <header className="card__header"><h2 className="card__title">Загрузка из файла</h2></header>
            <div className="card__body">
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                hidden
                onChange={onImportFile}
              />
              <div className="page-actions">
                <button
                  type="button"
                  className="button"
                  disabled={pending}
                  onClick={() => fileInput.current?.click()}
                >
                  {pending ? 'Загрузка…' : 'Выбрать CSV или XLSX'}
                </button>
              </div>
              <Hint>
                Нужны листы «Планы» и «Границы» (столбцы indicator_code, Тип, Значение либо Нижняя / Верхняя).
                Пример — demo_data/promtech_service_norms.xlsx. Коэффициенты вроде current_ratio, которых нет
                в справочнике исходных показателей, пропускаются.
              </Hint>
            </div>
          </section>
          <form className="card" onSubmit={onTarget}>
            <header className="card__header"><h2 className="card__title">План или норматив</h2></header>
            <div className="card__body form-grid">
              <label className="field">
                <span className="field__label">Код показателя</span>
                <input className="input" required value={target.indicator_code} onChange={(e) => setTarget({ ...target, indicator_code: e.target.value })} />
              </label>
              <label className="field">
                <span className="field__label">Тип</span>
                <select className="select" value={target.kind} onChange={(e) => setTarget({ ...target, kind: e.target.value })}>
                  <option value="plan">План</option>
                  <option value="norm">Норматив</option>
                  <option value="target">Цель</option>
                </select>
              </label>
              <label className="field">
                <span className="field__label">Значение</span>
                <input className="input" type="number" step="any" required value={target.value} onChange={(e) => setTarget({ ...target, value: e.target.value })} />
              </label>
              <label className="field">
                <span className="field__label">Источник</span>
                <input className="input" value={target.source} onChange={(e) => setTarget({ ...target, source: e.target.value })} />
              </label>
            </div>
            <div className="card__body page-actions">
              <button className="button" type="submit" disabled={pending}>Сохранить</button>
            </div>
          </form>
          <form className="card" onSubmit={onBound}>
            <header className="card__header"><h2 className="card__title">Границы</h2></header>
            <div className="card__body form-grid">
              <label className="field">
                <span className="field__label">Код показателя</span>
                <input className="input" required value={bound.indicator_code} onChange={(e) => setBound({ ...bound, indicator_code: e.target.value })} />
              </label>
              <label className="field">
                <span className="field__label">Нижняя</span>
                <input className="input" type="number" step="any" value={bound.lower_bound} onChange={(e) => setBound({ ...bound, lower_bound: e.target.value })} />
              </label>
              <label className="field">
                <span className="field__label">Верхняя</span>
                <input className="input" type="number" step="any" value={bound.upper_bound} onChange={(e) => setBound({ ...bound, upper_bound: e.target.value })} />
              </label>
              <label className="field">
                <span className="field__label">Источник и методика</span>
                <input className="input" value={bound.methodology} onChange={(e) => setBound({ ...bound, methodology: e.target.value, source: e.target.value })} />
              </label>
            </div>
            <div className="card__body page-actions">
              <button className="button" type="submit" disabled={pending}>Сохранить границы</button>
            </div>
          </form>
        </>
      ) : null}
      <section className="card">
        <header className="card__header"><h2 className="card__title">Заданные значения</h2></header>
        <DataTable
          columns={[
            { key: 'indicator_code', title: 'Показатель' },
            { key: 'kind', title: 'Тип' },
            { key: 'value', title: 'Значение', render: (row) => formatNumber(row.value) },
            { key: 'source', title: 'Источник' },
          ]}
          rows={profile.targets || []}
          emptyTitle="Планы и нормативы не заданы"
        />
      </section>
      <section className="card">
        <header className="card__header"><h2 className="card__title">Границы</h2></header>
        <DataTable
          columns={[
            { key: 'indicator_code', title: 'Показатель' },
            { key: 'lower_bound', title: 'Нижняя', render: (row) => formatNumber(row.lower_bound) },
            { key: 'upper_bound', title: 'Верхняя', render: (row) => formatNumber(row.upper_bound) },
            { key: 'source', title: 'Источник' },
          ]}
          rows={profile.thresholds || []}
          emptyTitle="Границы не заданы"
        />
      </section>
      <section className="card">
        <header className="card__header"><h2 className="card__title">Журнал действий организации</h2></header>
        <DataTable
          columns={[
            { key: 'created_at', title: 'Время', render: (row) => formatDateTime(row.created_at) },
            { key: 'action', title: 'Действие', render: (row) => auditActionLabel(row.action) },
            { key: 'object_type', title: 'Объект' },
            { key: 'object_id', title: 'Идентификатор' },
          ]}
          rows={audit}
          emptyTitle="Записей нет"
        />
      </section>
    </div>
  );
}

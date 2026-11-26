import { Link, useOutletContext } from 'react-router-dom';
import { accessLevelLabel, formatDateTime } from '../lib/format.js';
import DataTable from '../components/ui/DataTable.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Notice from '../components/ui/Notice.jsx';
import './pages.css';

export default function OrganizationsPage() {
  const { organizations = [], selectedOrganization, setOrganizationId } = useOutletContext() ?? {};

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1>Организации</h1>
          <p className="page__lead">Организации, к которым у вас есть доступ.</p>
        </div>
      </div>

      {!organizations.length ? (
        <EmptyState
          title="Нет доступных организаций"
          description="Попросите администратора создать организацию и назначить вам доступ с нужным уровнем прав."
        />
      ) : (
        <section className="card">
          <header className="card__header"><h2 className="card__title">Доступные организации</h2></header>
          <DataTable
            columns={[
              { key: 'name', title: 'Название' },
              {
                key: 'access_level',
                title: 'Ваш доступ',
                render: (row) => accessLevelLabel(row.can_edit ? 'edit' : row.access_level),
              },
              { key: 'created_at', title: 'Создана', render: (row) => formatDateTime(row.created_at) },
              { key: 'datasets_count', title: 'Наборы' },
              { key: 'analyses_count', title: 'Исследования' },
              {
                key: 'open',
                title: '',
                render: (row) => (
                  <span className="table-actions">
                    <Link className="button button--ghost button--compact" to={`/organizations/${row.id}`}>Карточка</Link>
                    <button
                      type="button"
                      className="button button--ghost button--compact"
                      onClick={() => setOrganizationId?.(String(row.id))}
                    >
                      {String(selectedOrganization?.id) === String(row.id) ? 'Выбрана' : 'Выбрать'}
                    </button>
                  </span>
                ),
              },
            ]}
            rows={organizations}
            emptyTitle="Список пуст"
          />
        </section>
      )}

      {selectedOrganization && !selectedOrganization.can_edit ? (
        <Notice tone="warning" title="Сейчас выбран режим просмотра">
          Загрузка файлов и запуск анализа недоступны. Администратор может выдать право «редактирование».
        </Notice>
      ) : null}

      {selectedOrganization?.can_edit ? (
        <div className="page-actions">
          <Link className="button" to="/data">Перейти к наборам данных</Link>
        </div>
      ) : null}
    </div>
  );
}

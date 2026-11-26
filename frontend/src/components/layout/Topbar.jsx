import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext.jsx';
import { IconBuilding, IconMenu, IconUser } from '../../icons/Icons.jsx';

const PERIODS = [
  { value: '3', label: '3 мес' },
  { value: '6', label: '6 мес' },
  { value: '12', label: '12 мес' },
];

const ROLE_LABEL = { admin: 'Администратор', analyst: 'Аналитик' };

export default function Topbar({
  period,
  onPeriodChange,
  organizations = [],
  organizationId = '',
  onOrganizationChange,
  onMenuToggle,
  showPeriod = false,
  showOrganization = false,
}) {
  const { user, logout } = useAuth();
  const home = user?.role === 'admin' ? '/admin' : '/';

  return (
    <header className="topbar">
      <div className="topbar__left">
        <button type="button" className="button button--icon topbar__menu" onClick={onMenuToggle} aria-label="Открыть меню">
          <IconMenu />
        </button>
        <Link to={home} className="topbar__brand">
          <span className="topbar__mark" aria-hidden="true">CC</span>
          <div>
            <div className="topbar__title">Crisis Control</div>
            <div className="topbar__subtitle">Антикризисная аналитика</div>
          </div>
        </Link>
      </div>
      <div className="topbar__right">
        {showPeriod ? (
          <div className="topbar__field">
            <span className="topbar__field-label">Окно панели</span>
            <div className="segmented" role="group" aria-label="Период отображения панели">
              {PERIODS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={`segmented__item${period === item.value ? ' segmented__item--active' : ''}`}
                  aria-pressed={period === item.value}
                  onClick={() => onPeriodChange(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {showOrganization && organizations.length ? (
          <label className="topbar__control">
            <IconBuilding />
            <span className="sr-only">Организация</span>
            <select
              value={organizationId}
              onChange={(event) => onOrganizationChange(event.target.value)}
              aria-label="Организация"
            >
              {organizations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}{item.can_edit ? '' : ' (просмотр)'}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {user ? (
          <div className="topbar__user" title={user.username}>
            <IconUser />
            <span className="truncate">{user.full_name || user.username}</span>
            <span className="role-badge">{ROLE_LABEL[user.role] || user.role}</span>
            <button type="button" className="button button--ghost" onClick={logout}>Выйти</button>
          </div>
        ) : (
          <Link to="/login" className="topbar__control">
            <IconUser />
            <span>Войти</span>
          </Link>
        )}
      </div>
    </header>
  );
}

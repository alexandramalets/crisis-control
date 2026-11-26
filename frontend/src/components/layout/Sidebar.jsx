import { NavLink } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext.jsx';
import {
  IconAnalysis, IconBuilding, IconData, IconHelp, IconHome, IconReports, IconSettings, IconStatus, IconUser,
} from '../../icons/Icons.jsx';

const ANALYST_MAIN = [
  { to: '/', label: 'Рабочая панель', icon: IconHome, end: true },
  { to: '/organizations', label: 'Организации', icon: IconBuilding },
  { to: '/data', label: 'Наборы данных', icon: IconData },
  { to: '/analysis', label: 'Анализ', icon: IconAnalysis },
  { to: '/recommendations', label: 'Рекомендации', icon: IconReports },
  { to: '/measures', label: 'Мероприятия', icon: IconStatus },
  { to: '/scenarios', label: 'Сценарии', icon: IconAnalysis },
  { to: '/norms', label: 'Нормативы', icon: IconSettings },
  { to: '/reports', label: 'История исследований', icon: IconReports },
];

const ADMIN_MAIN = [
  { to: '/admin', label: 'Обзор системы', icon: IconHome, end: true },
  { to: '/admin/users', label: 'Пользователи', icon: IconUser },
  { to: '/admin/organizations', label: 'Организации', icon: IconBuilding },
];

const SECONDARY = [
  { to: '/settings', label: 'Настройки', icon: IconSettings },
  { to: '/help', label: 'Справка', icon: IconHelp },
  { to: '/privacy', label: 'Конфиденциальность', icon: IconHelp },
];

function MenuItem({ to, label, icon: Icon, onNavigate, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => `sidebar__item${isActive ? ' sidebar__item--active' : ''}`}
      onClick={onNavigate}
    >
      <Icon />
      {label}
    </NavLink>
  );
}

export default function Sidebar({ open, onNavigate }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const main = isAdmin ? ADMIN_MAIN : ANALYST_MAIN;
  return (
    <nav className={`sidebar${open ? ' sidebar--open' : ''}`} aria-label="Основное меню">
      <div>
        <div className="sidebar__group">
          <div className="sidebar__label">{isAdmin ? 'Управление' : 'Работа с данными'}</div>
          {main.map((item) => <MenuItem key={item.to} {...item} onNavigate={onNavigate} />)}
        </div>
        <div className="sidebar__group">
          <div className="sidebar__label">Система</div>
          {SECONDARY.map((item) => <MenuItem key={item.to} {...item} onNavigate={onNavigate} />)}
        </div>
      </div>
      <div className="sidebar__version">v{__APP_VERSION__}</div>
    </nav>
  );
}

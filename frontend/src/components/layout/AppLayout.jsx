import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { fetchOrganizations } from '../../api/organizationsApi.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import Sidebar from './Sidebar.jsx';
import Topbar from './Topbar.jsx';
import './layout.css';

const ORG_STORAGE_KEY = 'ca_organization_id';

export default function AppLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [period, setPeriod] = useState('12');
  const [organizations, setOrganizations] = useState([]);
  const [organizationId, setOrganizationId] = useState(() => sessionStorage.getItem(ORG_STORAGE_KEY) || '');

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 960) {
        setMenuOpen(false);
      }
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    if (!user || user.role === 'admin') {
      setOrganizations([]);
      return undefined;
    }
    let cancelled = false;
    fetchOrganizations()
      .then((page) => {
        if (cancelled) {
          return;
        }
        const items = page.items || [];
        setOrganizations(items);
        setOrganizationId((current) => {
          if (current && items.some((item) => String(item.id) === String(current))) {
            return current;
          }
          const next = items[0] ? String(items[0].id) : '';
          if (next) {
            sessionStorage.setItem(ORG_STORAGE_KEY, next);
          } else {
            sessionStorage.removeItem(ORG_STORAGE_KEY);
          }
          return next;
        });
      })
      .catch(() => {
        if (!cancelled) {
          setOrganizations([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  function onOrganizationChange(value) {
    setOrganizationId(value);
    if (value) {
      sessionStorage.setItem(ORG_STORAGE_KEY, value);
    } else {
      sessionStorage.removeItem(ORG_STORAGE_KEY);
    }
  }

  const selectedOrganization = organizations.find((item) => String(item.id) === String(organizationId)) || null;
  const showPeriod = location.pathname === '/' || location.pathname === '/workspace';

  return (
    <div className="app">
      <Topbar
        period={period}
        onPeriodChange={setPeriod}
        organizations={organizations}
        organizationId={organizationId}
        onOrganizationChange={onOrganizationChange}
        onMenuToggle={() => setMenuOpen((open) => !open)}
        showPeriod={Boolean(user) && user.role !== 'admin' && showPeriod}
        showOrganization={Boolean(user) && user.role !== 'admin'}
      />
      <div className="app__body">
        {menuOpen ? (
          <button
            type="button"
            className="sidebar-backdrop"
            aria-label="Закрыть меню"
            onClick={() => setMenuOpen(false)}
          />
        ) : null}
        <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
        <main className="app__content">
          <Outlet context={{
            period,
            organizationId: organizationId ? Number(organizationId) : undefined,
            organizations,
            selectedOrganization,
            canEdit: Boolean(selectedOrganization?.can_edit),
            setOrganizationId: onOrganizationChange,
          }}
          />
        </main>
      </div>
    </div>
  );
}

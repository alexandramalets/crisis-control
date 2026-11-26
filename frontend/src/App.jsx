import { Route, Routes } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth.jsx';
import RequireRole from './auth/RequireRole.jsx';
import AppLayout from './components/layout/AppLayout.jsx';
import AdminOrganizationsPage from './pages/admin/AdminOrganizationsPage.jsx';
import AdminOverviewPage from './pages/admin/AdminOverviewPage.jsx';
import AdminUsersPage from './pages/admin/AdminUsersPage.jsx';
import AnalysisPage from './pages/AnalysisPage.jsx';
import DataPage from './pages/DataPage.jsx';
import DatasetPage from './pages/DatasetPage.jsx';
import HelpPage from './pages/HelpPage.jsx';
import HomePage from './pages/HomePage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import MeasuresPage from './pages/MeasuresPage.jsx';
import NormsPage from './pages/NormsPage.jsx';
import RecommendationsPage from './pages/RecommendationsPage.jsx';
import ScenariosPage from './pages/ScenariosPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';
import OrganizationPage from './pages/OrganizationPage.jsx';
import OrganizationsPage from './pages/OrganizationsPage.jsx';
import PrivacyPage from './pages/PrivacyPage.jsx';
import ReportsPage from './pages/ReportsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route element={<RequireAuth />}>
          <Route path="settings" element={<SettingsPage />} />
          <Route element={<RequireRole role="analyst" redirectTo="/admin" />}>
            <Route index element={<HomePage />} />
            <Route path="organizations" element={<OrganizationsPage />} />
            <Route path="organizations/:organizationId" element={<OrganizationPage />} />
            <Route path="data" element={<DataPage />} />
            <Route path="data/:datasetId" element={<DatasetPage />} />
            <Route path="analysis" element={<AnalysisPage />} />
            <Route path="analysis/:runId" element={<AnalysisPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="measures" element={<MeasuresPage />} />
            <Route path="scenarios" element={<ScenariosPage />} />
            <Route path="norms" element={<NormsPage />} />
          </Route>
          <Route element={<RequireRole role="admin" redirectTo="/" />}>
            <Route path="admin" element={<AdminOverviewPage />} />
            <Route path="admin/users" element={<AdminUsersPage />} />
            <Route path="admin/organizations" element={<AdminOrganizationsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

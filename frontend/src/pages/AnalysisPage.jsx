import { Link, useLocation, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { fetchAnalysisResults } from '../api/analysesApi.js';
import { errorMessage } from '../api/httpClient.js';
import ErrorBoundary from '../components/ui/ErrorBoundary.jsx';
import ErrorMessage from '../components/ui/ErrorMessage.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import LaunchForm from './analysis/LaunchForm.jsx';
import ResultsView from './analysis/ResultsView.jsx';
import './pages.css';

function seedFromLocation(location, runId) {
  const run = location.state?.run;
  if (!runId || !run || String(run.id) !== String(runId)) {
    return null;
  }
  return { run };
}

export default function AnalysisPage() {
  const { runId } = useParams();
  const location = useLocation();
  const [state, setState] = useState(() => {
    const seeded = seedFromLocation(location, runId);
    return { loading: Boolean(runId) && !seeded, error: null, data: seeded };
  });

  useEffect(() => {
    if (!runId) {
      setState({ loading: false, error: null, data: null });
      return undefined;
    }
    const seeded = seedFromLocation(location, runId);
    let active = true;
    setState((current) => ({
      loading: !(seeded || current.data?.run),
      error: null,
      data: seeded || current.data,
    }));
    fetchAnalysisResults(runId)
      .then((data) => {
        if (active) {
          setState({ loading: false, error: null, data });
        }
      })
      .catch((error) => {
        if (active) {
          setState((current) => ({
            loading: false,
            error,
            data: current.data?.run ? current.data : null,
          }));
        }
      });
    return () => {
      active = false;
    };
  }, [runId, location.state]);

  if (!runId) {
    return (
      <div className="page">
        <div className="page__header">
          <div>
            <h1>Анализ</h1>
            <p className="page__lead">Выберите набор и период, затем запустите расчёт.</p>
          </div>
        </div>
        <LaunchForm />
      </div>
    );
  }

  if (state.loading && !state.data?.run) {
    return (
      <div className="page">
        <div className="page__header">
          <div>
            <h1>Исследование №{runId}</h1>
            <p className="page__lead">Загружаем сохранённые результаты. Расчёт повторно не запускается.</p>
          </div>
          <div className="page-actions">
            <Link to="/analysis" className="button button--ghost">К запуску</Link>
            <Link to="/reports" className="button button--ghost">К истории</Link>
          </div>
        </div>
        <LoadingState title="Загрузка результатов" description={`Открываем исследование №${runId}.`} />
      </div>
    );
  }

  if (state.error && !state.data?.run) {
    return (
      <div className="page">
        <div className="page__header">
          <div>
            <h1>Исследование №{runId}</h1>
            <p className="page__lead">Результаты не удалось открыть.</p>
          </div>
        </div>
        <ErrorMessage message={errorMessage(state.error)} />
        <div className="page-actions">
          <Link to="/analysis" className="button button--ghost">К запуску</Link>
          <Link to="/reports" className="button button--ghost">К истории</Link>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary
      key={runId}
      fallback={(
        <div className="page">
          <div className="page__header">
            <div>
              <h1>Исследование №{runId}</h1>
              <p className="page__lead">Не удалось показать экран результатов. Исследование сохранено в истории.</p>
            </div>
            <div className="page-actions">
              <Link to="/analysis" className="button button--ghost">К запуску</Link>
              <Link to="/reports" className="button">К истории</Link>
            </div>
          </div>
        </div>
      )}
    >
      <ResultsView data={state.data} />
    </ErrorBoundary>
  );
}

import EmptyState from './EmptyState.jsx';
import './ui.css';

export default function ChartPanel({ title, actions, children, emptyTitle, emptyDescription }) {
  return (
    <section className="card">
      <header className="card__header">
        <h2 className="card__title">{title}</h2>
        {actions ? <div className="card__actions">{actions}</div> : null}
      </header>
      <div className="card__body chart-panel__canvas">
        {children || (
          <EmptyState
            title={emptyTitle || 'Нет данных для отображения'}
            description={emptyDescription}
          />
        )}
      </div>
    </section>
  );
}

import { IconArrowDown, IconArrowUp } from '../../icons/Icons.jsx';
import './ui.css';

export default function MetricCard({ title, value, change, direction, favorable, icon, accent = false, children }) {
  const hasValue = value !== null && value !== undefined && value !== '';
  const trendClass = favorable === false
    ? 'metric-card__meta--down'
    : favorable === true
      ? 'metric-card__meta--up'
      : direction === 'down'
        ? 'metric-card__meta--down'
        : direction === 'up'
          ? 'metric-card__meta--up'
          : '';

  return (
    <article className={`card metric-card${accent ? ' metric-card--accent' : ''}`}>
      <div className="metric-card__head">
        <div className="metric-card__label truncate" title={title}>{title}</div>
        {icon ? <div className="metric-card__icon">{icon}</div> : null}
      </div>
      {hasValue ? (
        <>
          <div className="metric-card__value">{value}</div>
          {change && (
            <div className={`metric-card__meta ${trendClass}`}>
              {direction === 'down' ? <IconArrowDown /> : direction === 'up' ? <IconArrowUp /> : null}
              <span>{change}</span>
            </div>
          )}
        </>
      ) : (
        <div className="metric-card__empty">Нет данных</div>
      )}
      {children ? <div className="metric-card__spark">{children}</div> : null}
    </article>
  );
}

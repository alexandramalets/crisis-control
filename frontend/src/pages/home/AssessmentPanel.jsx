import EmptyState from '../../components/ui/EmptyState.jsx';
import { formatNumber, interpretScore, scoreTone } from '../../lib/format.js';

const RADIUS = 42;
const CIRC = 2 * Math.PI * RADIUS;

function zoneTone(score) {
  return scoreTone(score);
}

function Donut({ score }) {
  const value = Math.max(0, Math.min(100, score));
  const dash = (value / 100) * CIRC;
  return (
    <div className="donut" aria-label={`Сводная оценка ${formatNumber(value, 0)} из 100`}>
      <svg className="donut__svg" viewBox="0 0 120 120" aria-hidden="true">
        <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="#e8eee9" strokeWidth="12" />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          stroke={zoneTone(value)}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${CIRC - dash}`}
          transform="rotate(-90 60 60)"
        />
      </svg>
      <div className="donut__readout">
        <span className="donut__value" style={{ color: zoneTone(value) }}>{formatNumber(value, 0)}</span>
        <span className="donut__unit">из 100</span>
      </div>
    </div>
  );
}

export default function AssessmentPanel({ assessment, compact = false }) {
  if (!assessment) {
    return (
      <EmptyState
        title="Оценка не рассчитана"
        description="Запустите исследование, чтобы получить оценку 0–100."
      />
    );
  }
  if (assessment.warning && assessment.score == null) {
    return (
      <EmptyState
        title="Недостаточно данных"
        description={assessment.warning}
      />
    );
  }
  const score = Number(assessment.score);
  return (
    <div className={`score-panel${compact ? ' score-panel--compact' : ''}`}>
      {Number.isFinite(score) ? <Donut score={score} /> : null}
      <p className="score-panel__text">{assessment.interpretation || interpretScore(score)}</p>
      {assessment.history_score != null || assessment.compliance_score != null ? (
        <p className="muted">
          История: {assessment.history_score == null ? '—' : formatNumber(assessment.history_score, 0)}
          {' · '}
          Нормативы: {assessment.compliance_score == null ? 'не заданы' : formatNumber(assessment.compliance_score, 0)}
          {assessment.completeness != null ? ` · полнота ${formatNumber(Number(assessment.completeness) * 100, 0)} %` : ''}
        </p>
      ) : null}
      {assessment.methodology ? <p className="muted">{assessment.methodology}</p> : null}
      {assessment.warning ? <p className="muted">{assessment.warning}</p> : null}
      {!compact && (assessment.factors || []).length && !assessment.groups?.length ? (
        <ul className="score-groups">
          {assessment.factors.map((factor) => {
            const width = Math.max(0, Math.min(100, Number(factor.normalized_score) * 100 || 0));
            return (
              <li key={factor.code}>
                <div className="score-groups__meta">
                  <span className="truncate" title={factor.explanation || factor.name}>{factor.name}</span>
                  <span>{formatNumber(width, 0)}</span>
                </div>
                <div className="factor-bar">
                  <i style={{ width: `${width}%`, background: zoneTone(width) }} />
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
      {assessment.groups?.length ? (
        <ul className="score-groups">
          {assessment.groups.map((group) => {
            const width = Math.max(0, Math.min(100, Number(group.score) || 0));
            return (
              <li key={group.code}>
                <div className="score-groups__meta">
                  <span className="truncate" title={group.name}>{group.name}</span>
                  <span>{formatNumber(group.score, 0)}</span>
                </div>
                <div className="factor-bar">
                  <i style={{ width: `${width}%`, background: zoneTone(width) }} />
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

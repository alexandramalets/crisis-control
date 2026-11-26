export default function NarrativeBlock({ narrative, extra = null, hideDetails = false }) {
  if (!narrative) {
    return null;
  }
  return (
    <div className="narrative">
      <p className="narrative__brief">{narrative.brief}</p>
      {!hideDetails && (narrative.details || []).length ? (
        <details className="details-block">
          <summary>Подробнее</summary>
          <ul className="issue-list">
            {narrative.details.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </details>
      ) : null}
      {(narrative.technical || []).length ? (
        <details className="details-block">
          <summary>Параметры расчёта</summary>
          <ul className="issue-list">
            {narrative.technical.filter(Boolean).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </details>
      ) : null}
      {extra}
    </div>
  );
}

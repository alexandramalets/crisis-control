function toneForScore(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) {
    return 'caution';
  }
  if (value < 0.4) {
    return 'alert';
  }
  if (value < 0.7) {
    return 'caution';
  }
  return 'ok';
}

export default function RiskFactors({ factors }) {
  if (!factors?.length) {
    return null;
  }
  return (
    <section className="card risk-board">
      <header className="card__header">
        <h2 className="card__title">Показатели с низким баллом</h2>
      </header>
      <div className="risk-board__grid">
        {factors.map((factor) => {
          const tone = toneForScore(factor.normalized_score);
          return (
            <article key={factor.code} className={`risk-chip risk-chip--${tone}`}>
              <span className="risk-chip__mark" aria-hidden="true" />
              <div>
                <h3 className="risk-chip__title" title={factor.name}>{factor.name}</h3>
                <p className="risk-chip__text">
                  {factor.explanation || 'Фактор получен из сохранённой сводной оценки исследования.'}
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

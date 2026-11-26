function cellStyle(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return { background: '#f4f6f8', color: '#8b97a3' };
  }
  const t = Math.max(-1, Math.min(1, value));
  if (t >= 0) {
    const mix = 0.14 + t * 0.8;
    return {
      background: `rgba(31, 143, 85, ${mix})`,
      color: t > 0.62 ? '#ffffff' : '#143028',
    };
  }
  const mix = 0.14 + Math.abs(t) * 0.72;
  return {
    background: `rgba(212, 84, 70, ${mix})`,
    color: Math.abs(t) > 0.62 ? '#ffffff' : '#3d1c18',
  };
}

function matrixFromPairs(correlations) {
  const codes = correlations?.indicators || [];
  const lookup = new Map();
  for (const pair of correlations?.pairs || []) {
    lookup.set(`${pair.indicator_a}|${pair.indicator_b}`, pair.coefficient);
    lookup.set(`${pair.indicator_b}|${pair.indicator_a}`, pair.coefficient);
  }
  return codes.map((row) => codes.map((column) => {
    if (row === column) {
      return 1;
    }
    const value = lookup.get(`${row}|${column}`);
    return value === undefined ? null : value;
  }));
}

export function heatmapFromPairs(pairs, names = {}, interpretation = '') {
  const codes = [];
  const list = Array.isArray(pairs) ? pairs : [];
  for (const pair of list) {
    for (const code of [pair.indicator_a, pair.indicator_b]) {
      if (!codes.includes(code)) {
        codes.push(code);
      }
    }
  }
  return { indicators: codes, names, pairs: list, interpretation };
}

export default function CorrelationHeatmap({ correlations }) {
  const codes = correlations?.indicators || [];
  const names = correlations?.names || {};
  const matrix = matrixFromPairs(correlations);
  if (!codes.length) {
    return null;
  }
  return (
    <div className="heatmap-wrap">
      <table className="heatmap">
        <thead>
          <tr>
            <th />
            {codes.map((code) => (
              <th key={code} title={names[code] || code}>
                <span>{names[code] || code}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {codes.map((rowCode, rowIndex) => (
            <tr key={rowCode}>
              <th title={names[rowCode] || rowCode}>{names[rowCode] || rowCode}</th>
              {matrix[rowIndex].map((value, columnIndex) => (
                <td
                  key={`${rowCode}-${codes[columnIndex]}`}
                  style={cellStyle(value)}
                  title={`${names[rowCode] || rowCode} × ${names[codes[columnIndex]] || codes[columnIndex]}: ${value == null || Number.isNaN(Number(value)) ? 'нет данных' : Number(value).toFixed(2)}`}
                >
                  {value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted heatmap-note">{correlations.interpretation}</p>
    </div>
  );
}

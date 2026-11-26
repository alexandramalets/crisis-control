import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { formatNumber } from '../../lib/format.js';

const AXIS = { fill: '#7b8794', fontSize: 11 };

function chartRows(series) {
  if (!series) {
    return [];
  }
  const rows = (series.history || []).map((point) => ({
    label: point.label,
    history: point.value,
    forecast: null,
    lower: null,
    upper: null,
  }));
  const lastHistory = [...(series.history || [])].reverse().find((point) => point.value != null);
  const forecast = series.forecast || [];
  if (lastHistory && forecast.length) {
    const lastRow = [...rows].reverse().find((row) => row.history != null);
    if (lastRow) {
      lastRow.forecast = lastHistory.value;
    }
  }
  for (const point of forecast) {
    rows.push({
      label: point.label,
      history: null,
      forecast: point.value,
      lower: point.lower,
      upper: point.upper,
    });
  }
  return rows;
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) {
    return null;
  }
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{label}</div>
      {payload.map((entry) => (
        entry.value == null || entry.dataKey === 'upper' || entry.dataKey === 'lower' ? null : (
          <div key={entry.dataKey}>
            {entry.name}: {formatNumber(entry.value)}
          </div>
        )
      ))}
      {payload[0]?.payload?.lower != null ? (
        <div>Интервал: {formatNumber(payload[0].payload.lower)} — {formatNumber(payload[0].payload.upper)}</div>
      ) : null}
    </div>
  );
}

export default function DynamicsChart({ series }) {
  const data = chartRows(series);
  if (!data.length) {
    return null;
  }
  const hasForecast = (series.forecast || []).length > 0;
  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#e6ebf0" strokeDasharray="3 4" vertical={false} />
          <XAxis
            dataKey="label"
            tick={AXIS}
            axisLine={false}
            tickLine={false}
            minTickGap={16}
          />
          <YAxis
            tick={AXIS}
            width={58}
            tickFormatter={(value) => formatNumber(value, Math.abs(value) >= 100 ? 0 : 1)}
            axisLine={false}
            tickLine={false}
            domain={[(min) => min - Math.abs(min) * 0.12, (max) => max + Math.abs(max) * 0.08]}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#5c6b7c', strokeWidth: 1 }} />
          <Legend wrapperStyle={{ fontSize: 11, color: '#5c6b7c', paddingTop: 4 }} />
          <Line
            type="monotone"
            dataKey="history"
            name="Факт"
            stroke="var(--color-positive)"
            strokeWidth={2.4}
            dot={false}
            activeDot={{ r: 4, fill: 'var(--color-positive)', stroke: '#fff', strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
          {hasForecast ? (
            <Line
              type="monotone"
              dataKey="forecast"
              name="Прогноз"
              stroke="var(--color-warning)"
              strokeDasharray="4 3"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: 'var(--color-warning)', stroke: '#fff', strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

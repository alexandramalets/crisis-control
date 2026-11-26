import { Area, AreaChart, ResponsiveContainer } from 'recharts';

export default function Sparkline({ points, tone = 'accent' }) {
  const data = (points || []).filter((point) => point.value !== null && point.value !== undefined);
  if (data.length < 3) {
    return null;
  }
  const stroke = tone === 'negative' ? 'var(--color-negative)' : 'var(--color-positive)';
  return (
    <ResponsiveContainer width="100%" height={28}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
        <Area
          type="monotone"
          dataKey="value"
          stroke={stroke}
          fill="transparent"
          strokeWidth={1.25}
          isAnimationActive={false}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

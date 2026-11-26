import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';

const COLORS = ['#12b56a', '#e06a12', '#1a4f8b', '#e23b32', '#6d5cae', '#5c6b7c'];

export default function ClusterScatter({ members, clusters }) {
  const groups = (clusters || []).map((cluster) => ({
    ...cluster,
    points: (members || []).filter((member) => member.cluster === cluster.cluster),
  }));
  if (!groups.some((group) => group.points.length)) {
    return null;
  }
  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
          <XAxis dataKey="pc1" name="PC1" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} type="number" />
          <YAxis dataKey="pc2" name="PC2" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} type="number" />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} isAnimationActive={false} />
          <Legend />
          {groups.map((group, index) => (
            <Scatter
              key={group.cluster}
              name={group.label || `Кластер ${group.cluster}`}
              data={group.points}
              fill={COLORS[index % COLORS.length]}
              isAnimationActive={false}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

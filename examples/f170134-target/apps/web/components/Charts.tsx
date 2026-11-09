import { formatNumber } from '../lib/format';

/** Oracle JET charts of page 100 as static SVG: pie (value_format decimal) and vertical bar. */
const COLORS = ['#309fdb', '#13b6cf', '#2ebfbc', '#3cb44b', '#9ec03e', '#ffb800', '#fc8e3b', '#ee4d6c', '#a76dc7'];

export interface Point { label: string; value: string }

export function PieChart({ data, title }: { data: Point[]; title: string }) {
  const total = data.reduce((s, d) => s + Number(d.value), 0);
  if (!total) return <div className="nodata">No data found.</div>;
  let angle = -Math.PI / 2;
  const r = 90;
  const slices = data.map((d, i) => {
    const frac = Number(d.value) / total;
    const start = angle;
    angle += frac * 2 * Math.PI;
    const large = frac > 0.5 ? 1 : 0;
    const [x1, y1, x2, y2] = [Math.cos(start) * r, Math.sin(start) * r, Math.cos(angle) * r, Math.sin(angle) * r];
    const path = frac >= 0.9999 ? `M ${-r} 0 A ${r} ${r} 0 1 1 ${r} 0 A ${r} ${r} 0 1 1 ${-r} 0` : `M 0 0 L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
    return <path key={d.label} d={path} fill={COLORS[i % COLORS.length]}><title>{`${d.label}: ${d.value}`}</title></path>;
  });
  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox="-100 -100 200 200" width="220" height="220" role="img" aria-label={title}>{slices}</svg>
      <figcaption className="legend">
        {data.map((d, i) => <span key={d.label} style={{ ['--c' as string]: COLORS[i % COLORS.length] }}>{d.label}: {d.value}</span>)}
      </figcaption>
    </figure>
  );
}

export function BarChart({ data, title }: { data: Point[]; title: string }) {
  if (!data.length) return <div className="nodata">No data found.</div>;
  const max = Math.max(...data.map((d) => Number(d.value)), 1);
  const w = 360; const h = 200; const bw = Math.min(60, (w - 20) / data.length - 10);
  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${w} ${h + 40}`} width="100%" style={{ maxWidth: 480 }} role="img" aria-label={title}>
        {data.map((d, i) => {
          const bh = (Number(d.value) / max) * h;
          const x = 10 + i * (bw + 10);
          return (
            <g key={d.label}>
              <rect x={x} y={h - bh} width={bw} height={bh} fill={COLORS[0]}><title>{`${d.label}: ${d.value}`}</title></rect>
              <text x={x + bw / 2} y={h + 14} fontSize="10" textAnchor="middle">{d.label}</text>
              <text x={x + bw / 2} y={h - bh - 4} fontSize="10" textAnchor="middle">{formatNumber(d.value, '999G999G999G999G990')}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

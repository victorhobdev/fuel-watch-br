import { useId, useMemo, useRef, useState, type MouseEvent } from 'react';
import {
  count,
  date,
  money,
  moneyCompact,
  signedPercent,
  unitLabel,
  type ChartWindow,
  type Observation,
} from './data';

type Props = {
  rows: Observation[];
  referenceRows?: Observation[];
  referenceLabel?: string;
  primaryLabel: string;
  unit: string;
  week: number;
  weeks: string[];
  windowMode: ChartWindow;
  onWindowChange: (mode: ChartWindow) => void;
  onSelectWeek: (weekIndex: number) => void;
};

type Point = { w: number; x: number; y: number; row: Observation };

function buildGapSafeLinePath(points: Point[]): string {
  return points
    .map((pt, i) => {
      const cmd = i === 0 || points[i].w !== points[i - 1].w + 1 ? 'M' : 'L';
      return `${cmd}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
    })
    .join(' ');
}

function buildContiguousAreaPaths(points: Point[], baselineY: number): string[] {
  const segments: Point[][] = [];
  for (const pt of points) {
    const current = segments[segments.length - 1];
    if (!current || pt.w !== current[current.length - 1].w + 1) {
      segments.push([pt]);
    } else {
      current.push(pt);
    }
  }
  return segments
    .filter(seg => seg.length >= 2)
    .map(seg => {
      const top = seg.map((pt, i) => `${i === 0 ? 'M' : 'L'}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');
      const last = seg[seg.length - 1];
      const first = seg[0];
      return `${top} L${last.x.toFixed(1)},${baselineY.toFixed(1)} L${first.x.toFixed(1)},${baselineY.toFixed(1)} Z`;
    });
}

export default function TrendChart({
  rows,
  referenceRows,
  referenceLabel,
  primaryLabel,
  unit,
  week,
  weeks,
  windowMode,
  onWindowChange,
  onSelectWeek,
}: Props) {
  const gradientId = useId();
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverWeek, setHoverWeek] = useState<number | null>(null);

  const [startW, endW] = useMemo<[number, number]>(() => {
    const maxIdx = Math.max(0, weeks.length - 1);
    if (windowMode === 'all' || maxIdx <= 25) return [0, maxIdx];
    if (week < 25) return [0, Math.min(maxIdx, 25)];
    return [week - 25, week];
  }, [week, weeks.length, windowMode]);

  const visiblePrimary = useMemo(
    () => rows.filter(r => r.w >= startW && r.w <= endW),
    [rows, startW, endW],
  );
  const visibleRef = useMemo(
    () => (referenceRows ? referenceRows.filter(r => r.w >= startW && r.w <= endW) : []),
    [referenceRows, startW, endW],
  );

  const width = 360;
  const height = 138;
  const padLeft = 52;
  const padRight = 10;
  const padTop = 12;
  const padBottom = 24;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;
  const baselineY = padTop + plotH;

  const { minVal, maxVal, primaryPoints, refPoints } = useMemo(() => {
    const allPrices = [...visiblePrimary.map(r => r.p), ...visibleRef.map(r => r.p)];
    if (!allPrices.length) {
      return { minVal: 0, maxVal: 1, primaryPoints: [] as Point[], refPoints: [] as Point[] };
    }
    const rawMin = Math.min(...allPrices);
    const rawMax = Math.max(...allPrices);
    const margin = Math.max((rawMax - rawMin) * 0.12, 0.04);
    const lo = Math.max(0, rawMin - margin);
    const hi = rawMax + margin;
    const wSpan = Math.max(1, endW - startW);

    const toPoints = (series: Observation[]): Point[] =>
      series.map(row => ({
        w: row.w,
        x: padLeft + ((row.w - startW) / wSpan) * plotW,
        y: padTop + (1 - (row.p - lo) / (hi - lo || 1)) * plotH,
        row,
      }));

    return {
      minVal: lo,
      maxVal: hi,
      primaryPoints: toPoints(visiblePrimary),
      refPoints: toPoints(visibleRef),
    };
  }, [visiblePrimary, visibleRef, startW, endW, plotW, plotH]);

  const activeW = hoverWeek !== null ? hoverWeek : week;
  const activePrimary = useMemo(
    () => visiblePrimary.find(r => r.w === activeW) || rows.find(r => r.w === activeW),
    [visiblePrimary, rows, activeW],
  );
  const activeRef = useMemo(
    () => (referenceRows ? referenceRows.find(r => r.w === activeW) : undefined),
    [referenceRows, activeW],
  );
  const activeX =
    activeW >= startW && activeW <= endW
      ? padLeft + ((activeW - startW) / Math.max(1, endW - startW)) * plotW
      : null;
  const activePoint = primaryPoints.find(pt => pt.w === activeW);

  const handlePointer = (event: MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const relX = ((event.clientX - rect.left) / rect.width) * width;
    const clamped = Math.max(padLeft, Math.min(padLeft + plotW, relX));
    const ratio = (clamped - padLeft) / plotW;
    const nearest = Math.round(startW + ratio * (endW - startW));
    setHoverWeek(Math.max(startW, Math.min(endW, nearest)));
  };

  const handleClick = () => {
    if (hoverWeek !== null) onSelectWeek(hoverWeek);
  };

  const midVal = (minVal + maxVal) / 2;
  const activeDelta =
    activePrimary && activeRef && activeRef.p > 0 && activePrimary.eligible !== false
      ? ((activePrimary.p / activeRef.p) - 1) * 100
      : undefined;

  return (
    <section className="chart-card" aria-label="Evolução semanal de preços">
      <div className="chart-header">
        <div>
          <span className="eyebrow">SÉRIE HISTÓRICA</span>
          <h3>Evolução semanal</h3>
        </div>
        <div className="segmented-mini" role="group" aria-label="Janela da série histórica">
          <button
            type="button"
            aria-pressed={windowMode === '26w'}
            onClick={() => onWindowChange('26w')}
          >
            26 sem.
          </button>
          <button
            type="button"
            aria-pressed={windowMode === 'all'}
            onClick={() => onWindowChange('all')}
          >
            2024–2026
          </button>
        </div>
      </div>

      <div className="chart-readout" aria-live="polite">
        <span className="chart-readout-date">
          {weeks[activeW] ? date(weeks[activeW]) : '—'}
          {hoverWeek !== null && hoverWeek !== week ? ' (clique p/ ir)' : ''}
        </span>
        <span className="chart-readout-values">
          {activePrimary ? (
            <>
              <strong>
                {money(activePrimary.p)}/{unitLabel(unit)}
              </strong>
              <small>{count(activePrimary.n)} {activePrimary.n === 1 ? 'posto' : 'postos'}</small>
              {activeDelta !== undefined && (
                <em className={activeDelta > 0 ? 'up' : activeDelta < 0 ? 'down' : ''}>
                  {signedPercent(activeDelta)}
                </em>
              )}
            </>
          ) : (
            <span className="muted">Sem coleta nesta semana</span>
          )}
        </span>
      </div>

      {visiblePrimary.length < 2 ? (
        <div className="chart-empty">
          Coletas insuficientes nesta janela para traçar a curva semanal. Ausências permanecem sem interpolação.
        </div>
      ) : (
        <>
          <svg
            ref={svgRef}
            className="trend-svg"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label={`Série semanal de ${primaryLabel}, variando entre ${money(minVal)} e ${money(maxVal)}`}
            onMouseMove={handlePointer}
            onMouseLeave={() => setHoverWeek(null)}
            onClick={handleClick}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.26" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {[
              { y: padTop, val: maxVal },
              { y: padTop + plotH / 2, val: midVal },
              { y: baselineY, val: minVal },
            ].map((tick, idx) => (
              <g key={idx}>
                <line
                  x1={padLeft}
                  y1={tick.y}
                  x2={width - padRight}
                  y2={tick.y}
                  stroke="#1e293b"
                  strokeDasharray={idx === 2 ? undefined : '3 4'}
                />
                <text
                  x={padLeft - 6}
                  y={tick.y + 3.5}
                  textAnchor="end"
                  className="chart-axis-text"
                >
                  {moneyCompact(tick.val)}
                </text>
              </g>
            ))}

            {activeX !== null && (
              <line
                x1={activeX}
                y1={padTop}
                x2={activeX}
                y2={baselineY}
                stroke={hoverWeek !== null ? '#94a3b8' : '#38bdf8'}
                strokeWidth="1"
                strokeDasharray="2 3"
              />
            )}

            {buildContiguousAreaPaths(primaryPoints, baselineY).map((d, idx) => (
              <path key={idx} d={d} fill={`url(#${gradientId})`} />
            ))}

            {refPoints.length >= 2 && (
              <path
                d={buildGapSafeLinePath(refPoints)}
                fill="none"
                stroke="#64748b"
                strokeWidth="1.5"
                strokeDasharray="4 3"
              />
            )}

            <path
              d={buildGapSafeLinePath(primaryPoints)}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {windowMode === '26w' &&
              primaryPoints.map(pt => (
                <circle
                  key={pt.w}
                  cx={pt.x}
                  cy={pt.y}
                  r={pt.w === activeW ? 4.2 : 1.8}
                  fill={pt.w === activeW ? '#f8fafc' : '#38bdf8'}
                  stroke={pt.w === activeW ? '#0284c7' : 'none'}
                  strokeWidth={pt.w === activeW ? 2 : 0}
                />
              ))}

            {windowMode === 'all' && activePoint && (
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                r={4.2}
                fill="#f8fafc"
                stroke="#0284c7"
                strokeWidth={2}
              />
            )}

            <text x={padLeft} y={height - 5} textAnchor="start" className="chart-axis-text">
              {weeks[startW] ? date(weeks[startW], { month: 'short', year: '2-digit' }) : ''}
            </text>
            <text
              x={padLeft + plotW / 2}
              y={height - 5}
              textAnchor="middle"
              className="chart-axis-text"
            >
              {weeks[Math.round((startW + endW) / 2)]
                ? date(weeks[Math.round((startW + endW) / 2)], { month: 'short', year: '2-digit' })
                : ''}
            </text>
            <text x={width - padRight} y={height - 5} textAnchor="end" className="chart-axis-text">
              {weeks[endW] ? date(weeks[endW], { month: 'short', year: '2-digit' }) : ''}
            </text>
          </svg>

          <div className="chart-legend">
            <span>
              <i className="swatch-primary" /> {primaryLabel}
            </span>
            {referenceLabel && refPoints.length >= 2 && (
              <span>
                <i className="swatch-ref" /> Ref.: {referenceLabel}
              </span>
            )}
            <span className="chart-gap-note">Semanas sem coleta ficam abertas</span>
          </div>
        </>
      )}
    </section>
  );
}

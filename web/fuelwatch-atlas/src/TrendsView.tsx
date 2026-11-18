import { useMemo } from 'react';
import { AlertTriangle, ArrowLeft, Calendar, Fuel, MapPin, TrendingUp } from 'lucide-react';
import TrendChart from './TrendChart';
import {
  count,
  money,
  semesterMilestones,
  signedPercent,
  unitLabel,
  weekLabel,
  type ChartWindow,
  type CityRow,
  type Manifest,
  type Observation,
  type ProductData,
  type Selection,
} from './data';

type Props = {
  manifest: Manifest;
  data: ProductData | null;
  productId: string;
  onChangeProduct: (id: string) => void;
  week: number;
  onChangeWeek: (w: number) => void;
  selection: Selection;
  onSelect: (next: Selection) => void;
  windowMode: ChartWindow;
  onWindowChange: (mode: ChartWindow) => void;
  onBackToMap: () => void;
};

export default function TrendsView({
  manifest,
  data,
  productId,
  onChangeProduct,
  week,
  onChangeWeek,
  selection,
  onSelect,
  windowMode,
  onWindowChange,
  onBackToMap,
}: Props) {
  const product = manifest.products.find(p => p.id === productId) || manifest.products[0];
  const stateMeta = manifest.states.find(s => s.uf === selection.uf);
  const cityMeta = manifest.cities.find(c => c.id === selection.city);
  const ufCities = useMemo(
    () =>
      selection.uf
        ? manifest.cities
            .filter(c => c.uf === selection.uf)
            .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
        : [],
    [manifest.cities, selection.uf],
  );

  const { primaryRows, refRows, primaryLabel, refLabel } = useMemo(() => {
    if (!data) {
      return {
        primaryRows: [] as Observation[],
        refRows: undefined,
        primaryLabel: 'Brasil',
        refLabel: undefined,
      };
    }
    const ufSeries = selection.uf ? data.states.filter(r => r.uf === selection.uf) : undefined;
    if (selection.city) {
      return {
        primaryRows: data.cities.filter(r => r.id === selection.city),
        refRows: ufSeries,
        primaryLabel: `${cityMeta?.name || 'Município'} (${selection.uf})`,
        refLabel: selection.uf ? `Mediana ${selection.uf}` : undefined,
      };
    }
    if (selection.uf) {
      return {
        primaryRows: ufSeries || [],
        refRows: data.national,
        primaryLabel: `${stateMeta?.name || selection.uf} (${selection.uf})`,
        refLabel: 'Mediana Brasil',
      };
    }
    return {
      primaryRows: data.national,
      refRows: undefined,
      primaryLabel: 'Brasil (Mediana Nacional)',
      refLabel: undefined,
    };
  }, [data, selection.city, selection.uf, cityMeta, stateMeta]);

  const currentObs = primaryRows.find(r => r.w === week);
  const refObs = refRows?.find(r => r.w === week);
  const deltaVsRef =
    currentObs && currentObs.eligible !== false && refObs && refObs.p > 0
      ? (currentObs.p / refObs.p - 1) * 100
      : undefined;

  const seriesStats = useMemo(() => {
    if (!primaryRows.length) return null;
    const prices = primaryRows.map(r => r.p);
    const minRow = primaryRows.reduce((best, r) => (r.p < best.p ? r : best), primaryRows[0]);
    const maxRow = primaryRows.reduce((best, r) => (r.p > best.p ? r : best), primaryRows[0]);
    const first = primaryRows[0];
    const last = primaryRows[primaryRows.length - 1];
    const changePct = first.p > 0 ? (last.p / first.p - 1) * 100 : 0;
    return {
      minPrice: Math.min(...prices),
      minWeek: minRow.w,
      maxPrice: Math.max(...prices),
      maxWeek: maxRow.w,
      weeksObserved: primaryRows.length,
      changePct,
    };
  }, [primaryRows]);

  const milestones = useMemo(() => semesterMilestones(manifest.weeks), [manifest.weeks]);
  const isPartialWeek = week === manifest.weeks.length - 1;
  const cityCurrentRow = selection.city
    ? (currentObs as CityRow | undefined)
    : undefined;

  return (
    <main className="subpage-scroll">
      <header className="wa-hero-banner">
        <div className="wa-hero-inner">
          <button type="button" className="wa-hero-back" onClick={onBackToMap}>
            <ArrowLeft size={16} />
            Voltar ao mapa de preços
          </button>
          <div className="wa-hero-title-row">
            <div>
              <span className="wa-hero-eyebrow">
                <TrendingUp size={15} /> ANÁLISE TEMPORAL · SÉRIE ANP AUDITADA
              </span>
              <h1>Tendências de preços</h1>
              <p>
                Acompanhe a evolução semanal das medianas por posto (peso 1 por revenda) entre janeiro de 2024 e junho de 2026.
              </p>
            </div>
            <button type="button" className="wa-btn-light" onClick={onBackToMap}>
              <MapPin size={16} />
              Abrir recorte no mapa
            </button>
          </div>
        </div>
      </header>

      <div className="subpage-container">
        <section className="wa-elevated-card">
          {/* Controls Strip */}
          <div className="subpage-controls-grid">
            <label className="wa-field">
              <span>
                <Fuel size={14} /> Combustível
              </span>
              <select value={productId} onChange={e => onChangeProduct(e.target.value)}>
                {manifest.products.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.label} (R$/{unitLabel(p.unit)})
                  </option>
                ))}
              </select>
            </label>

            <label className="wa-field">
              <span>Estado (UF)</span>
              <select
                value={selection.uf || ''}
                onChange={e =>
                  onSelect(e.target.value ? { uf: e.target.value } : {})
                }
              >
                <option value="">Brasil (27 UFs)</option>
                {manifest.states
                  .slice()
                  .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
                  .map(s => (
                    <option key={s.uf} value={s.uf}>
                      {s.name} ({s.uf})
                    </option>
                  ))}
              </select>
            </label>

            <label className="wa-field">
              <span>Município pesquisado</span>
              <select
                value={selection.city || ''}
                disabled={!selection.uf}
                onChange={e =>
                  onSelect({
                    uf: selection.uf,
                    city: e.target.value || undefined,
                  })
                }
              >
                <option value="">
                  {selection.uf ? `Toda a UF (${selection.uf})` : 'Selecione uma UF primeiro'}
                </option>
                {ufCities.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="wa-field">
              <span>
                <Calendar size={14} /> Semana em foco
              </span>
              <select value={week} onChange={e => onChangeWeek(Number(e.target.value))}>
                {manifest.weeks.map((wIso, idx) => (
                  <option key={wIso} value={idx}>
                    S{idx + 1} · {weekLabel(wIso, manifest.dataset.periodEnd)}
                    {idx === manifest.weeks.length - 1 ? ' (Parcial)' : ''}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="subpage-semester-bar">
            <span>Atalhos semestrais:</span>
            <div className="filter-semester-chips">
              {milestones.map(m => (
                <button
                  key={m.id}
                  type="button"
                  className={week === m.weekIndex ? 'active' : ''}
                  onClick={() => onChangeWeek(m.weekIndex)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {isPartialWeek && (
            <div className="partial-alert" role="note">
              <AlertTriangle size={15} />
              <span>
                Semana parcial selecionada (29–30/06/2026): compreende apenas 2 dias de pesquisa antes do encerramento do corte semestral.
              </span>
            </div>
          )}

          {/* KPI Strip */}
          <div className="trends-kpi-grid">
            <div className="trends-kpi-card">
              <span className="eyebrow">MEDIANA NA SEMANA {week + 1}</span>
              <strong>
                {currentObs ? `${money(currentObs.p)} / ${unitLabel(product.unit)}` : 'Sem coleta'}
              </strong>
              <small>
                {currentObs
                  ? `${count(currentObs.n)} postos · ${count(currentObs.c)} coletas`
                  : 'Nenhuma pesquisa registrada'}
              </small>
            </div>

            <div className="trends-kpi-card">
              <span className="eyebrow">COMPARATIVO DE REFERÊNCIA</span>
              <strong
                className={
                  deltaVsRef !== undefined
                    ? deltaVsRef < 0
                      ? 'text-teal'
                      : deltaVsRef > 0
                        ? 'text-crimson'
                        : ''
                    : ''
                }
              >
                {deltaVsRef !== undefined
                  ? `${signedPercent(deltaVsRef)} vs. ${refLabel}`
                  : selection.uf
                    ? currentObs && currentObs.eligible === false
                      ? 'Cobertura < mínimo'
                      : '—'
                    : 'Base nacional'}
              </strong>
              <small>
                {cityCurrentRow?.ref
                  ? `Ref. estadual: ${money(cityCurrentRow.ref)}`
                  : refObs
                    ? `Ref. nacional: ${money(refObs.p)}`
                    : 'Exige ≥10 postos UF / ≥3 mun.'}
              </small>
            </div>

            <div className="trends-kpi-card">
              <span className="eyebrow">MENOR MEDIANA DA SÉRIE</span>
              <strong className="text-crimson">
                {seriesStats ? money(seriesStats.minPrice) : '—'}
              </strong>
              <small>
                {seriesStats
                  ? weekLabel(manifest.weeks[seriesStats.minWeek], manifest.dataset.periodEnd)
                  : '—'}
              </small>
            </div>

            <div className="trends-kpi-card">
              <span className="eyebrow">MAIOR MEDIANA &amp; VARIAÇÃO</span>
              <strong>{seriesStats ? money(seriesStats.maxPrice) : '—'}</strong>
              <small>
                {seriesStats
                  ? `Acumulado 2024–2026: ${signedPercent(seriesStats.changePct)} (${seriesStats.weeksObserved}/${manifest.weeks.length} sem.)`
                  : '—'}
              </small>
            </div>
          </div>

          {/* Wide Interactive SVG Chart */}
          <TrendChart
            rows={primaryRows}
            referenceRows={refRows}
            referenceLabel={refLabel}
            primaryLabel={primaryLabel}
            unit={product.unit}
            week={week}
            weeks={manifest.weeks}
            windowMode={windowMode}
            onWindowChange={onWindowChange}
            onSelectWeek={onChangeWeek}
            variant="wide"
          />

          {currentObs && (
            <div className="trends-spread-footer">
              <div>
                <strong>Amplitude bruta observada na semana selecionada:</strong>{' '}
                mínimo de <b>{money(currentObs.lo)}</b> e máximo de <b>{money(currentObs.hi)}</b> por{' '}
                {unitLabel(product.unit)} entre as coletas individuais aceitas na camada Silver/Gold.
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

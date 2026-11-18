import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Calendar, Check, Fuel, RotateCcw, Search, SlidersHorizontal, X } from 'lucide-react';
import DistributorBadge from './DistributorBadge';
import {
  count,
  normalize,
  semesterMilestones,
  TOP_NATIONAL_DISTRIBUTORS,
  unitLabel,
  weekLabel,
  type Manifest,
  type Metric,
  type SortMode,
} from './data';

type DistributorOption = {
  name: string;
  count: number;
};

type Props = {
  manifest: Manifest;
  productId: string;
  week: number;
  sort: SortMode;
  metric: Metric;
  selectedBrands: string[];
  availableBrands: DistributorOption[];
  hasLoadedUf: boolean;
  onApply: (next: {
    productId: string;
    week: number;
    sort: SortMode;
    metric: Metric;
    selectedBrands: string[];
  }) => void;
  onClose: () => void;
};

export default function FiltersModal({
  manifest,
  productId,
  week,
  sort,
  metric,
  selectedBrands,
  availableBrands,
  hasLoadedUf,
  onApply,
  onClose,
}: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [draftProduct, setDraftProduct] = useState(productId);
  const [draftWeek, setDraftWeek] = useState(week);
  const [draftSort, setDraftSort] = useState<SortMode>(sort);
  const [draftMetric, setDraftMetric] = useState<Metric>(metric);
  const [draftBrands, setDraftBrands] = useState<string[]>(selectedBrands);
  const [brandQuery, setBrandQuery] = useState('');

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const milestones = useMemo(() => semesterMilestones(manifest.weeks), [manifest.weeks]);
  const latestCompleteWeek = Math.max(0, manifest.weeks.length - 2);
  const isPartialDraftWeek = draftWeek === manifest.weeks.length - 1;

  const brandOptions = useMemo<DistributorOption[]>(() => {
    if (availableBrands.length > 0) return availableBrands;
    return TOP_NATIONAL_DISTRIBUTORS.map(name => ({ name, count: 0 }));
  }, [availableBrands]);

  const filteredBrands = useMemo(() => {
    const q = normalize(brandQuery.trim());
    if (!q) return brandOptions;
    return brandOptions.filter(item => normalize(item.name).includes(q));
  }, [brandOptions, brandQuery]);

  const toggleBrand = (name: string) => {
    setDraftBrands(prev =>
      prev.includes(name) ? prev.filter(b => b !== name) : [...prev, name],
    );
  };

  const handleReset = () => {
    setDraftProduct('gasolina');
    setDraftWeek(latestCompleteWeek);
    setDraftSort('low');
    setDraftMetric('price');
    setDraftBrands([]);
    setBrandQuery('');
  };

  const handleConfirm = () => {
    onApply({
      productId: draftProduct,
      week: draftWeek,
      sort: draftSort,
      metric: draftMetric,
      selectedBrands: draftBrands,
    });
    dialogRef.current?.close();
  };

  return (
    <dialog
      ref={dialogRef}
      className="filters-dialog"
      onClose={onClose}
      onClick={event => {
        if (event.target === event.currentTarget) dialogRef.current?.close();
      }}
    >
      <div className="filters-dialog-head">
        <div className="filters-dialog-title">
          <SlidersHorizontal size={18} />
          <h2>Filtros de pesquisa</h2>
        </div>
        <button
          type="button"
          className="icon-btn"
          aria-label="Fechar filtros"
          onClick={() => dialogRef.current?.close()}
        >
          <X size={20} />
        </button>
      </div>

      <div className="filters-dialog-body">
        {/* 1. Combustível */}
        <section className="filter-section">
          <div className="filter-section-head">
            <span className="filter-section-label">
              <Fuel size={15} /> Combustível
            </span>
            <small>Unidades preservadas (L vs. m³)</small>
          </div>
          <div className="filter-fuel-grid" role="radiogroup" aria-label="Tipo de combustível">
            {manifest.products.map(p => {
              const checked = draftProduct === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  className={`filter-radio-card ${checked ? 'active' : ''}`}
                  onClick={() => setDraftProduct(p.id)}
                >
                  <span className="radio-dot" />
                  <span className="filter-radio-copy">
                    <strong>{p.label}</strong>
                    <small>R$ / {unitLabel(p.unit)}</small>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {/* 2. Período / Semana ISO */}
        <section className="filter-section">
          <div className="filter-section-head">
            <span className="filter-section-label">
              <Calendar size={15} /> Semana histórica (ANP)
            </span>
            <span className="filter-week-badge">
              Semana {draftWeek + 1}/{manifest.weeks.length} ·{' '}
              {weekLabel(manifest.weeks[draftWeek], manifest.dataset.periodEnd)}
            </span>
          </div>

          <input
            type="range"
            className="wa-range"
            min={0}
            max={manifest.weeks.length - 1}
            value={draftWeek}
            aria-label="Selecionar semana histórica"
            onChange={e => setDraftWeek(Number(e.target.value))}
          />

          <div className="filter-semester-chips">
            {milestones.map(m => (
              <button
                key={m.id}
                type="button"
                className={draftWeek === m.weekIndex ? 'active' : ''}
                onClick={() => setDraftWeek(m.weekIndex)}
              >
                {m.label}
              </button>
            ))}
          </div>

          {isPartialDraftWeek && (
            <div className="partial-alert" role="note">
              <AlertTriangle size={15} />
              <span>
                A última semana do snapshot (29–30/06/2026) contém apenas 2 dias de coleta antes do corte semestral.
              </span>
            </div>
          )}
        </section>

        {/* 3. Ordenação & Modo do Mapa */}
        <section className="filter-section filter-two-col">
          <div>
            <span className="filter-section-label">Ordenar lista por</span>
            <div className="segmented-control">
              <button
                type="button"
                className={draftSort === 'low' ? 'active' : ''}
                onClick={() => setDraftSort('low')}
              >
                Menor preço
              </button>
              <button
                type="button"
                className={draftSort === 'high' ? 'active' : ''}
                onClick={() => setDraftSort('high')}
              >
                Maior
              </button>
              <button
                type="button"
                className={draftSort === 'coverage' ? 'active' : ''}
                onClick={() => setDraftSort('coverage')}
              >
                Coletas
              </button>
            </div>
          </div>

          <div>
            <span className="filter-section-label">Cor das regiões</span>
            <div className="segmented-control">
              <button
                type="button"
                className={draftMetric === 'price' ? 'active' : ''}
                onClick={() => setDraftMetric('price')}
              >
                Preço (R$)
              </button>
              <button
                type="button"
                className={draftMetric === 'comparison' ? 'active' : ''}
                onClick={() => setDraftMetric('comparison')}
              >
                Desvio (%)
              </button>
            </div>
          </div>
        </section>

        {/* 4. Bandeiras / Distribuidoras */}
        <section className="filter-section">
          <div className="filter-section-head">
            <span className="filter-section-label">
              Bandeiras / Distribuidoras
              {draftBrands.length > 0 && (
                <em className="filter-count-pill">{draftBrands.length} selecionadas</em>
              )}
            </span>
            {draftBrands.length > 0 && (
              <button
                type="button"
                className="text-link-btn"
                onClick={() => setDraftBrands([])}
              >
                Todas as bandeiras
              </button>
            )}
          </div>

          {!hasLoadedUf && (
            <p className="filter-hint">
              Pré-selecione bandeiras nacionais abaixo ou clique em uma UF no mapa para listar todas as distribuidoras regionais.
            </p>
          )}

          <div className="filter-brand-search">
            <Search size={14} />
            <input
              type="search"
              placeholder="Filtrar bandeira (ex.: Vibra, Ipiranga, Raízen, Branca)…"
              value={brandQuery}
              onChange={e => setBrandQuery(e.target.value)}
            />
          </div>

          <div className="filter-brand-list" role="group" aria-label="Filtrar por distribuidora">
            {filteredBrands.map(item => {
              const selected = draftBrands.includes(item.name);
              return (
                <button
                  key={item.name}
                  type="button"
                  role="checkbox"
                  aria-checked={selected}
                  className={`filter-brand-row ${selected ? 'selected' : ''}`}
                  onClick={() => toggleBrand(item.name)}
                >
                  <span className={`checkbox-box ${selected ? 'checked' : ''}`}>
                    {selected && <Check size={12} strokeWidth={3} />}
                  </span>
                  <DistributorBadge distributor={item.name} size="sm" />
                  <span className="filter-brand-name">{item.name}</span>
                  {item.count > 0 && (
                    <small className="filter-brand-count">{count(item.count)} postos</small>
                  )}
                </button>
              );
            })}
            {filteredBrands.length === 0 && (
              <p className="filter-empty">Nenhuma bandeira encontrada para “{brandQuery}”.</p>
            )}
          </div>
        </section>
      </div>

      <div className="filters-dialog-foot">
        <button type="button" className="wa-btn-secondary" onClick={handleReset}>
          <RotateCcw size={15} />
          Limpar
        </button>
        <button type="button" className="wa-btn-primary" onClick={handleConfirm}>
          Aplicar filtros
        </button>
      </div>
    </dialog>
  );
}

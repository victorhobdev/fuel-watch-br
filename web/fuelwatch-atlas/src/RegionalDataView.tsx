import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Download,
  Fuel,
  MapPin,
  Search,
  Table,
} from 'lucide-react';
import {
  count,
  downloadCsv,
  money,
  normalize,
  priceDigits,
  signedPercent,
  unitLabel,
  weekLabel,
  type Manifest,
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
  onOpenOnMap: (selection: Selection) => void;
  onBackToMap: () => void;
};

const REGIONS = ['Todas', 'Sudeste', 'Sul', 'Nordeste', 'Centro-Oeste', 'Norte'] as const;

export default function RegionalDataView({
  manifest,
  data,
  productId,
  onChangeProduct,
  week,
  onChangeWeek,
  onOpenOnMap,
  onBackToMap,
}: Props) {
  const [scopeLevel, setScopeLevel] = useState<'states' | 'cities'>('states');
  const [regionFilter, setRegionFilter] = useState<string>('Todas');
  const [ufFilter, setUfFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'priceAsc' | 'priceDesc' | 'stationsDesc' | 'nameAsc'>(
    'priceAsc',
  );
  const [limit, setLimit] = useState(100);

  const product = manifest.products.find(p => p.id === productId) || manifest.products[0];
  const weekStates = useMemo(() => data?.states.filter(r => r.w === week) || [], [data, week]);
  const weekCities = useMemo(() => data?.cities.filter(r => r.w === week) || [], [data, week]);
  const nationalRow = useMemo(() => data?.national.find(r => r.w === week), [data, week]);

  const rows = useMemo(() => {
    const q = normalize(search.trim());
    if (scopeLevel === 'states') {
      const items = weekStates
        .map(r => {
          const st = manifest.states.find(s => s.uf === r.uf);
          const delta =
            r.eligible && nationalRow?.p ? (r.p / nationalRow.p - 1) * 100 : undefined;
          return {
            key: r.uf,
            name: st?.name || r.uf,
            uf: r.uf,
            region: st?.region || '',
            price: r.p,
            lo: r.lo,
            hi: r.hi,
            stations: r.n,
            collections: r.c,
            eligible: Boolean(r.eligible),
            delta,
            refLabel: 'Brasil',
            selection: { uf: r.uf } as Selection,
          };
        })
        .filter(item => {
          if (regionFilter !== 'Todas' && item.region !== regionFilter) return false;
          if (q && !normalize(`${item.name} ${item.uf} ${item.region}`).includes(q)) return false;
          return true;
        });

      return items.sort((a, b) =>
        sortBy === 'priceAsc'
          ? a.price - b.price
          : sortBy === 'priceDesc'
            ? b.price - a.price
            : sortBy === 'stationsDesc'
              ? b.stations - a.stations
              : a.name.localeCompare(b.name, 'pt-BR'),
      );
    }

    const items = weekCities
      .map(r => {
        const city = manifest.cities.find(c => c.id === r.id);
        const st = manifest.states.find(s => s.uf === city?.uf);
        const delta = r.eligible && r.ref ? (r.p / r.ref - 1) * 100 : undefined;
        return {
          key: r.id,
          name: city?.name || r.id,
          uf: city?.uf || '',
          region: st?.region || '',
          price: r.p,
          lo: r.lo,
          hi: r.hi,
          stations: r.n,
          collections: r.c,
          eligible: Boolean(r.eligible),
          delta,
          refLabel: city?.uf || 'UF',
          selection: { uf: city?.uf, city: r.id } as Selection,
        };
      })
      .filter(item => {
        if (regionFilter !== 'Todas' && item.region !== regionFilter) return false;
        if (ufFilter && item.uf !== ufFilter) return false;
        if (q && !normalize(`${item.name} ${item.uf} ${item.region}`).includes(q)) return false;
        return true;
      });

    return items.sort((a, b) =>
      sortBy === 'priceAsc'
        ? a.price - b.price
        : sortBy === 'priceDesc'
          ? b.price - a.price
          : sortBy === 'stationsDesc'
            ? b.stations - a.stations
            : a.name.localeCompare(b.name, 'pt-BR'),
    );
  }, [
    scopeLevel,
    weekStates,
    weekCities,
    manifest.states,
    manifest.cities,
    nationalRow,
    regionFilter,
    ufFilter,
    search,
    sortBy,
  ]);

  const minPriceInTable = useMemo(
    () => (rows.length ? Math.min(...rows.map(r => r.price)) : undefined),
    [rows],
  );

  const handleExportCsv = () => {
    const wIso = manifest.weeks[week] || '';
    const filename = `fuelwatch-br-${productId}-${scopeLevel}-${wIso}.csv`;
    const headers = [
      'Semana_Inicio',
      'Combustivel',
      'Unidade',
      'Nivel',
      'Localidade',
      'UF',
      'Regiao',
      'Mediana_BRL',
      'Minimo_Bruto_BRL',
      'Maximo_Bruto_BRL',
      'Desvio_Ref_Pct',
      'Elegivel_Comparacao',
      'Postos_Observados',
      'Coletas_Aceitas',
    ];
    const csvRows = rows.map(r => [
      wIso,
      product.label,
      unitLabel(product.unit),
      scopeLevel === 'states' ? 'UF' : 'Municipio',
      r.name,
      r.uf,
      r.region,
      priceDigits(r.price),
      priceDigits(r.lo),
      priceDigits(r.hi),
      r.delta !== undefined ? r.delta.toFixed(2).replace('.', ',') : '',
      r.eligible ? 'Sim' : 'Nao',
      r.stations,
      r.collections,
    ]);
    downloadCsv(filename, headers, csvRows);
  };

  const isPartialWeek = week === manifest.weeks.length - 1;
  const visibleSlice = rows.slice(0, limit);

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
                <Table size={15} /> TABELA CONSOLIDADA · SNAPSHOT GOLD
              </span>
              <h1>Médias e dados regionais</h1>
              <p>
                Consulte rankings estaduais e municipais por semana ISO, verifique elegibilidade de cobertura e exporte os dados auditados em CSV.
              </p>
            </div>
            <button type="button" className="wa-btn-light" onClick={handleExportCsv}>
              <Download size={16} />
              Exportar CSV ({count(rows.length)})
            </button>
          </div>
        </div>
      </header>

      <div className="subpage-container">
        <section className="wa-elevated-card">
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
              <span>Recorte territorial</span>
              <select
                value={scopeLevel}
                onChange={e => {
                  setScopeLevel(e.target.value as 'states' | 'cities');
                  setLimit(100);
                }}
              >
                <option value="states">Estados (27 UFs)</option>
                <option value="cities">Municípios pesquisados (462)</option>
              </select>
            </label>

            <label className="wa-field">
              <span>Macro-região</span>
              <select value={regionFilter} onChange={e => setRegionFilter(e.target.value)}>
                {REGIONS.map(reg => (
                  <option key={reg} value={reg}>
                    {reg === 'Todas' ? 'Todas as regiões' : reg}
                  </option>
                ))}
              </select>
            </label>

            <label className="wa-field">
              <span>
                <Calendar size={14} /> Semana histórica
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

          <div className="table-toolbar">
            <div className="table-search">
              <Search size={15} />
              <input
                type="search"
                placeholder={
                  scopeLevel === 'states'
                    ? 'Filtrar estado ou sigla…'
                    : 'Filtrar município ou sigla da UF…'
                }
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>

            {scopeLevel === 'cities' && (
              <select
                className="compact-select"
                aria-label="Filtrar por UF"
                value={ufFilter}
                onChange={e => setUfFilter(e.target.value)}
              >
                <option value="">Todas as UFs</option>
                {manifest.states
                  .slice()
                  .sort((a, b) => a.uf.localeCompare(b.uf))
                  .map(s => (
                    <option key={s.uf} value={s.uf}>
                      {s.uf} — {s.name}
                    </option>
                  ))}
              </select>
            )}

            <select
              className="compact-select"
              aria-label="Ordenar tabela"
              value={sortBy}
              onChange={e => setSortBy(e.target.value as typeof sortBy)}
            >
              <option value="priceAsc">Menor preço primeiro</option>
              <option value="priceDesc">Maior preço primeiro</option>
              <option value="stationsDesc">Mais postos pesquisados</option>
              <option value="nameAsc">Ordem alfabética (A–Z)</option>
            </select>
          </div>

          {isPartialWeek && (
            <div className="partial-alert" role="note">
              <AlertTriangle size={15} />
              <span>
                A semana selecionada (29–30/06/2026) possui cobertura parcial de 2 dias.
              </span>
            </div>
          )}

          <div className="wa-table-wrap">
            <table className="wa-data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Localidade</th>
                  <th>Região</th>
                  <th>Mediana (R$/{unitLabel(product.unit)})</th>
                  <th>Mín. – Máx. bruto</th>
                  <th>vs. Referência</th>
                  <th>Postos</th>
                  <th>Coletas</th>
                  <th aria-label="Ação" />
                </tr>
              </thead>
              <tbody>
                {visibleSlice.map((r, idx) => {
                  const isCheapest =
                    minPriceInTable !== undefined && Math.abs(r.price - minPriceInTable) < 0.0005;
                  return (
                    <tr key={r.key} className={isCheapest ? 'row-cheapest' : ''}>
                      <td className="num-col">{idx + 1}</td>
                      <td>
                        <strong>{r.name}</strong>{' '}
                        <span className="uf-inline-tag">{r.uf}</span>
                      </td>
                      <td>{r.region}</td>
                      <td className={`num-col price-cell ${isCheapest ? 'text-crimson' : ''}`}>
                        <strong>{money(r.price)}</strong>
                      </td>
                      <td className="num-col muted-cell">
                        {money(r.lo)} – {money(r.hi)}
                      </td>
                      <td className="num-col">
                        {r.delta !== undefined ? (
                          <span
                            className={`delta-pill ${
                              r.delta < 0 ? 'down' : r.delta > 0 ? 'up' : ''
                            }`}
                          >
                            {signedPercent(r.delta)} vs. {r.refLabel}
                          </span>
                        ) : (
                          <span className="ineligible-tag" title="Abaixo da cobertura mínima">
                            Cobertura &lt; mín.
                          </span>
                        )}
                      </td>
                      <td className="num-col">{count(r.stations)}</td>
                      <td className="num-col">{count(r.collections)}</td>
                      <td className="action-col">
                        <button
                          type="button"
                          className="table-map-btn"
                          onClick={() => onOpenOnMap(r.selection)}
                        >
                          <MapPin size={13} /> Mapa
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="empty-table-cell">
                      Nenhum registro encontrado para os filtros aplicados nesta semana.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {rows.length > limit && (
            <div className="table-more-bar">
              <button
                type="button"
                className="wa-btn-secondary"
                onClick={() => setLimit(prev => prev + 150)}
              >
                Mostrar mais resultados ({count(rows.length - limit)} restantes)
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

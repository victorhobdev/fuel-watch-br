import { useEffect, useMemo, useRef, useState } from 'react';
import { animate, useReducedMotion } from 'motion/react';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Building2,
  ChevronLeft,
  ChevronRight,
  Database,
  Droplet,
  Fuel,
  Info,
  MapPin,
  Pause,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  Store,
  X,
} from 'lucide-react';
import AtlasMap from './AtlasMap';
import TrendChart from './TrendChart';
import MethodologyModal from './MethodologyModal';
import {
  count,
  date,
  getData,
  money,
  normalize,
  priceColor,
  semesterMilestones,
  signedPercent,
  stationId,
  unitLabel,
  weekLabel,
  type ActiveStation,
  type ChartWindow,
  type CityRow,
  type ExplorerTab,
  type Manifest,
  type Metric,
  type Observation,
  type ProductData,
  type Selection,
  type SortMode,
  type StateRow,
  type StationFeature,
  type StationFile,
} from './data';

const REGIONS = ['Todas', 'Sudeste', 'Sul', 'Nordeste', 'Centro-Oeste', 'Norte'] as const;

function PriceTicker({ value }: { value: number }) {
  const spanRef = useRef<HTMLSpanElement>(null);
  const prevRef = useRef(value);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) {
      if (spanRef.current) spanRef.current.textContent = money(value);
      prevRef.current = value;
      return;
    }
    const controls = animate(prevRef.current, value, {
      duration: 0.28,
      ease: 'easeOut',
      onUpdate: latest => {
        if (spanRef.current) spanRef.current.textContent = money(latest);
      },
    });
    prevRef.current = value;
    return () => controls.stop();
  }, [value, reduced]);

  return (
    <span aria-label={money(value)}>
      <span ref={spanRef} aria-hidden="true">
        {money(value)}
      </span>
    </span>
  );
}

function SpreadBar({
  lo,
  median,
  hi,
  reference,
  referenceLabel,
}: {
  lo: number;
  median: number;
  hi: number;
  reference?: number;
  referenceLabel?: string;
}) {
  const span = hi - lo;
  const medianPct = span > 0 ? Math.max(0, Math.min(100, ((median - lo) / span) * 100)) : 50;
  const refPct =
    reference !== undefined && span > 0 && reference >= lo && reference <= hi
      ? ((reference - lo) / span) * 100
      : undefined;

  return (
    <div className="spread-block" aria-label={`Amplitude observada de ${money(lo)} a ${money(hi)}`}>
      <div className="spread-labels">
        <span>
          Mínimo bruto: <b>{money(lo)}</b>
        </span>
        <span>
          Máximo bruto: <b>{money(hi)}</b>
        </span>
      </div>
      <div className="spread-track">
        <div className="spread-fill" />
        {refPct !== undefined && (
          <span
            className="spread-ref-marker"
            style={{ left: `${refPct}%` }}
            title={`Referência ${referenceLabel || ''}: ${money(reference!)}`}
          />
        )}
        <span
          className="spread-median-marker"
          style={{ left: `${medianPct}%` }}
          title={`Mediana: ${money(median)}`}
        />
      </div>
    </div>
  );
}

export default function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [data, setData] = useState<ProductData | null>(null);
  const [productId, setProductId] = useState('gasolina');
  const [week, setWeek] = useState(129); // Penúltima semana (última semana ISO completa); a parcial permanece selecionável.
  const [playing, setPlaying] = useState(false);

  const [selection, setSelection] = useState<Selection>({});
  const [focusedStationKey, setFocusedStationKey] = useState<string | null>(null);
  const [showStations, setShowStations] = useState(true);

  const [metric, setMetric] = useState<Metric>('price');
  const [explorerTab, setExplorerTab] = useState<ExplorerTab>('regions');
  const [regionFilter, setRegionFilter] = useState<string>('Todas');
  const [sort, setSort] = useState<SortMode>('low');
  const [listFilter, setListFilter] = useState('');
  const [showAllStations, setShowAllStations] = useState(false);
  const [chartWindow, setChartWindow] = useState<ChartWindow>('26w');

  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [methodology, setMethodology] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  const [stationFile, setStationFile] = useState<StationFile | null>(null);
  const [loadingStations, setLoadingStations] = useState(false);
  const [stationError, setStationError] = useState(false);

  const searchBoxRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const reducedMotion = useReducedMotion();

  // Initial Manifest Load
  useEffect(() => {
    let active = true;
    getData<Manifest>('manifest.json')
      .then(loaded => {
        if (!active) return;
        setManifest(loaded);
        setWeek(Math.max(0, loaded.weeks.length - 2));
        setError('');
      })
      .catch(() => {
        if (active) {
          setError('Não foi possível abrir o manifesto do snapshot. Verifique sua conexão e tente novamente.');
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [retry]);

  // Product Slice Load
  useEffect(() => {
    if (!manifest) return;
    let active = true;
    setLoading(true);
    setError('');
    const prod = manifest.products.find(p => p.id === productId) || manifest.products[0];
    getData<ProductData>(prod.file)
      .then(slice => {
        if (!active) return;
        setData(slice);
        setLoading(false);
      })
      .catch(() => {
        if (active) {
          setError('Não foi possível carregar os dados deste combustível. Tente novamente.');
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [manifest, productId, retry]);

  // Strict Lazy Load of Station GeoJSON: ONLY after a UF is selected
  useEffect(() => {
    setFocusedStationKey(null);
    setShowAllStations(false);
    if (!manifest || !selection.uf || !manifest.stationLayer) {
      setStationFile(null);
      setLoadingStations(false);
      setStationError(false);
      return;
    }
    let active = true;
    const prod = manifest.products.find(item => item.id === productId);
    const path = (prod?.stationFile || manifest.stationLayer.filePattern)
      .replace('{product}', productId)
      .replace('{uf}', selection.uf);

    setStationFile(null);
    setLoadingStations(true);
    setStationError(false);

    getData<StationFile>(path)
      .then(file => {
        if (!active) return;
        setStationFile(file);
        setLoadingStations(false);
      })
      .catch(() => {
        if (!active) return;
        setStationError(true);
        setLoadingStations(false);
      });

    return () => {
      active = false;
    };
  }, [manifest, selection.uf, productId, retry]);

  // Outside click & '/' keyboard shortcut for Global Search
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!searchBoxRef.current?.contains(event.target as Node)) setSearching(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (event.key === '/' && tag !== 'INPUT' && tag !== 'SELECT' && tag !== 'TEXTAREA') {
        event.preventDefault();
        searchInputRef.current?.focus();
        setSearching(true);
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  // Timeline Autoplay
  useEffect(() => {
    if (!playing || !manifest) return;
    const maxWeek = manifest.weeks.length - 1;
    const timer = window.setInterval(() => {
      setWeek(prev => {
        if (prev >= maxWeek) {
          setPlaying(false);
          return maxWeek;
        }
        return prev + 1;
      });
    }, reducedMotion ? 750 : 420);
    return () => window.clearInterval(timer);
  }, [playing, manifest, reducedMotion]);

  const applySelection = (next: Selection) => {
    setSelection(next);
    setFocusedStationKey(null);
    setSearching(false);
    setQuery('');
    setListFilter('');
    setShowAllStations(false);
    if (!next.uf) {
      setExplorerTab('regions');
    } else if (next.city) {
      setExplorerTab('stations');
    } else {
      setExplorerTab('regions');
    }
  };

  const states = useMemo(() => data?.states.filter(r => r.w === week) || [], [data, week]);
  const cities = useMemo(() => data?.cities.filter(r => r.w === week) || [], [data, week]);
  const national = useMemo(() => data?.national.find(r => r.w === week), [data, week]);

  const stateMeta = useMemo(
    () => manifest?.states.find(s => s.uf === selection.uf),
    [manifest, selection.uf],
  );
  const cityMeta = useMemo(
    () => manifest?.cities.find(c => c.id === selection.city),
    [manifest, selection.city],
  );
  const stateRow = useMemo(
    () => states.find(r => r.uf === selection.uf),
    [states, selection.uf],
  );
  const cityById = useMemo(() => {
    const map = new Map<string, { name: string; uf: string }>();
    manifest?.cities.forEach(c => map.set(c.id, { name: c.name, uf: c.uf }));
    return map;
  }, [manifest]);

  const visibleCities = useMemo(
    () => cities.filter(c => cityById.get(c.id)?.uf === selection.uf),
    [cities, cityById, selection.uf],
  );

  const range = useMemo<[number, number]>(() => {
    if (metric === 'comparison') return [-15, 15];
    const values = (selection.uf ? visibleCities : states).map(r => r.p);
    return values.length ? [Math.min(...values), Math.max(...values)] : [0, 1];
  }, [states, visibleCities, selection.uf, metric]);

  // Active Stations for current UF / City / Week
  const activeStations = useMemo<ActiveStation[]>(() => {
    if (!selection.uf || !stationFile) return [];
    const result: ActiveStation[] = [];
    for (const feature of stationFile.features) {
      if (selection.city && feature.properties.municipalityId !== selection.city) continue;
      const priceTuple = feature.properties.prices.find(entry => entry[0] === week);
      if (!priceTuple) continue;
      const price = priceTuple[1] / 1000;
      const deltaPercent =
        stateRow?.eligible && stateRow.p ? (price / stateRow.p - 1) * 100 : undefined;
      const colorVal = metric === 'price' ? price : deltaPercent;
      const [lon, lat] = feature.geometry.coordinates;
      result.push({
        key: stationId(feature),
        lon,
        lat,
        price,
        collections: priceTuple[2],
        deltaPercent,
        color: priceColor(colorVal, ...range, metric),
        properties: feature.properties,
      });
    }
    return result;
  }, [selection.uf, selection.city, stationFile, week, stateRow, range, metric]);

  const focusedFeature = useMemo<StationFeature | undefined>(() => {
    if (!focusedStationKey || !stationFile) return undefined;
    return stationFile.features.find(f => stationId(f) === focusedStationKey);
  }, [focusedStationKey, stationFile]);

  const focusedActiveStation = useMemo(
    () => activeStations.find(s => s.key === focusedStationKey),
    [activeStations, focusedStationKey],
  );

  const currentRow: Observation | undefined = selection.city
    ? cities.find(r => r.id === selection.city)
    : selection.uf
      ? stateRow
      : national;

  const referenceValue = selection.city
    ? (currentRow as CityRow | undefined)?.ref
    : selection.uf
      ? national?.p
      : undefined;
  const referenceLabel = selection.city ? stateMeta?.uf || 'UF' : selection.uf ? 'Brasil' : undefined;

  const delta =
    selection.uf && currentRow?.eligible && referenceValue
      ? (currentRow.p / referenceValue - 1) * 100
      : undefined;

  const product = manifest?.products.find(p => p.id === productId);
  const dataIsCurrent = data?.id === productId;
  const regionName = cityMeta?.name || stateMeta?.name || 'Brasil';

  // Historical Chart Series (supports National, UF, City, OR Focused Station!)
  const { primaryChartRows, refChartRows, primaryChartLabel, refChartLabel } = useMemo(() => {
    if (!data) {
      return {
        primaryChartRows: [] as Observation[],
        refChartRows: undefined,
        primaryChartLabel: regionName,
        refChartLabel: undefined,
      };
    }
    const ufSeries = selection.uf ? data.states.filter(r => r.uf === selection.uf) : undefined;
    if (focusedFeature) {
      const stationSeries: Observation[] = focusedFeature.properties.prices.map(
        ([wIdx, mills, colls]) => ({
          w: wIdx,
          p: mills / 1000,
          n: 1,
          c: colls,
          lo: mills / 1000,
          hi: mills / 1000,
          eligible: true,
        }),
      );
      return {
        primaryChartRows: stationSeries,
        refChartRows: ufSeries,
        primaryChartLabel: focusedFeature.properties.name,
        refChartLabel: selection.uf ? `Mediana ${selection.uf}` : undefined,
      };
    }
    if (selection.city) {
      return {
        primaryChartRows: data.cities.filter(r => r.id === selection.city),
        refChartRows: ufSeries,
        primaryChartLabel: cityMeta?.name || 'Município',
        refChartLabel: selection.uf ? `Mediana ${selection.uf}` : undefined,
      };
    }
    if (selection.uf) {
      return {
        primaryChartRows: ufSeries || [],
        refChartRows: data.national,
        primaryChartLabel: stateMeta?.uf || 'UF',
        refChartLabel: 'Mediana Brasil',
      };
    }
    return {
      primaryChartRows: data.national,
      refChartRows: undefined,
      primaryChartLabel: 'Mediana Brasil',
      refChartLabel: undefined,
    };
  }, [data, focusedFeature, selection.city, selection.uf, cityMeta, stateMeta, regionName]);

  // Filtered & Sorted Region Rows (States or Cities)
  const filteredRegions = useMemo(() => {
    if (!manifest) return [];
    const q = normalize(listFilter.trim());
    if (!selection.uf) {
      return states
        .filter(row => {
          const st = manifest.states.find(s => s.uf === row.uf);
          if (!st) return false;
          if (regionFilter !== 'Todas' && st.region !== regionFilter) return false;
          if (q && !normalize(`${st.name} ${st.uf} ${st.region}`).includes(q)) return false;
          return true;
        })
        .sort((a, b) =>
          sort === 'low' ? a.p - b.p : sort === 'high' ? b.p - a.p : b.n - a.n,
        );
    }
    return visibleCities
      .filter(row => {
        const c = cityById.get(row.id);
        if (!c) return false;
        if (q && !normalize(c.name).includes(q)) return false;
        return true;
      })
      .sort((a, b) =>
        sort === 'low' ? a.p - b.p : sort === 'high' ? b.p - a.p : b.n - a.n,
      );
  }, [manifest, selection.uf, states, visibleCities, regionFilter, listFilter, sort, cityById]);

  // Filtered & Sorted Station Rows
  const filteredStations = useMemo(() => {
    const q = normalize(listFilter.trim());
    return activeStations
      .filter(st => {
        if (!q) return true;
        const p = st.properties;
        return normalize(
          `${p.name} ${p.distributor} ${p.neighborhood} ${p.municipality} ${p.address}`,
        ).includes(q);
      })
      .sort((a, b) =>
        sort === 'low'
          ? a.price - b.price
          : sort === 'high'
            ? b.price - a.price
            : b.collections - a.collections,
      );
  }, [activeStations, listFilter, sort]);

  // Global Quick Search Results (States + 462 Municipalities with live week price)
  const searchResults = useMemo(() => {
    if (!manifest) return [];
    const q = normalize(query.trim());
    const matchedStates = manifest.states
      .filter(s => normalize(`${s.name} ${s.uf} ${s.region}`).includes(q))
      .map(s => {
        const row = states.find(r => r.uf === s.uf);
        return {
          key: `uf-${s.uf}`,
          name: s.name,
          meta: `${s.uf} · ${s.region}`,
          price: row?.p,
          stations: row?.n,
          selection: { uf: s.uf } as Selection,
        };
      });
    const matchedCities =
      q.length >= 2
        ? manifest.cities
            .filter(c => normalize(`${c.name} ${c.uf}`).includes(q))
            .map(c => {
              const row = cities.find(r => r.id === c.id);
              return {
                key: `city-${c.id}`,
                name: c.name,
                meta: `${c.uf} · Município`,
                price: row?.p,
                stations: row?.n,
                selection: { uf: c.uf, city: c.id } as Selection,
              };
            })
        : [];
    return [...matchedStates, ...matchedCities].slice(0, 9);
  }, [manifest, query, states, cities]);

  const milestones = useMemo(
    () => (manifest ? semesterMilestones(manifest.weeks) : []),
    [manifest],
  );

  if (!manifest) {
    return (
      <div className="boot-screen">
        <div className="brand-mark">
          <span className="brand-badge">
            <Droplet size={20} />
          </span>
          <span className="brand-text">
            fuel<strong>watch</strong>
          </span>
          <small>ATLAS</small>
        </div>
        {error ? (
          <div className="boot-error" role="alert">
            <p>{error}</p>
            <button type="button" className="primary-btn" onClick={() => setRetry(v => v + 1)}>
              Tentar novamente
            </button>
          </div>
        ) : (
          <p className="boot-status" role="status">
            <span className="spinner" /> Inicializando observatório geográfico…
          </p>
        )}
      </div>
    );
  }

  const isPartialLastWeek = week === manifest.weeks.length - 1;
  const displayedStations = showAllStations ? filteredStations : filteredStations.slice(0, 80);

  return (
    <div className="atlas-shell">
      {/* Command Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          <a
            href={import.meta.env.BASE_URL}
            className="brand-mark"
            aria-label="Fuel Watch BR Atlas — voltar ao início"
            onClick={e => {
              e.preventDefault();
              applySelection({});
            }}
          >
            <span className="brand-badge">
              <Droplet size={19} />
            </span>
            <span className="brand-text">
              fuel<strong>watch</strong>
            </span>
            <small>ATLAS BR</small>
          </a>

          <div className="topbar-pills">
            <span className="status-pill">
              <i /> Snapshot validado no Microsoft Fabric · 2024–2026
            </span>
          </div>
        </div>

        <nav className="topbar-actions" aria-label="Ações e documentação">
          <button
            type="button"
            className="ghost-btn"
            onClick={() => setMethodology(true)}
          >
            <ShieldCheck size={16} />
            <span>Metodologia &amp; Linhagem</span>
          </button>
          <a
            href="https://github.com/victorhobdev/fuel-watch-br"
            target="_blank"
            rel="noreferrer"
            className="ghost-btn"
          >
            <Database size={15} />
            <span>Código &amp; Evidências ↗</span>
          </a>
        </nav>
      </header>

      {/* Filter & Search Deck */}
      <section className="control-deck" aria-label="Controles globais de combustível, busca e métrica">
        <div className="fuel-selector-group">
          <span className="control-label">
            <Fuel size={15} /> Combustível
          </span>
          <div className="fuel-pills" role="tablist" aria-label="Selecionar combustível">
            {manifest.products.map(p => (
              <button
                key={p.id}
                type="button"
                role="tab"
                aria-selected={productId === p.id}
                className={`fuel-pill ${productId === p.id ? 'active' : ''}`}
                onClick={() => setProductId(p.id)}
              >
                <span>{p.label}</span>
                <small>{unitLabel(p.unit)}</small>
              </button>
            ))}
          </div>
          <div className="fuel-select-mobile">
            <label className="sr-only" htmlFor="fuel-mobile-select">
              Combustível
            </label>
            <select
              id="fuel-mobile-select"
              value={productId}
              onChange={e => setProductId(e.target.value)}
            >
              {manifest.products.map(p => (
                <option key={p.id} value={p.id}>
                  {p.label} (R$/{unitLabel(p.unit)})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="control-deck-right">
          <div className="global-search" ref={searchBoxRef}>
            <Search size={16} />
            <input
              ref={searchInputRef}
              type="text"
              aria-label="Buscar estado ou município"
              aria-controls="global-location-results"
              aria-expanded={searching}
              placeholder="Buscar UF ou município… ( / )"
              value={query}
              onFocus={() => setSearching(true)}
              onChange={e => {
                setQuery(e.target.value);
                setSearching(true);
              }}
              onKeyDown={e => {
                if (e.key === 'Escape') setSearching(false);
                if (e.key === 'ArrowDown') {
                  e.preventDefault();
                  searchBoxRef.current
                    ?.querySelector<HTMLButtonElement>('.search-dropdown button')
                    ?.focus();
                }
                if (e.key === 'Enter' && searchResults[0]) {
                  applySelection(searchResults[0].selection);
                }
              }}
            />
            {query && (
              <button
                type="button"
                className="clear-btn"
                aria-label="Limpar busca"
                onClick={() => setQuery('')}
              >
                <X size={14} />
              </button>
            )}

            {searching && (
              <div id="global-location-results" className="search-dropdown">
                <div className="search-dropdown-head">
                  <span className="eyebrow">
                    {query ? 'LOCAIS ENCONTRADOS' : 'ACESSO RÁPIDO · ESTADOS'}
                  </span>
                  <span>Semana {week + 1}</span>
                </div>
                {searchResults.length ? (
                  <div className="search-dropdown-list">
                    {searchResults.map(item => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => applySelection(item.selection)}
                      >
                        <MapPin size={15} />
                        <span className="search-item-main">
                          <strong>{item.name}</strong>
                          <small>{item.meta}</small>
                        </span>
                        <span className="search-item-stat">
                          {item.price !== undefined ? (
                            <>
                              <b>{money(item.price)}</b>
                              <small>{count(item.stations || 0)} postos</small>
                            </>
                          ) : (
                            <small className="muted">Sem coleta</small>
                          )}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="search-empty">
                    Nenhum estado ou município observado corresponde a “{query}”.
                  </p>
                )}
                <div className="search-dropdown-foot">
                  Cobertura histórica: 27 UFs e 462 municípios pesquisados pela ANP.
                </div>
              </div>
            )}
          </div>

          <div className="metric-toggle" role="group" aria-label="Modo de cor do mapa">
            <button
              type="button"
              aria-pressed={metric === 'price'}
              onClick={() => setMetric('price')}
            >
              Preço mediano
            </button>
            <button
              type="button"
              aria-pressed={metric === 'comparison'}
              onClick={() => setMetric('comparison')}
            >
              Desvio (%)
            </button>
          </div>
        </div>
      </section>

      {/* Main Analytical Workspace: Inspector + Map */}
      <main className="workspace" aria-busy={loading}>
        <aside className="inspector" aria-label="Painel analítico do recorte selecionado">
          {/* Breadcrumbs & Scope Header */}
          <div className="scope-topbar">
            <nav className="breadcrumbs" aria-label="Nível geográfico">
              <button
                type="button"
                className={!selection.uf ? 'current' : ''}
                onClick={() => applySelection({})}
              >
                Brasil
              </button>
              {stateMeta && (
                <>
                  <ChevronRight size={13} />
                  <button
                    type="button"
                    className={selection.uf && !selection.city ? 'current' : ''}
                    onClick={() => applySelection({ uf: stateMeta.uf })}
                  >
                    {stateMeta.uf}
                  </button>
                </>
              )}
              {cityMeta && (
                <>
                  <ChevronRight size={13} />
                  <span className="current">{cityMeta.name}</span>
                </>
              )}
            </nav>

            {selection.uf && (
              <button
                type="button"
                className="reset-scope-btn"
                onClick={() => applySelection({})}
                title="Voltar ao panorama nacional"
              >
                <RotateCcw size={13} />
                <span>Brasil</span>
              </button>
            )}
          </div>

          <div className="scope-heading">
            <div>
              <span className="eyebrow accent">
                {cityMeta
                  ? `VISÃO MUNICIPAL · ${stateMeta?.name.toUpperCase()}`
                  : stateMeta
                    ? `VISÃO ESTADUAL · REGIÃO ${stateMeta.region.toUpperCase()}`
                    : 'PANORAMA NACIONAL · SÉRIE ANP'}
              </span>
              <h1>{regionName}</h1>
            </div>
            <span className="unit-pill">
              R$ / {unitLabel(product?.unit || 'litro')}
            </span>
          </div>

          {error && (
            <div className="alert-banner error" role="alert">
              <span>{error}</span>
              <button type="button" onClick={() => setRetry(v => v + 1)}>
                Tentar novamente
              </button>
            </div>
          )}

          {loading || !dataIsCurrent ? (
            <div className="panel-loading" role="status">
              <span className="spinner" />
              <span>Carregando recorte de {product?.label.toLowerCase()}…</span>
            </div>
          ) : (
            <>
              {/* Hero Price & Coverage Card */}
              <div className="kpi-hero-card">
                <div className="kpi-hero-top">
                  <span className="kpi-caption">
                    Mediana semanal · {product?.label}
                  </span>
                  <span className="kpi-week-tag">
                    {date(manifest.weeks[week], { day: '2-digit', month: 'short', year: 'numeric' })}
                  </span>
                </div>

                <div className="kpi-main-price">
                  {currentRow ? (
                    <>
                      <PriceTicker value={currentRow.p} />
                      <small>/ {unitLabel(product!.unit)}</small>
                    </>
                  ) : (
                    <span className="no-price">—</span>
                  )}
                </div>

                {selection.uf ? (
                  delta !== undefined ? (
                    <div
                      className={`delta-banner ${delta > 0.05 ? 'up' : delta < -0.05 ? 'down' : 'neutral'}`}
                    >
                      {delta > 0.05 ? (
                        <ArrowUpRight size={16} />
                      ) : delta < -0.05 ? (
                        <ArrowDownRight size={16} />
                      ) : (
                        <ArrowRight size={16} />
                      )}
                      <strong>
                        {Math.abs(delta).toFixed(1).replace('.', ',')}%{' '}
                        {delta > 0.05 ? 'acima' : delta < -0.05 ? 'abaixo' : 'em linha'}
                      </strong>
                      <span>
                        da mediana {referenceLabel} ({money(referenceValue!)})
                      </span>
                    </div>
                  ) : (
                    <div className="delta-banner warning">
                      <Info size={15} />
                      <span>
                        {currentRow
                          ? selection.city
                            ? 'Base insuficiente (< 3 postos ou UF sem referência)'
                            : 'Base insuficiente na UF (< 10 postos na semana)'
                          : 'Sem coleta registrada neste combustível e semana'}
                      </span>
                    </div>
                  )
                ) : (
                  <div className="delta-banner neutral">
                    <span>
                      Mediana nacional com peso 1 por posto observado na semana
                    </span>
                  </div>
                )}

                <div className="kpi-metrics-grid">
                  <div>
                    <span>Postos na semana</span>
                    <strong>{currentRow ? count(currentRow.n) : '—'}</strong>
                  </div>
                  <div>
                    <span>Coletas aceitas</span>
                    <strong>{currentRow ? count(currentRow.c) : '—'}</strong>
                  </div>
                  <div>
                    <span>
                      {selection.uf ? 'Postos no mapa' : 'UFs c/ coleta'}
                    </span>
                    <strong>
                      {selection.uf
                        ? loadingStations
                          ? '…'
                          : count(activeStations.length)
                        : `${states.length}/27`}
                    </strong>
                  </div>
                </div>

                {currentRow && (
                  <SpreadBar
                    lo={currentRow.lo}
                    median={currentRow.p}
                    hi={currentRow.hi}
                    reference={referenceValue}
                    referenceLabel={referenceLabel}
                  />
                )}
              </div>

              {/* Focused Station Card (when a map pin or station list item is selected) */}
              {focusedFeature && (
                <div className="focused-station-card">
                  <div className="focused-station-head">
                    <div>
                      <span className="eyebrow accent">POSTO EM FOCO · SÉRIE PRÓPRIA</span>
                      <strong>{focusedFeature.properties.name}</strong>
                    </div>
                    <button
                      type="button"
                      className="icon-btn small"
                      aria-label="Desfazer seleção de posto"
                      onClick={() => setFocusedStationKey(null)}
                    >
                      <X size={15} />
                    </button>
                  </div>
                  <div className="focused-station-meta">
                    {focusedFeature.properties.distributor && (
                      <span className="brand-tag">{focusedFeature.properties.distributor}</span>
                    )}
                    <span>
                      {[focusedFeature.properties.neighborhood, focusedFeature.properties.municipality]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </div>
                  <div className="focused-station-price">
                    {focusedActiveStation ? (
                      <>
                        <b>
                          {money(focusedActiveStation.price)} / {unitLabel(product!.unit)}
                        </b>
                        <span>
                          {count(focusedActiveStation.collections)}{' '}
                          {focusedActiveStation.collections === 1 ? 'coleta' : 'coletas'} na semana
                        </span>
                        {focusedActiveStation.deltaPercent !== undefined && (
                          <em
                            className={
                              focusedActiveStation.deltaPercent > 0
                                ? 'up'
                                : focusedActiveStation.deltaPercent < 0
                                  ? 'down'
                                  : ''
                            }
                          >
                            {signedPercent(focusedActiveStation.deltaPercent)} vs. UF
                          </em>
                        )}
                      </>
                    ) : (
                      <span className="muted">Sem coleta para este posto na semana selecionada</span>
                    )}
                  </div>
                </div>
              )}

              {/* Historical Evolution Chart */}
              <TrendChart
                rows={primaryChartRows}
                referenceRows={refChartRows}
                referenceLabel={refChartLabel}
                primaryLabel={primaryChartLabel}
                unit={product!.unit}
                week={week}
                weeks={manifest.weeks}
                windowMode={chartWindow}
                onWindowChange={setChartWindow}
                onSelectWeek={w => {
                  setPlaying(false);
                  setWeek(w);
                }}
              />

              {/* Directory Explorer: UFs / Municípios / Postos */}
              <section className="explorer-card" aria-label="Listagem comparativa">
                {selection.uf ? (
                  <div className="explorer-tabs" role="tablist" aria-label="Alternar municípios e postos">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={explorerTab === 'regions'}
                      className={explorerTab === 'regions' ? 'active' : ''}
                      onClick={() => {
                        setExplorerTab('regions');
                        setListFilter('');
                      }}
                    >
                      <Building2 size={14} />
                      <span>Municípios ({visibleCities.length})</span>
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={explorerTab === 'stations'}
                      className={explorerTab === 'stations' ? 'active' : ''}
                      onClick={() => {
                        setExplorerTab('stations');
                        setListFilter('');
                      }}
                    >
                      <Store size={14} />
                      <span>
                        Postos ({loadingStations ? '…' : count(activeStations.length)})
                      </span>
                    </button>
                  </div>
                ) : (
                  <div className="explorer-header-single">
                    <div>
                      <span className="eyebrow">COMPARAÇÃO ESTADUAL</span>
                      <h3>Unidades da Federação ({filteredRegions.length})</h3>
                    </div>
                  </div>
                )}

                {!selection.uf && (
                  <div className="region-chips" role="group" aria-label="Filtrar macrorregião">
                    {REGIONS.map(reg => (
                      <button
                        key={reg}
                        type="button"
                        aria-pressed={regionFilter === reg}
                        className={regionFilter === reg ? 'active' : ''}
                        onClick={() => setRegionFilter(reg)}
                      >
                        {reg}
                      </button>
                    ))}
                  </div>
                )}

                <div className="explorer-toolbar">
                  <div className="mini-search">
                    <Search size={14} />
                    <input
                      type="text"
                      aria-label="Filtrar itens da lista"
                      placeholder={
                        selection.uf && explorerTab === 'stations'
                          ? 'Filtrar posto, bandeira ou bairro…'
                          : selection.uf
                            ? 'Filtrar município da UF…'
                            : 'Filtrar estado…'
                      }
                      value={listFilter}
                      onChange={e => setListFilter(e.target.value)}
                    />
                    {listFilter && (
                      <button
                        type="button"
                        className="clear-btn"
                        aria-label="Limpar filtro da lista"
                        onClick={() => setListFilter('')}
                      >
                        <X size={12} />
                      </button>
                    )}
                  </div>

                  <label className="sr-only" htmlFor="explorer-sort">
                    Ordenar lista
                  </label>
                  <select
                    id="explorer-sort"
                    className="mini-select"
                    value={sort}
                    onChange={e => setSort(e.target.value as SortMode)}
                  >
                    <option value="low">Menor preço</option>
                    <option value="high">Maior preço</option>
                    <option value="coverage">
                      {selection.uf && explorerTab === 'stations' ? 'Mais coletas' : 'Mais postos'}
                    </option>
                  </select>
                </div>

                {/* Tab Content: Regions (UFs or Cities) */}
                {(!selection.uf || explorerTab === 'regions') && (
                  <div className="explorer-list">
                    {filteredRegions.length ? (
                      filteredRegions.map((row, idx) => {
                        const isCity = 'id' in row;
                        const item = isCity
                          ? manifest.cities.find(c => c.id === row.id)
                          : manifest.states.find(s => s.uf === (row as StateRow).uf);
                        if (!item) return null;

                        const isSelected = isCity && selection.city === item.id;
                        const rowRef = isCity ? (row as CityRow).ref : national?.p;
                        const rowDelta =
                          row.eligible && rowRef ? (row.p / rowRef - 1) * 100 : undefined;
                        const barRatio =
                          range[1] > range[0] && metric === 'price'
                            ? Math.max(8, ((row.p - range[0]) / (range[1] - range[0])) * 100)
                            : 50;

                        return (
                          <button
                            key={isCity ? item.id : item.uf}
                            type="button"
                            className={`explorer-row ${isSelected ? 'selected' : ''}`}
                            onClick={() =>
                              isCity
                                ? applySelection(
                                    selection.city === item.id
                                      ? { uf: item.uf }
                                      : { uf: item.uf, city: item.id },
                                  )
                                : applySelection({ uf: item.uf })
                            }
                          >
                            <span className="row-rank">
                              {String(idx + 1).padStart(2, '0')}
                            </span>
                            <span className="row-info">
                              <span className="row-title">
                                <strong>{item.name}</strong>
                                {!isCity && <em className="uf-code">{item.uf}</em>}
                              </span>
                              <span className="row-sub">
                                {count(row.n)} {row.n === 1 ? 'posto' : 'postos'}
                                {!row.eligible && ' · base limitada'}
                              </span>
                              {metric === 'price' && (
                                <span className="row-bar-track">
                                  <span
                                    className="row-bar-fill"
                                    style={{
                                      width: `${barRatio}%`,
                                      background: priceColor(row.p, ...range, 'price'),
                                    }}
                                  />
                                </span>
                              )}
                            </span>
                            <span className="row-price-col">
                              <b>{money(row.p)}</b>
                              {rowDelta !== undefined && (
                                <small
                                  className={
                                    rowDelta > 0.05 ? 'up' : rowDelta < -0.05 ? 'down' : ''
                                  }
                                >
                                  {signedPercent(rowDelta)}
                                </small>
                              )}
                            </span>
                            <ChevronRight size={15} className="row-chevron" />
                          </button>
                        );
                      })
                    ) : (
                      <p className="explorer-empty">
                        Nenhum local com coleta corresponde ao filtro atual.
                      </p>
                    )}
                  </div>
                )}

                {/* Tab Content: Individual Mapped Stations */}
                {selection.uf && explorerTab === 'stations' && (
                  <>
                    {selection.city && cityMeta && (
                      <div className="city-filter-chip">
                        <span>
                          Filtrado por <strong>{cityMeta.name}</strong>
                        </span>
                        <button
                          type="button"
                          onClick={() => applySelection({ uf: selection.uf })}
                        >
                          Ver toda a UF ({selection.uf})
                        </button>
                      </div>
                    )}

                    <div className="explorer-list stations-mode">
                      {loadingStations ? (
                        <p className="explorer-empty">
                          <span className="spinner" /> Carregando postos localizados em{' '}
                          {selection.uf}…
                        </p>
                      ) : stationError ? (
                        <p className="explorer-empty">
                          Não foi possível carregar o arquivo de postos desta UF.
                        </p>
                      ) : displayedStations.length ? (
                        <>
                          {displayedStations.map(st => {
                            const active = focusedStationKey === st.key;
                            return (
                              <button
                                key={st.key}
                                type="button"
                                className={`explorer-row station-row ${active ? 'selected' : ''}`}
                                onClick={() => {
                                  if (!showStations) setShowStations(true);
                                  setFocusedStationKey(active ? null : st.key);
                                }}
                              >
                                <span
                                  className="station-color-dot"
                                  style={{ background: st.color }}
                                />
                                <span className="row-info">
                                  <strong className="station-row-name">
                                    {st.properties.name}
                                  </strong>
                                  <span className="row-sub">
                                    {st.properties.distributor || 'Bandeira não informada'} ·{' '}
                                    {[st.properties.neighborhood, st.properties.municipality]
                                      .filter(Boolean)
                                      .join(', ')}
                                  </span>
                                </span>
                                <span className="row-price-col">
                                  <b>{money(st.price)}</b>
                                  {st.deltaPercent !== undefined ? (
                                    <small
                                      className={
                                        st.deltaPercent > 0.05
                                          ? 'up'
                                          : st.deltaPercent < -0.05
                                            ? 'down'
                                            : ''
                                      }
                                    >
                                      {signedPercent(st.deltaPercent)}
                                    </small>
                                  ) : (
                                    <small>{st.collections} col.</small>
                                  )}
                                </span>
                              </button>
                            );
                          })}
                          {!showAllStations && filteredStations.length > 80 && (
                            <button
                              type="button"
                              className="load-more-btn"
                              onClick={() => setShowAllStations(true)}
                            >
                              Mostrar todos os {count(filteredStations.length)} postos
                            </button>
                          )}
                        </>
                      ) : (
                        <p className="explorer-empty">
                          Nenhum posto com coordenada elegível encontrado neste recorte e semana.
                        </p>
                      )}
                    </div>

                    {manifest.stationLayer && (
                      <p className="station-Registry-note">
                        Cadastro ANP de {date(manifest.stationLayer.snapshotAt)} · coordenadas marcadas
                        pela ANP como não validadas; postos sem coordenada compatível não entram como pontos.
                      </p>
                    )}
                  </>
                )}
              </section>
            </>
          )}
        </aside>

        {/* Interactive Map Stage */}
        <div className="map-viewport">
          {data && dataIsCurrent ? (
            <AtlasMap
              manifest={manifest}
              states={states}
              cities={cities}
              activeStations={activeStations}
              loadingStations={loadingStations}
              stationError={stationError}
              showStations={showStations}
              onToggleStations={() => setShowStations(s => !s)}
              focusedStationKey={focusedStationKey}
              onFocusStation={setFocusedStationKey}
              selection={selection}
              metric={metric}
              national={national?.p}
              range={range}
              unit={product!.unit}
              productLabel={product!.label}
              weekIso={manifest.weeks[week]}
              onSelect={applySelection}
            />
          ) : (
            <div className="map-skeleton">
              <span className="spinner" />
              <span>Preparando camada geográfica…</span>
            </div>
          )}
          {loading && <div className="map-loading-veil" />}
        </div>
      </main>

      {/* Temporal Scrubber & Playback Bar */}
      <section className="timeline-deck" aria-label="Linha do tempo semanal (2024 a 2026)">
        <div className="timeline-meta">
          <div className="timeline-title-row">
            <span className="eyebrow accent">
              SEMANA {week + 1} DE {manifest.weeks.length}
            </span>
            {isPartialLastWeek && (
              <span className="partial-badge">
                <AlertTriangle size={12} /> Parcial (2 dias: 29–30/06)
              </span>
            )}
          </div>
          <strong className="timeline-range-text">
            {weekLabel(manifest.weeks[week], manifest.dataset.periodEnd)}
          </strong>
        </div>

        <div className="timeline-controls">
          <div className="transport-btns">
            <button
              type="button"
              className="transport-btn play"
              aria-label={playing ? 'Pausar animação semanal' : 'Reproduzir evolução semanal'}
              title={playing ? 'Pausar' : 'Reproduzir evolução'}
              onClick={() => {
                if (!playing && week >= manifest.weeks.length - 1) {
                  setWeek(Math.max(0, manifest.weeks.length - 26));
                }
                setPlaying(p => !p);
              }}
            >
              {playing ? <Pause size={15} /> : <Play size={15} />}
            </button>
            <button
              type="button"
              className="transport-btn"
              aria-label="Semana anterior"
              disabled={week === 0}
              onClick={() => {
                setPlaying(false);
                setWeek(w => Math.max(0, w - 1));
              }}
            >
              <ChevronLeft size={17} />
            </button>
            <button
              type="button"
              className="transport-btn"
              aria-label="Próxima semana"
              disabled={week === manifest.weeks.length - 1}
              onClick={() => {
                setPlaying(false);
                setWeek(w => Math.min(manifest.weeks.length - 1, w + 1));
              }}
            >
              <ChevronRight size={17} />
            </button>
          </div>

          <div className="scrubber-col">
            <label className="sr-only" htmlFor="week-slider">
              Selecionar semana do histórico
            </label>
            <input
              id="week-slider"
              type="range"
              min={0}
              max={manifest.weeks.length - 1}
              value={week}
              aria-valuetext={weekLabel(manifest.weeks[week], manifest.dataset.periodEnd)}
              onChange={e => {
                setPlaying(false);
                setWeek(Number(e.target.value));
              }}
            />
            <div className="scrubber-ticks">
              <span>JAN 2024</span>
              <span>JUL 2024</span>
              <span>JAN 2025</span>
              <span>JUL 2025</span>
              <span>JAN 2026</span>
              <span>JUN 2026</span>
            </div>
          </div>
        </div>

        <div className="semester-jumps" role="group" aria-label="Atalhos de semestre">
          {milestones.map(m => {
            const isActive =
              m.id === 'latest'
                ? week === m.weekIndex
                : week >= m.weekIndex &&
                  week <
                    (milestones[milestones.indexOf(m) + 1]?.weekIndex ?? manifest.weeks.length);
            return (
              <button
                key={m.id}
                type="button"
                className={`jump-pill ${isActive ? 'active' : ''}`}
                onClick={() => {
                  setPlaying(false);
                  setWeek(m.weekIndex);
                }}
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* Clean Analytical Footer */}
      <footer className="atlas-footer">
        <div className="footer-left">
          <strong>Fuel Watch BR</strong>
          <span>·</span>
          <span>
            {count(manifest.dataset.observations)} coletas aceitas ·{' '}
            {count(manifest.dataset.stations)} postos · {manifest.dataset.municipalities} municípios
          </span>
        </div>
        <div className="footer-right">
          <span>Dados históricos nominais (ANP / IBGE) · Não são preços em tempo real</span>
          <button type="button" className="text-btn" onClick={() => setMethodology(true)}>
            Ver reconciliação Fabric →
          </button>
        </div>
      </footer>

      {methodology && (
        <MethodologyModal manifest={manifest} onClose={() => setMethodology(false)} />
      )}
    </div>
  );
}

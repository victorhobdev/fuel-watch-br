import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useReducedMotion } from 'motion/react';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Crosshair,
  Database,
  ExternalLink,
  Filter,
  Fuel,
  Info,
  Map as MapIcon,
  MapPin,
  Menu,
  Navigation,
  Pause,
  Play,
  Search,
  ShieldCheck,
  Store,
  Table,
  TrendingUp,
  X,
} from 'lucide-react';
import AtlasMap from './AtlasMap';
import DistributorBadge from './DistributorBadge';
import FiltersModal from './FiltersModal';
import MethodologyModal from './MethodologyModal';
import RegionalDataView from './RegionalDataView';
import TrendChart from './TrendChart';
import TrendsView from './TrendsView';
import {
  count,
  date,
  distributorVisual,
  formatSuburbLine,
  getData,
  isInViewport,
  money,
  normalize,
  priceColor,
  priceDigits,
  sanitizeStreet,
  semesterMilestones,
  shortFuelName,
  signedPercent,
  stationId,
  unitLabel,
  weekCompactLabel,
  weekLabel,
  type ActiveStation,
  type AppView,
  type ChartWindow,
  type CityRow,
  type ExplorerTab,
  type Manifest,
  type Metric,
  type Observation,
  type ProductData,
  type Selection,
  type SortMode,
  type StationFeature,
  type StationFile,
  type ViewportBounds,
} from './data';

function FuelWatchLogo({ onClick }: { onClick: () => void }) {
  return (
    <a
      href={import.meta.env.BASE_URL}
      className="wa-logo"
      aria-label="FuelWatch BR — voltar ao mapa do Brasil"
      onClick={e => {
        e.preventDefault();
        onClick();
      }}
    >
      <span className="wa-logo-icon" aria-hidden="true">
        <svg viewBox="0 0 38 38" fill="none">
          <rect width="38" height="38" rx="10" fill="#4B287D" />
          <path
            d="M10.5 11C10.5 9.61929 11.6193 8.5 13 8.5H21.5C22.8807 8.5 24 9.61929 24 11V29H10.5V11Z"
            fill="#FFFFFF"
          />
          <rect x="13" y="11" width="8.5" height="6" rx="1.5" fill="#00797B" />
          <path
            d="M24 14.5H26.5C27.8807 14.5 29 15.6193 29 17V23.5C29 24.8807 27.8807 26 26.5 26C25.1193 26 24 24.8807 24 23.5V14.5Z"
            stroke="#5EEAD4"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <path d="M8.5 29H26" stroke="#FFFFFF" strokeWidth="2.4" strokeLinecap="round" />
          <circle cx="17.25" cy="22.8" r="2.4" fill="#C8102E" />
        </svg>
      </span>
      <span className="wa-logo-wordmark">
        <span className="wa-word-fuel">Fuel</span>
        <span className="wa-word-watch">Watch</span>
        <small className="wa-word-br">BR</small>
      </span>
    </a>
  );
}

export default function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [data, setData] = useState<ProductData | null>(null);
  const [productId, setProductId] = useState('gasolina');
  const [week, setWeek] = useState(129); // Última semana ISO completa por padrão; parcial (130) segue selecionável.
  const [playing, setPlaying] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(false);

  const [view, setView] = useState<AppView>('map');
  const [sidenavOpen, setSidenavOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [fuelMenuOpen, setFuelMenuOpen] = useState(false);
  const [methodologyOpen, setMethodologyOpen] = useState(false);

  const [selection, setSelection] = useState<Selection>({});
  const [focusedStationKey, setFocusedStationKey] = useState<string | null>(null);
  const [showStations, setShowStations] = useState(true);
  const [strictCityOnly, setStrictCityOnly] = useState(false);

  const [metric, setMetric] = useState<Metric>('price');
  const [explorerTab, setExplorerTab] = useState<ExplorerTab>('stations');
  const [sort, setSort] = useState<SortMode>('low');
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [listFilter, setListFilter] = useState('');
  const [showAllStations, setShowAllStations] = useState(false);
  const [chartWindow, setChartWindow] = useState<ChartWindow>('26w');

  const [viewportBounds, setViewportBounds] = useState<ViewportBounds | null>(null);
  const [reframeToken, setReframeToken] = useState(0);

  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  const [stationFile, setStationFile] = useState<StationFile | null>(null);
  const [loadingStations, setLoadingStations] = useState(false);
  const [stationError, setStationError] = useState(false);

  const searchPillRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const fuelDropdownRef = useRef<HTMLDivElement>(null);
  const sidebarScrollRef = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();

  // 1. Load Manifest
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
          setError(
            'Não foi possível carregar o manifesto de dados. Verifique sua conexão e tente novamente.',
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [retry]);

  // 2. Load Product Regional Slice
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
          setError('Não foi possível abrir os dados deste combustível. Tente novamente.');
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [manifest, productId, retry]);

  // 3. Strict Lazy Load of Station GeoJSON: ZERO requests at Brasil level; loads only when a UF is selected
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

  // 4. Outside clicks & '/' shortcut
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!searchPillRef.current?.contains(target)) {
        setSearching(false);
      }
      if (!fuelDropdownRef.current?.contains(target)) {
        setFuelMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (event.key === '/' && tag !== 'INPUT' && tag !== 'SELECT' && tag !== 'TEXTAREA') {
        event.preventDefault();
        searchInputRef.current?.focus();
        setSearching(true);
      }
      if (event.key === 'Escape') {
        setSearching(false);
        setFuelMenuOpen(false);
        setSidenavOpen(false);
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  // 5. Historical Timeline Playback
  useEffect(() => {
    if (!playing || !manifest) return;
    const maxWeek = manifest.weeks.length - 1;
    const timer = window.setInterval(
      () => {
        setWeek(prev => {
          if (prev >= maxWeek) {
            setPlaying(false);
            return maxWeek;
          }
          return prev + 1;
        });
      },
      reducedMotion ? 750 : 420,
    );
    return () => window.clearInterval(timer);
  }, [playing, manifest, reducedMotion]);

  // Scroll sidebar to top when switching focus or UF
  useEffect(() => {
    sidebarScrollRef.current?.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [focusedStationKey, selection.uf, selection.city, explorerTab]);

  const applySelection = useCallback((next: Selection, focusKey: string | null = null) => {
    setSelection(next);
    setFocusedStationKey(focusKey);
    setStrictCityOnly(false);
    setSearching(false);
    setQuery('');
    setListFilter('');
    setShowAllStations(false);
    setExplorerTab('stations');
  }, []);

  const handleViewportChange = useCallback((bounds: ViewportBounds) => {
    setViewportBounds(bounds);
  }, []);

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
  const cityRow = useMemo(
    () => (selection.city ? cities.find(r => r.id === selection.city) : undefined),
    [cities, selection.city],
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

  // Available distributors in current UF & week (for FiltersModal)
  const availableBrands = useMemo(() => {
    if (!selection.uf || !stationFile) return [];
    const tally = new Map<string, number>();
    for (const feature of stationFile.features) {
      const hasWeek = feature.properties.prices.some(entry => entry[0] === week);
      if (!hasWeek) continue;
      const brand = (feature.properties.distributor || 'BANDEIRA BRANCA').trim();
      tally.set(brand, (tally.get(brand) || 0) + 1);
    }
    return Array.from(tally.entries())
      .map(([name, cnt]) => ({ name, count: cnt }))
      .sort((a, b) => b.count - a.count);
  }, [selection.uf, stationFile, week]);

  // All active stations in the loaded UF for the selected week & brand filter
  const activeStations = useMemo<ActiveStation[]>(() => {
    if (!selection.uf || !stationFile) return [];
    const brandSet =
      selectedBrands.length > 0
        ? new Set(selectedBrands.map(b => b.trim().toUpperCase()))
        : null;

    const result: ActiveStation[] = [];
    for (const feature of stationFile.features) {
      if (strictCityOnly && selection.city && feature.properties.municipalityId !== selection.city) {
        continue;
      }
      const rawBrand = (feature.properties.distributor || 'BANDEIRA BRANCA').trim().toUpperCase();
      if (brandSet && !brandSet.has(rawBrand)) continue;

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
  }, [
    selection.uf,
    selection.city,
    strictCityOnly,
    stationFile,
    selectedBrands,
    week,
    stateRow,
    range,
    metric,
  ]);

  // Stations synchronized with current map viewport bounds
  const viewportStations = useMemo(() => {
    if (!selection.uf) return [];
    const inView = activeStations.filter(s => isInViewport(s.lon, s.lat, viewportBounds));
    // If camera is mid-flight to a newly chosen city and bounds haven't caught up yet, show city stations cleanly
    if (inView.length === 0 && selection.city) {
      const cityFallback = activeStations.filter(
        s => s.properties.municipalityId === selection.city,
      );
      if (cityFallback.length > 0) return cityFallback;
    }
    const q = normalize(listFilter.trim());
    const textFiltered = q
      ? inView.filter(st => {
          const p = st.properties;
          return normalize(
            `${p.name} ${p.distributor} ${p.neighborhood} ${p.municipality} ${p.address} ${p.cep}`,
          ).includes(q);
        })
      : inView;

    return textFiltered.sort((a, b) =>
      sort === 'low'
        ? a.price - b.price
        : sort === 'high'
          ? b.price - a.price
          : b.collections - a.collections,
    );
  }, [selection.uf, selection.city, activeStations, viewportBounds, listFilter, sort]);

  const minStationPriceInList = useMemo(
    () => (viewportStations.length ? Math.min(...viewportStations.map(s => s.price)) : undefined),
    [viewportStations],
  );

  // Sorted States (at Brasil level) or Municipalities (inside UF when Municípios tab is chosen)
  const sortedStates = useMemo(() => {
    if (!manifest) return [];
    const q = normalize(listFilter.trim());
    return states
      .filter(row => {
        const st = manifest.states.find(s => s.uf === row.uf);
        if (!st) return false;
        if (q && !normalize(`${st.name} ${st.uf} ${st.region}`).includes(q)) return false;
        return true;
      })
      .sort((a, b) =>
        sort === 'low' ? a.p - b.p : sort === 'high' ? b.p - a.p : b.n - a.n,
      );
  }, [manifest, states, listFilter, sort]);

  const minStatePrice = useMemo(
    () => (sortedStates.length ? Math.min(...sortedStates.map(s => s.p)) : undefined),
    [sortedStates],
  );

  const sortedUfCities = useMemo(() => {
    const q = normalize(listFilter.trim());
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
  }, [visibleCities, cityById, listFilter, sort]);

  const minCityPrice = useMemo(
    () => (sortedUfCities.length ? Math.min(...sortedUfCities.map(c => c.p)) : undefined),
    [sortedUfCities],
  );

  // Focused Station Detail Data
  const focusedFeature = useMemo<StationFeature | undefined>(() => {
    if (!focusedStationKey || !stationFile) return undefined;
    return stationFile.features.find(f => stationId(f) === focusedStationKey);
  }, [focusedStationKey, stationFile]);

  const focusedActiveStation = useMemo(
    () => activeStations.find(s => s.key === focusedStationKey),
    [activeStations, focusedStationKey],
  );

  const focusedStationSeries = useMemo<Observation[]>(() => {
    if (!focusedFeature) return [];
    return focusedFeature.properties.prices.map(([wIdx, mills, colls]) => ({
      w: wIdx,
      p: mills / 1000,
      n: 1,
      c: colls,
      lo: mills / 1000,
      hi: mills / 1000,
      eligible: true,
    }));
  }, [focusedFeature]);

  const focusedUfSeries = useMemo(
    () => (data && selection.uf ? data.states.filter(r => r.uf === selection.uf) : undefined),
    [data, selection.uf],
  );

  const focusedCityRow = useMemo(() => {
    if (!focusedFeature) return undefined;
    return cities.find(c => c.id === focusedFeature.properties.municipalityId);
  }, [focusedFeature, cities]);

  // Unified Header Search Results (States + 462 Cities + Loaded UF Stations/Suburbs/CEP)
  const searchResults = useMemo(() => {
    if (!manifest) return [];
    const q = normalize(query.trim());

    const matchedStates = manifest.states
      .filter(s => normalize(`${s.name} ${s.uf} ${s.region}`).includes(q))
      .map(s => {
        const row = states.find(r => r.uf === s.uf);
        return {
          key: `uf-${s.uf}`,
          kind: 'uf' as const,
          name: s.name,
          meta: `Estado (${s.uf}) · ${s.region}`,
          price: row?.p,
          substat: row ? `${count(row.n)} postos` : 'Sem coleta',
          onPick: () => {
            setView('map');
            applySelection({ uf: s.uf });
          },
        };
      });

    const matchedCities =
      q.length >= 2
        ? manifest.cities
            .filter(c => normalize(`${c.name} ${c.uf}`).includes(q))
            .slice(0, 8)
            .map(c => {
              const row = cities.find(r => r.id === c.id);
              return {
                key: `city-${c.id}`,
                kind: 'city' as const,
                name: c.name,
                meta: `Município · ${c.uf}`,
                price: row?.p,
                substat: row ? `${count(row.n)} postos` : 'Sem coleta',
                onPick: () => {
                  setView('map');
                  applySelection({ uf: c.uf, city: c.id });
                },
              };
            })
        : [];

    const matchedStations =
      q.length >= 3 && selection.uf && activeStations.length > 0
        ? activeStations
            .filter(st => {
              const p = st.properties;
              return normalize(
                `${p.name} ${p.neighborhood} ${p.address} ${p.cep} ${p.distributor}`,
              ).includes(q);
            })
            .sort((a, b) => a.price - b.price)
            .slice(0, 5)
            .map(st => ({
              key: `st-${st.key}`,
              kind: 'station' as const,
              name: st.properties.name,
              meta: `${st.properties.neighborhood || st.properties.municipality} · ${st.properties.uf}`,
              price: st.price,
              substat: distributorVisual(st.properties.distributor).label,
              onPick: () => {
                setView('map');
                setSearching(false);
                setQuery('');
                setFocusedStationKey(st.key);
              },
            }))
        : [];

    return [...matchedStates.slice(0, 5), ...matchedCities, ...matchedStations].slice(0, 10);
  }, [manifest, query, states, cities, selection.uf, activeStations, applySelection]);

  const milestones = useMemo(
    () => (manifest ? semesterMilestones(manifest.weeks) : []),
    [manifest],
  );

  if (!manifest) {
    return (
      <div className="wa-boot-screen">
        <div className="wa-boot-card">
          <FuelWatchLogo onClick={() => {}} />
          {error ? (
            <div className="wa-boot-error" role="alert">
              <p>{error}</p>
              <button
                type="button"
                className="wa-btn-primary"
                onClick={() => setRetry(v => v + 1)}
              >
                Tentar novamente
              </button>
            </div>
          ) : (
            <p className="wa-boot-status" role="status">
              <span className="spinner-sm" /> Carregando dados históricos da ANP…
            </p>
          )}
        </div>
      </div>
    );
  }

  const product = manifest.products.find(p => p.id === productId) || manifest.products[0];
  const isPartialLastWeek = week === manifest.weeks.length - 1;
  const activeFilterCount =
    selectedBrands.length + (metric !== 'price' ? 1 : 0) + (sort !== 'low' ? 1 : 0);
  const displayedStations = showAllStations
    ? viewportStations
    : viewportStations.slice(0, 80);

  return (
    <div className="wa-app">
      {/* FuelWatch WA Single White Header */}
      <header className="wa-header">
        <div className="wa-header-left">
          <FuelWatchLogo
            onClick={() => {
              setView('map');
              applySelection({});
            }}
          />
        </div>

        {/* Centered Unified Search + Fuel + Filter Pill */}
        <div className="wa-header-center">
          <div className="wa-search-pill" ref={searchPillRef}>
            <div className="wa-search-input-wrap">
              <Search size={17} className="wa-search-icon" />
              <input
                ref={searchInputRef}
                type="text"
                aria-label="Buscar estado, município, bairro ou posto"
                aria-controls="wa-search-results"
                aria-expanded={searching}
                placeholder={
                  selection.uf
                    ? `Buscar cidade, bairro, CEP ou posto em ${selection.uf}…`
                    : 'Buscar estado ou município… ( / )'
                }
                value={query}
                onFocus={() => setSearching(true)}
                onChange={e => {
                  setQuery(e.target.value);
                  setSearching(true);
                }}
                onKeyDown={e => {
                  if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    searchPillRef.current
                      ?.querySelector<HTMLButtonElement>('.wa-search-dropdown button')
                      ?.focus();
                  }
                  if (e.key === 'Enter' && searchResults[0]) {
                    searchResults[0].onPick();
                  }
                }}
              />
              {query && (
                <button
                  type="button"
                  className="wa-clear-input"
                  aria-label="Limpar busca"
                  onClick={() => setQuery('')}
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Inline Fuel Selector inside Pill */}
            <div className="wa-pill-fuel-wrap" ref={fuelDropdownRef}>
              <button
                type="button"
                className="wa-pill-fuel-btn"
                aria-haspopup="listbox"
                aria-expanded={fuelMenuOpen}
                title="Trocar combustível"
                onClick={() => setFuelMenuOpen(prev => !prev)}
              >
                <Fuel size={16} />
                <span>{shortFuelName(product)}</span>
                <ChevronDown size={14} />
              </button>

              {fuelMenuOpen && (
                <div className="wa-fuel-popover" role="listbox" aria-label="Combustíveis">
                  {manifest.products.map(p => {
                    const active = p.id === productId;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        role="option"
                        aria-selected={active}
                        className={`wa-fuel-option ${active ? 'active' : ''}`}
                        onClick={() => {
                          setProductId(p.id);
                          setFuelMenuOpen(false);
                        }}
                      >
                        <span>
                          <strong>{p.label}</strong>
                          <small>R$ / {unitLabel(p.unit)}</small>
                        </span>
                        {active && <Check size={15} />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Funnel Filter Modal Trigger inside Pill */}
            <button
              type="button"
              className={`wa-pill-filter-btn ${activeFilterCount > 0 ? 'has-active' : ''}`}
              aria-label="Abrir filtros de combustível, semana e bandeiras"
              title="Filtros"
              onClick={() => setFiltersOpen(true)}
            >
              <Filter size={16} />
              {activeFilterCount > 0 && (
                <span className="wa-filter-badge">{activeFilterCount}</span>
              )}
            </button>

            {/* Search Autocomplete Dropdown */}
            {searching && (
              <div id="wa-search-results" className="wa-search-dropdown">
                <div className="wa-search-dropdown-head">
                  <span>
                    {query
                      ? 'RESULTADOS ENCONTRADOS'
                      : 'ESTADOS PESQUISADOS (27 UFS)'}
                  </span>
                  <small>
                    {shortFuelName(product)} · S{week + 1}
                  </small>
                </div>

                {searchResults.length > 0 ? (
                  <div className="wa-search-list">
                    {searchResults.map(item => (
                      <button key={item.key} type="button" onClick={item.onPick}>
                        <span className={`wa-search-kind kind-${item.kind}`}>
                          {item.kind === 'station' ? <Store size={14} /> : <MapPin size={14} />}
                        </span>
                        <span className="wa-search-main">
                          <strong>{item.name}</strong>
                          <small>{item.meta}</small>
                        </span>
                        <span className="wa-search-stat">
                          {item.price !== undefined ? (
                            <>
                              <b>{money(item.price)}</b>
                              <small>{item.substat}</small>
                            </>
                          ) : (
                            <small className="muted">{item.substat}</small>
                          )}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="wa-search-empty">
                    Nenhuma UF, município ou posto encontrado para “{query}”.
                  </p>
                )}

                <div className="wa-search-foot">
                  Base histórica auditada: 27 UFs · 462 municípios · 13.030 postos.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Header Navigation & Hamburger Drawer Trigger */}
        <div className="wa-header-right">
          <nav className="wa-header-nav" aria-label="Visões analíticas">
            <button
              type="button"
              className={`wa-nav-chip ${view === 'map' ? 'active' : ''}`}
              onClick={() => setView('map')}
            >
              <MapIcon size={15} />
              <span>Mapa</span>
            </button>
            <button
              type="button"
              className={`wa-nav-chip ${view === 'trends' ? 'active' : ''}`}
              onClick={() => setView('trends')}
            >
              <TrendingUp size={15} />
              <span>Tendências</span>
            </button>
            <button
              type="button"
              className={`wa-nav-chip ${view === 'regional' ? 'active' : ''}`}
              onClick={() => setView('regional')}
            >
              <Table size={15} />
              <span>Dados</span>
            </button>
          </nav>

          <button
            type="button"
            className="wa-fabric-pill"
            title="Auditoria e reconciliação no Microsoft Fabric"
            onClick={() => setMethodologyOpen(true)}
          >
            <ShieldCheck size={15} />
            <span>Fabric</span>
          </button>

          <button
            type="button"
            className="wa-menu-btn"
            aria-label="Abrir menu principal"
            aria-expanded={sidenavOpen}
            onClick={() => setSidenavOpen(true)}
          >
            <Menu size={21} />
          </button>
        </div>
      </header>

      {/* Subpages (Tendências / Dados) + Persistent Split Map Workspace */}
      {view === 'trends' && (
        <TrendsView
          manifest={manifest}
          data={data}
          productId={productId}
          onChangeProduct={setProductId}
          week={week}
          onChangeWeek={w => {
            setPlaying(false);
            setWeek(w);
          }}
          selection={selection}
          onSelect={next => applySelection(next)}
          windowMode={chartWindow}
          onWindowChange={setChartWindow}
          onBackToMap={() => setView('map')}
        />
      )}

      {view === 'regional' && (
        <RegionalDataView
          manifest={manifest}
          data={data}
          productId={productId}
          onChangeProduct={setProductId}
          week={week}
          onChangeWeek={w => {
            setPlaying(false);
            setWeek(w);
          }}
          onOpenOnMap={next => {
            setView('map');
            window.requestAnimationFrame(() => applySelection(next));
          }}
          onBackToMap={() => setView('map')}
        />
      )}

      <main
        className="wa-map-workspace"
        hidden={view !== 'map'}
        aria-busy={loading}
      >
          <aside className="wa-sidebar" aria-label="Lista de preços e detalhes">
            {/* Sticky Fuel & Historical Week Subheader (WA style) */}
            <div className="wa-sidebar-subheader">
              <div className="wa-week-strip">
                <div className="wa-week-strip-left">
                  <span className="wa-week-fuel">{shortFuelName(product)}</span>
                  <button
                    type="button"
                    className={`wa-week-badge ${isPartialLastWeek ? 'is-partial' : ''}`}
                    title="Abrir linha do tempo histórica (2024–2026)"
                    aria-expanded={timelineOpen}
                    onClick={() => setTimelineOpen(prev => !prev)}
                  >
                    <Calendar size={12} />
                    <span>
                      {weekCompactLabel(manifest.weeks[week], manifest.dataset.periodEnd)}
                      {isPartialLastWeek ? ' · Parcial' : ''}
                    </span>
                  </button>
                </div>

                <div className="wa-week-steppers">
                  <button
                    type="button"
                    aria-label="Semana anterior"
                    disabled={week <= 0}
                    onClick={() => {
                      setPlaying(false);
                      setWeek(w => Math.max(0, w - 1));
                    }}
                  >
                    <ChevronLeft size={15} />
                  </button>
                  <button
                    type="button"
                    aria-label="Próxima semana"
                    disabled={week >= manifest.weeks.length - 1}
                    onClick={() => {
                      setPlaying(false);
                      setWeek(w => Math.min(manifest.weeks.length - 1, w + 1));
                    }}
                  >
                    <ChevronRight size={15} />
                  </button>
                </div>
              </div>

              {/* Collapsible Inline Historical Scrubber */}
              {timelineOpen && (
                <div className="wa-inline-timeline">
                  <div className="wa-inline-timeline-top">
                    <span>
                      Semana {week + 1} de {manifest.weeks.length} ·{' '}
                      {weekLabel(manifest.weeks[week], manifest.dataset.periodEnd)}
                    </span>
                    <button
                      type="button"
                      className="wa-play-mini"
                      onClick={() => {
                        if (week >= manifest.weeks.length - 1) setWeek(0);
                        setPlaying(p => !p);
                      }}
                    >
                      {playing ? <Pause size={12} /> : <Play size={12} />}
                      <span>{playing ? 'Pausar' : 'Animar'}</span>
                    </button>
                  </div>
                  <input
                    type="range"
                    className="wa-range"
                    min={0}
                    max={manifest.weeks.length - 1}
                    value={week}
                    aria-label="Linha do tempo semanal"
                    onChange={e => {
                      setPlaying(false);
                      setWeek(Number(e.target.value));
                    }}
                  />
                  <div className="wa-mini-semesters">
                    {milestones.map(m => (
                      <button
                        key={m.id}
                        type="button"
                        className={week === m.weekIndex ? 'active' : ''}
                        onClick={() => {
                          setPlaying(false);
                          setWeek(m.weekIndex);
                        }}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Scope Breadcrumb & Postos/Municípios Switch when inside UF */}
              {selection.uf && !focusedFeature && (
                <div className="wa-scope-bar">
                  <div className="wa-breadcrumbs">
                    <button type="button" onClick={() => applySelection({})}>
                      Brasil
                    </button>
                    <ChevronRight size={12} />
                    <button
                      type="button"
                      className={!selection.city ? 'current' : ''}
                      onClick={() => applySelection({ uf: selection.uf })}
                    >
                      {selection.uf}
                    </button>
                    {cityMeta && (
                      <>
                        <ChevronRight size={12} />
                        <span className="current">{cityMeta.name}</span>
                      </>
                    )}
                  </div>

                  <div className="wa-tab-pills" role="tablist">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={explorerTab === 'stations'}
                      className={explorerTab === 'stations' ? 'active' : ''}
                      onClick={() => setExplorerTab('stations')}
                    >
                      Postos ({count(viewportStations.length)})
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={explorerTab === 'regions'}
                      className={explorerTab === 'regions' ? 'active' : ''}
                      onClick={() => setExplorerTab('regions')}
                    >
                      Cidades ({count(visibleCities.length)})
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Scrollable Body: Station Detail OR Brasil 27 UFs OR UF Viewport Stations / Cities */}
            <div className="wa-sidebar-body" ref={sidebarScrollRef}>
              {focusedFeature ? (
                /* STATE C: IN-PLACE STATION DETAIL VIEW (FuelWatch WA Pattern) */
                <div className="wa-station-detail">
                  <button
                    type="button"
                    className="wa-back-row-btn"
                    onClick={() => setFocusedStationKey(null)}
                  >
                    <ArrowLeft size={16} />
                    <span>Voltar aos resultados</span>
                  </button>

                  <div className="wa-detail-hero">
                    <div className="wa-detail-hero-text">
                      <h2>{focusedFeature.properties.name}</h2>
                      <span className="wa-detail-brand-tag">
                        {focusedFeature.properties.distributor || 'BANDEIRA BRANCA'}
                      </span>
                    </div>
                    <DistributorBadge
                      distributor={focusedFeature.properties.distributor}
                      size="lg"
                    />
                  </div>

                  <div className="wa-detail-address">
                    <MapPin size={15} />
                    <div>
                      <p>
                        {sanitizeStreet(
                          focusedFeature.properties.address,
                          focusedFeature.properties.complement,
                        ) || 'Endereço cadastral não informado'}
                      </p>
                      <small>
                        {[
                          focusedFeature.properties.neighborhood,
                          `${focusedFeature.properties.municipality} · ${focusedFeature.properties.uf}`,
                          focusedFeature.properties.cep
                            ? `CEP ${focusedFeature.properties.cep}`
                            : '',
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </small>
                    </div>
                  </div>

                  {/* Price & Comparison Cards */}
                  <div className="wa-detail-price-grid">
                    <div className="wa-detail-price-card primary">
                      <span className="eyebrow">MEDIANA NA SEMANA</span>
                      {focusedActiveStation ? (
                        <>
                          <strong
                            className={
                              minStationPriceInList !== undefined &&
                              focusedActiveStation.price <= minStationPriceInList + 0.0005
                                ? 'text-crimson'
                                : ''
                            }
                          >
                            {money(focusedActiveStation.price)}
                            <small>/{unitLabel(product.unit)}</small>
                          </strong>
                          <span>
                            {count(focusedActiveStation.collections)}{' '}
                            {focusedActiveStation.collections === 1 ? 'coleta' : 'coletas'} na semana
                          </span>
                          {minStationPriceInList !== undefined &&
                            focusedActiveStation.price <= minStationPriceInList + 0.0005 && (
                              <em className="cheapest-pill">Menor preço na área</em>
                            )}
                        </>
                      ) : (
                        <>
                          <strong className="muted-price">Sem coleta</strong>
                          <span>Posto não pesquisado nesta semana</span>
                        </>
                      )}
                    </div>

                    <div className="wa-detail-price-card">
                      <span className="eyebrow">REFERÊNCIA REGIONAL</span>
                      {focusedActiveStation?.deltaPercent !== undefined && stateRow ? (
                        <>
                          <strong
                            className={
                              focusedActiveStation.deltaPercent < 0
                                ? 'text-teal'
                                : focusedActiveStation.deltaPercent > 0
                                  ? 'text-crimson'
                                  : ''
                            }
                          >
                            {signedPercent(focusedActiveStation.deltaPercent)}
                          </strong>
                          <span>
                            vs. {selection.uf}: {money(stateRow.p)}/{unitLabel(product.unit)}
                          </span>
                          {focusedCityRow && (
                            <small>
                              {focusedCityRow.eligible
                                ? `Município: ${money(focusedCityRow.p)}`
                                : `Município (${count(focusedCityRow.n)} p.): cob. < 3`}
                            </small>
                          )}
                        </>
                      ) : (
                        <>
                          <strong className="muted-price">—</strong>
                          <span>
                            {stateRow
                              ? `Mediana ${selection.uf}: ${money(stateRow.p)}`
                              : 'Sem referência elegível'}
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Directions / Google Maps CTA (WA Purple Button) */}
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${focusedFeature.geometry.coordinates[1]},${focusedFeature.geometry.coordinates[0]}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="wa-btn-primary wa-directions-btn"
                  >
                    <Navigation size={15} />
                    <span>Abrir localização no Google Maps</span>
                    <ExternalLink size={14} />
                  </a>

                  {/* Station Individual Weekly Price Trend */}
                  <TrendChart
                    rows={focusedStationSeries}
                    referenceRows={focusedUfSeries}
                    referenceLabel={selection.uf ? `Mediana ${selection.uf}` : undefined}
                    primaryLabel={focusedFeature.properties.name}
                    unit={product.unit}
                    week={week}
                    weeks={manifest.weeks}
                    windowMode={chartWindow}
                    onWindowChange={setChartWindow}
                    onSelectWeek={w => {
                      setPlaying(false);
                      setWeek(w);
                    }}
                  />

                  {/* ANP Cadastral Provenance & Honest Limitations */}
                  <div className="wa-provenance-box">
                    <div className="wa-provenance-head">
                      <Info size={14} />
                      <strong>Cadastro ANP &amp; Acurácia Geográfica</strong>
                    </div>
                    <dl className="wa-provenance-dl">
                      <div>
                        <dt>Origem cadastral</dt>
                        <dd>{focusedFeature.properties.origin || 'API Revendedores ANP'}</dd>
                      </div>
                      <div>
                        <dt>Consulta cadastral</dt>
                        <dd>{focusedFeature.properties.dataObtained || 'Snapshot atual'}</dd>
                      </div>
                      <div>
                        <dt>Acurácia informada</dt>
                        <dd>{count(focusedFeature.properties.accuracyMeters)} m</dd>
                      </div>
                      <div>
                        <dt>Semanas com preço</dt>
                        <dd>
                          {count(focusedFeature.properties.prices.length)} de{' '}
                          {count(manifest.weeks.length)}
                        </dd>
                      </div>
                    </dl>
                    <p className="wa-provenance-note">
                      Posição geográfica classificada pela ANP como <em>não validada</em>. O cadastro reflete a base atual da agência e pode diferir da bandeira ou endereço vigentes na data da coleta histórica.
                    </p>
                  </div>
                </div>
              ) : !selection.uf ? (
                /* STATE A: BRASIL LANDING — National Summary + 27 UFs Sorted Cheapest-First */
                <>
                  <div className="wa-national-banner">
                    <div>
                      <span className="eyebrow">MEDIANA NACIONAL · PESO 1 POR POSTO</span>
                      <div className="wa-national-price-row">
                        <strong>
                          {national ? money(national.p) : '—'}
                          <small>/{unitLabel(product.unit)}</small>
                        </strong>
                        {national && (
                          <span>
                            {count(national.n)} postos · {count(national.c)} coletas
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="wa-national-hint">
                      Selecione um estado na lista ou no mapa para carregar os postos e ruas.
                    </p>
                  </div>

                  {selectedBrands.length > 0 && (
                    <div className="wa-active-filters-strip">
                      <span>
                        Filtro pré-ativo: <b>{selectedBrands.length} bandeiras</b> (aplicado ao abrir uma UF)
                      </span>
                      <button type="button" onClick={() => setSelectedBrands([])}>
                        Limpar
                      </button>
                    </div>
                  )}

                  <div className="wa-list-search-inline">
                    <Search size={14} />
                    <input
                      type="search"
                      placeholder="Filtrar entre os 27 estados…"
                      value={listFilter}
                      onChange={e => setListFilter(e.target.value)}
                    />
                  </div>

                  <div className="wa-card-list" role="list">
                    {sortedStates.map(row => {
                      const st = manifest.states.find(s => s.uf === row.uf);
                      if (!st) return null;
                      const isCheapest =
                        minStatePrice !== undefined &&
                        Math.abs(row.p - minStatePrice) < 0.0005;
                      const stDelta =
                        row.eligible && national?.p
                          ? (row.p / national.p - 1) * 100
                          : undefined;

                      return (
                        <button
                          key={row.uf}
                          type="button"
                          role="listitem"
                          className="wa-row-card"
                          onClick={() => applySelection({ uf: row.uf })}
                        >
                          <div className="wa-row-price-col">
                            <strong className={isCheapest ? 'is-cheapest' : ''}>
                              {priceDigits(row.p)}
                            </strong>
                            <small>R$/{unitLabel(product.unit)}</small>
                            {stDelta !== undefined && (
                              <em className={stDelta < 0 ? 'down' : stDelta > 0 ? 'up' : ''}>
                                {signedPercent(stDelta)}
                              </em>
                            )}
                          </div>

                          <div className="wa-row-info-col">
                            <strong>{st.name}</strong>
                            <span>{st.region.toUpperCase()}</span>
                            <small>
                              {count(row.n)} postos · {count(row.c)} coletas
                            </small>
                          </div>

                          <div className="wa-row-badge-col">
                            <span className={`wa-uf-tile ${isCheapest ? 'is-cheapest' : ''}`}>
                              {row.uf}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </>
              ) : explorerTab === 'regions' ? (
                /* STATE B2: UF MUNICIPALITIES LIST */
                <>
                  <div className="wa-uf-summary-strip">
                    <div>
                      <span>
                        Mediana {selection.uf}:{' '}
                        <b>{stateRow ? `${money(stateRow.p)}/${unitLabel(product.unit)}` : '—'}</b>
                      </span>
                      <small>{count(visibleCities.length)} municípios pesquisados na semana</small>
                    </div>
                  </div>

                  <div className="wa-list-search-inline">
                    <Search size={14} />
                    <input
                      type="search"
                      placeholder={`Filtrar município em ${selection.uf}…`}
                      value={listFilter}
                      onChange={e => setListFilter(e.target.value)}
                    />
                  </div>

                  <div className="wa-card-list" role="list">
                    {sortedUfCities.map(row => {
                      const c = cityById.get(row.id);
                      if (!c) return null;
                      const isCheapest =
                        minCityPrice !== undefined && Math.abs(row.p - minCityPrice) < 0.0005;
                      const cDelta =
                        row.eligible && row.ref ? (row.p / row.ref - 1) * 100 : undefined;

                      return (
                        <button
                          key={row.id}
                          type="button"
                          role="listitem"
                          className={`wa-row-card ${selection.city === row.id ? 'is-active' : ''}`}
                          onClick={() => applySelection({ uf: selection.uf, city: row.id })}
                        >
                          <div className="wa-row-price-col">
                            <strong className={isCheapest ? 'is-cheapest' : ''}>
                              {priceDigits(row.p)}
                            </strong>
                            <small>R$/{unitLabel(product.unit)}</small>
                            {cDelta !== undefined && (
                              <em className={cDelta < 0 ? 'down' : cDelta > 0 ? 'up' : ''}>
                                {signedPercent(cDelta)}
                              </em>
                            )}
                          </div>

                          <div className="wa-row-info-col">
                            <strong>{c.name}</strong>
                            <span>MUNICÍPIO · {c.uf}</span>
                            <small>
                              {count(row.n)} {row.n === 1 ? 'posto' : 'postos'} · {count(row.c)}{' '}
                              coletas
                            </small>
                          </div>

                          <div className="wa-row-badge-col">
                            <span className="wa-uf-tile subtle">{c.uf}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </>
              ) : (
                /* STATE B1: FUELWATCH WA VIEWPORT-SYNCED STATION FINDER */
                <>
                  <div className="wa-uf-summary-strip">
                    <div>
                      <span>
                        {cityMeta && cityRow ? (
                          <>
                            Mediana {cityMeta.name}:{' '}
                            <b>
                              {money(cityRow.p)}/{unitLabel(product.unit)}
                            </b>
                          </>
                        ) : (
                          <>
                            Mediana {selection.uf}:{' '}
                            <b>
                              {stateRow
                                ? `${money(stateRow.p)}/${unitLabel(product.unit)}`
                                : '—'}
                            </b>
                          </>
                        )}
                      </span>
                      <small>
                        {loadingStations
                          ? 'Carregando postos da UF…'
                          : `${count(viewportStations.length)} ${
                              viewportStations.length === 1 ? 'posto' : 'postos'
                            } na área visível do mapa`}
                      </small>
                    </div>

                    {cityMeta && (
                      <button
                        type="button"
                        className={`wa-city-lock-chip ${strictCityOnly ? 'active' : ''}`}
                        onClick={() => setStrictCityOnly(v => !v)}
                        title="Alternar entre todos os postos visíveis no mapa ou apenas dentro do município"
                      >
                        {strictCityOnly ? `Só ${cityMeta.name} ✓` : `Só ${cityMeta.name}`}
                      </button>
                    )}
                  </div>

                  {selectedBrands.length > 0 && (
                    <div className="wa-active-filters-strip">
                      <div className="wa-brand-chips">
                        {selectedBrands.map(b => (
                          <button
                            key={b}
                            type="button"
                            onClick={() =>
                              setSelectedBrands(prev => prev.filter(item => item !== b))
                            }
                          >
                            {distributorVisual(b).label} <X size={11} />
                          </button>
                        ))}
                      </div>
                      <button type="button" onClick={() => setSelectedBrands([])}>
                        Limpar
                      </button>
                    </div>
                  )}

                  <div className="wa-list-search-inline">
                    <Search size={14} />
                    <input
                      type="search"
                      placeholder="Filtrar posto, endereço, bairro ou bandeira…"
                      value={listFilter}
                      onChange={e => {
                        setListFilter(e.target.value);
                        setShowAllStations(false);
                      }}
                    />
                  </div>

                  {loadingStations ? (
                    <div className="wa-sidebar-empty" role="status">
                      <span className="spinner-sm" />
                      <p>Carregando postos georreferenciados de {selection.uf}…</p>
                    </div>
                  ) : displayedStations.length > 0 ? (
                    <>
                      <div className="wa-card-list" role="list">
                        {displayedStations.map(st => {
                          const p = st.properties;
                          const isCheapest =
                            minStationPriceInList !== undefined &&
                            st.price <= minStationPriceInList + 0.0005;
                          const street = sanitizeStreet(p.address, p.complement);
                          const suburb = formatSuburbLine(p.neighborhood, p.municipality);
                          const vis = distributorVisual(p.distributor);

                          return (
                            <button
                              key={st.key}
                              type="button"
                              role="listitem"
                              className="wa-row-card wa-station-card"
                              onClick={() => setFocusedStationKey(st.key)}
                            >
                              <div className="wa-row-price-col">
                                <strong className={isCheapest ? 'is-cheapest' : ''}>
                                  {priceDigits(st.price)}
                                </strong>
                                <small>R$/{unitLabel(product.unit)}</small>
                                <span className="wa-col-count">
                                  {st.collections} {st.collections === 1 ? 'coleta' : 'coletas'}
                                </span>
                              </div>

                              <div className="wa-row-info-col">
                                <strong>{p.name}</strong>
                                {street && <span className="wa-street-line">{street}</span>}
                                {suburb && <span className="wa-suburb-line">{suburb}</span>}
                                {vis.isWhiteLabel && (
                                  <em className="wa-station-tag">Bandeira branca</em>
                                )}
                              </div>

                              <div className="wa-row-badge-col">
                                <DistributorBadge distributor={p.distributor} size="md" />
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      {!showAllStations && viewportStations.length > displayedStations.length && (
                        <div className="wa-load-more-wrap">
                          <button
                            type="button"
                            className="wa-btn-secondary full-width"
                            onClick={() => setShowAllStations(true)}
                          >
                            Ver todos os {count(viewportStations.length)} postos na área
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="wa-sidebar-empty">
                      <p>
                        {activeStations.length === 0
                          ? 'Nenhum posto pesquisado atende aos filtros nesta semana.'
                          : 'Nenhum posto na área visível atual do mapa.'}
                      </p>
                      <div className="wa-empty-actions">
                        {activeStations.length > 0 && (
                          <button
                            type="button"
                            className="wa-btn-primary"
                            onClick={() => setReframeToken(v => v + 1)}
                          >
                            <Crosshair size={15} />
                            Reenquadrar {cityMeta?.name || selection.uf}
                          </button>
                        )}
                        {(selectedBrands.length > 0 || listFilter) && (
                          <button
                            type="button"
                            className="wa-btn-secondary"
                            onClick={() => {
                              setSelectedBrands([]);
                              setListFilter('');
                            }}
                          >
                            Limpar filtros
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </aside>

          {/* Full-Height Interactive Street Map */}
          <AtlasMap
            manifest={manifest}
            states={states}
            cities={visibleCities}
            activeStations={activeStations}
            loadingStations={loadingStations}
            stationError={stationError}
            showStations={showStations}
            onToggleStations={() => setShowStations(v => !v)}
            focusedStationKey={focusedStationKey}
            onFocusStation={setFocusedStationKey}
            selection={selection}
            metric={metric}
            national={national?.p}
            range={range}
            unit={product.unit}
            visible={view === 'map'}
            reframeToken={reframeToken}
            onSelect={next => applySelection(next)}
            onViewportChange={handleViewportChange}
          />
      </main>

      {/* FuelWatch WA Slide-Over Right Sidenav Drawer */}
      {sidenavOpen && (
        <div
          className="wa-sidenav-backdrop"
          role="presentation"
          onClick={e => {
            if (e.target === e.currentTarget) setSidenavOpen(false);
          }}
        >
          <aside className="wa-sidenav" aria-label="Menu de navegação">
            <div className="wa-sidenav-head">
              <FuelWatchLogo
                onClick={() => {
                  setView('map');
                  applySelection({});
                  setSidenavOpen(false);
                }}
              />
              <button
                type="button"
                className="icon-btn"
                aria-label="Fechar menu"
                onClick={() => setSidenavOpen(false)}
              >
                <X size={20} />
              </button>
            </div>

            <nav className="wa-sidenav-links">
              <button
                type="button"
                className={view === 'map' ? 'active' : ''}
                onClick={() => {
                  setView('map');
                  setSidenavOpen(false);
                }}
              >
                <MapIcon size={18} />
                <div>
                  <strong>Mapa de preços</strong>
                  <small>Busca geográfica por UF, município e postos</small>
                </div>
              </button>

              <button
                type="button"
                className={view === 'trends' ? 'active' : ''}
                onClick={() => {
                  setView('trends');
                  setSidenavOpen(false);
                }}
              >
                <TrendingUp size={18} />
                <div>
                  <strong>Tendências de preços</strong>
                  <small>Curvas semanais e amplitude (2024–2026)</small>
                </div>
              </button>

              <button
                type="button"
                className={view === 'regional' ? 'active' : ''}
                onClick={() => {
                  setView('regional');
                  setSidenavOpen(false);
                }}
              >
                <Table size={18} />
                <div>
                  <strong>Médias e dados regionais</strong>
                  <small>Rankings por semana ISO e exportação CSV</small>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSidenavOpen(false);
                  setFiltersOpen(true);
                }}
              >
                <Filter size={18} />
                <div>
                  <strong>Filtros avançados</strong>
                  <small>Combustível, semana e bandeiras</small>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSidenavOpen(false);
                  setMethodologyOpen(true);
                }}
              >
                <ShieldCheck size={18} />
                <div>
                  <strong>Metodologia &amp; Linhagem Fabric</strong>
                  <small>Regras analíticas e hashes SHA-256</small>
                </div>
              </button>
            </nav>

            <div className="wa-sidenav-divider" />

            <div className="wa-sidenav-ext">
              <span className="eyebrow">PORTFÓLIO &amp; AUDITORIA</span>
              <a
                href="https://github.com/victorhobdev/fuel-watch-br"
                target="_blank"
                rel="noreferrer"
              >
                <Database size={15} /> Repositório Fuel Watch BR <ExternalLink size={13} />
              </a>
              <a
                href={`${import.meta.env.BASE_URL}data/manifest.json`}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={15} /> Manifesto do Snapshot JSON
              </a>
              <a
                href={`${import.meta.env.BASE_URL}data/validation.json`}
                target="_blank"
                rel="noreferrer"
              >
                <ShieldCheck size={15} /> Recibo de Reconciliação Gold
              </a>
            </div>

            <footer className="wa-sidenav-foot">
              <strong>{count(manifest.dataset.observations)} coletas aceitas</strong>
              <span>
                Período {date(manifest.dataset.periodStart)} a {date(manifest.dataset.periodEnd)} · Snapshot estático reconciliado com o Warehouse Gold no Microsoft Fabric.
              </span>
            </footer>
          </aside>
        </div>
      )}

      {/* Filters Modal */}
      {filtersOpen && (
        <FiltersModal
          manifest={manifest}
          productId={productId}
          week={week}
          sort={sort}
          metric={metric}
          selectedBrands={selectedBrands}
          availableBrands={availableBrands}
          hasLoadedUf={Boolean(selection.uf)}
          onApply={next => {
            setPlaying(false);
            setProductId(next.productId);
            setWeek(next.week);
            setSort(next.sort);
            setMetric(next.metric);
            setSelectedBrands(next.selectedBrands);
          }}
          onClose={() => setFiltersOpen(false)}
        />
      )}

      {/* Methodology & Microsoft Fabric Lineage Modal */}
      {methodologyOpen && (
        <MethodologyModal manifest={manifest} onClose={() => setMethodologyOpen(false)} />
      )}
    </div>
  );
}

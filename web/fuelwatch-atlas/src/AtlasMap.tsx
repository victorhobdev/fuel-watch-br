import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { type GeoJSONSource, type MapMouseEvent, type StyleSpecification } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { ArrowLeft, Crosshair, Eye, EyeOff, Layers, Minus, Plus } from 'lucide-react';
import {
  count,
  distributorVisual,
  getData,
  money,
  moneyCompact,
  NO_DATA_FILL,
  priceColor,
  priceDigits,
  signedPercent,
  unitLabel,
  type ActiveStation,
  type CityRow,
  type Manifest,
  type Metric,
  type Selection,
  type StateRow,
  type ViewportBounds,
} from './data';

maplibregl.setWorkerUrl(workerUrl);

type PolyFeature = GeoJSON.Feature<
  GeoJSON.Geometry,
  { codarea: string; color?: string; selected?: boolean; hasData?: boolean }
>;
type PolyCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, PolyFeature['properties']>;

const EMPTY_POLYGONS: PolyCollection = { type: 'FeatureCollection', features: [] };

const STATE_LABEL_OFFSETS: Record<string, [number, number]> = {
  RN: [16, -7],
  PB: [20, 1],
  PE: [-8, 3],
  AL: [18, 9],
  SE: [15, 15],
  ES: [13, 2],
  RJ: [10, 9],
  DF: [9, -5],
};

const FALLBACK_LIGHT_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#CBE2F5' },
    },
  ],
};

const VECTOR_STYLE_URLS = [
  'https://tiles.openfreemap.org/styles/liberty',
  'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
];

const BRASIL_BOUNDS: [[number, number], [number, number]] = [
  [-73.99, -33.75],
  [-34.75, 5.28],
];

const MIN_MAP_ZOOM = 2.8;
const MAX_MAP_ZOOM = 17.5;

const BRASIL_FIT_PADDING = { top: 28, right: 38, bottom: 28, left: 24 };

function tuneStyleForBrazilFocus(raw: StyleSpecification): StyleSpecification {
  const tunedLayers = raw.layers
    .filter(layer => !layer.id.startsWith('label_country'))
    .map(layer => {
      if (layer.id === 'natural_earth' && layer.type === 'raster') {
        return {
          ...layer,
          paint: { ...(layer.paint || {}), 'raster-opacity': 0.12 },
        };
      }
      if (layer.id === 'boundary_2' && layer.type === 'line') {
        return {
          ...layer,
          paint: { ...(layer.paint || {}), 'line-opacity': 0.22 },
        };
      }
      if (
        layer.type === 'symbol' &&
        (layer.id.startsWith('label_city') ||
          layer.id.startsWith('label_town') ||
          layer.id.startsWith('label_state') ||
          layer.id.startsWith('country'))
      ) {
        return {
          ...layer,
          minzoom: Math.max(layer.minzoom ?? 0, 5.4),
        };
      }
      return layer;
    });

  return { ...raw, layers: tunedLayers };
}

async function resolveBasemapStyle(): Promise<{
  style: StyleSpecification;
  hasStreetTiles: boolean;
}> {
  for (const url of VECTOR_STYLE_URLS) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 4500);
    try {
      const res = await fetch(url, { signal: controller.signal });
      window.clearTimeout(timer);
      if (res.ok) {
        const json = (await res.json()) as StyleSpecification;
        if (json && Array.isArray(json.layers)) {
          return { style: tuneStyleForBrazilFocus(json), hasStreetTiles: true };
        }
      }
    } catch {
      window.clearTimeout(timer);
    }
  }
  return { style: FALLBACK_LIGHT_STYLE, hasStreetTiles: false };
}

type Props = {
  manifest: Manifest;
  states: StateRow[];
  cities: CityRow[];
  activeStations: ActiveStation[];
  loadingStations: boolean;
  stationError: boolean;
  showStations: boolean;
  onToggleStations: () => void;
  focusedStationKey: string | null;
  onFocusStation: (key: string | null) => void;
  selection: Selection;
  metric: Metric;
  national?: number;
  range: [number, number];
  unit: string;
  visible: boolean;
  reframeToken: number;
  onSelect: (selection: Selection) => void;
  onViewportChange: (bounds: ViewportBounds, zoom: number) => void;
};

type HoverState = {
  eyebrow: string;
  name: string;
  row?: StateRow | CityRow;
  reference?: number;
  referenceName?: string;
  x: number;
  y: number;
  clusterInfo?: { count: number; minPrice: number };
};

function computeBounds(feature: GeoJSON.Feature | PolyCollection): maplibregl.LngLatBounds {
  const b = new maplibregl.LngLatBounds();
  function walk(coords: unknown): void {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === 'number') b.extend(coords as [number, number]);
    else coords.forEach(walk);
  }
  const features = feature.type === 'FeatureCollection' ? feature.features : [feature];
  features.forEach(f => {
    if (f.geometry.type !== 'GeometryCollection') walk(f.geometry.coordinates);
  });
  return b;
}

function buildPricePinElement(
  station: ActiveStation,
  unit: string,
  isCheapest: boolean,
  isSelected: boolean,
  onClick: () => void,
): HTMLButtonElement {
  const vis = distributorVisual(station.properties.distributor);
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = [
    'wa-price-pin',
    isCheapest ? 'is-cheapest' : '',
    isSelected ? 'is-selected' : '',
  ]
    .filter(Boolean)
    .join(' ');
  btn.setAttribute(
    'aria-label',
    `${station.properties.name}, ${money(station.price)} por ${unitLabel(unit)}, ${vis.label}`,
  );

  const card = document.createElement('span');
  card.className = 'wa-pin-card';

  const priceBar = document.createElement('span');
  priceBar.className = 'wa-pin-price';
  priceBar.textContent = priceDigits(station.price);
  card.append(priceBar);

  const brandBox = document.createElement('span');
  brandBox.className = 'wa-pin-brand';

  const pill = document.createElement('span');
  pill.className = `wa-pin-brand-pill ${vis.isWhiteLabel ? 'is-white' : ''}`;
  pill.style.backgroundColor = vis.bg;
  pill.style.color = vis.fg;
  pill.textContent = vis.short;
  brandBox.append(pill);
  card.append(brandBox);

  const tip = document.createElement('span');
  tip.className = 'wa-pin-tip';
  card.append(tip);

  btn.append(card);

  btn.addEventListener('click', ev => {
    ev.stopPropagation();
    onClick();
  });

  return btn;
}

function buildClusterElement(
  clusterCount: number,
  minPrice: number,
  unit: string,
  isCheapest: boolean,
  onClick: () => void,
  onHoverEnter: (ev: MouseEvent) => void,
  onHoverLeave: () => void,
): HTMLButtonElement {
  const sizeClass =
    clusterCount >= 200
      ? 'size-xl'
      : clusterCount >= 50
        ? 'size-lg'
        : clusterCount >= 10
          ? 'size-md'
          : 'size-sm';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = `wa-cluster-pin ${sizeClass} ${isCheapest ? 'is-cheapest' : ''}`;
  btn.setAttribute(
    'aria-label',
    `${count(clusterCount)} ${clusterCount === 1 ? 'posto' : 'postos'}, menor preço ${money(minPrice)} por ${unitLabel(unit)}`,
  );

  const core = document.createElement('span');
  core.className = 'wa-cluster-core';
  core.textContent = count(clusterCount);
  btn.append(core);

  btn.addEventListener('click', ev => {
    ev.stopPropagation();
    onClick();
  });
  btn.addEventListener('mouseenter', onHoverEnter);
  btn.addEventListener('mouseleave', onHoverLeave);

  return btn;
}

export default function AtlasMap(props: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const stateShapesRef = useRef<PolyCollection | null>(null);
  const cityShapesRef = useRef<PolyCollection | null>(null);
  const currentProps = useRef(props);
  currentProps.current = props;

  const [ready, setReady] = useState(false);
  const [hasStreetTiles, setHasStreetTiles] = useState(true);
  const [hover, setHover] = useState<HoverState | null>(null);
  const [problem, setProblem] = useState('');
  const [loadingCities, setLoadingCities] = useState(false);
  const [zoom, setZoom] = useState(3.5);
  const [retry, setRetry] = useState(0);
  const [showChoroplethLegend, setShowChoroplethLegend] = useState(true);

  const stateLabelsRef = useRef<maplibregl.Marker[]>([]);
  const cityLabelsRef = useRef<maplibregl.Marker[]>([]);
  const stationMarkersRef = useRef<maplibregl.Marker[]>([]);
  const cameraSelectionRef = useRef('');
  const internalClickedKeyRef = useRef<string | null>(null);
  const renderMarkersFnRef = useRef<() => void>(() => {});

  const emitViewport = (instance: maplibregl.Map) => {
    const b = instance.getBounds();
    const z = instance.getZoom();
    setZoom(z);
    currentProps.current.onViewportChange(
      {
        west: b.getWest(),
        south: b.getSouth(),
        east: b.getEast(),
        north: b.getNorth(),
      },
      z,
    );
  };

  // Initialize MapLibre with OpenFreeMap street vector style (and resilient fallback)
  useEffect(() => {
    if (!containerRef.current) return;
    let alive = true;
    let instance: maplibregl.Map | null = null;

    void resolveBasemapStyle().then(({ style, hasStreetTiles: streetOk }) => {
      if (!alive || !containerRef.current) return;
      setHasStreetTiles(streetOk);

      try {
        instance = new maplibregl.Map({
          container: containerRef.current,
          attributionControl: false,
          bounds: BRASIL_BOUNDS,
          fitBoundsOptions: { padding: BRASIL_FIT_PADDING },
          minZoom: MIN_MAP_ZOOM,
          maxZoom: MAX_MAP_ZOOM,
          maxPitch: 0,
          renderWorldCopies: false,
          style,
        });
      } catch {
        setProblem(
          'Seu navegador não conseguiu iniciar o motor WebGL do mapa. A lista lateral, filtros e tabelas continuam disponíveis.',
        );
        return;
      }

      mapRef.current = instance;
      instance.dragRotate.disable();
      instance.touchZoomRotate.disableRotation();
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      instance.once('style.load', async () => {
        if (!alive || !instance) return;
        try {
          const shapes = await getData<PolyCollection>(
            currentProps.current.manifest.geometry.statesFile,
          );
          if (!alive || !instance) return;
          stateShapesRef.current = shapes;

          // Place IBGE polygons beneath vector text labels so street/place names stay crisp
          const styleLayers = instance.getStyle()?.layers || [];
          const firstSymbolId =
            styleLayers.find(l => l.type === 'symbol' && !l.id.includes('arrow'))?.id ||
            styleLayers.find(l => l.type === 'symbol')?.id;

          const pInit = currentProps.current;
          const initialStates: PolyCollection = {
            ...shapes,
            features: shapes.features.map(feature => {
              const state = pInit.manifest.states.find(
                s => s.id === String(feature.properties.codarea),
              );
              const row = pInit.states.find(r => r.uf === state?.uf);
              const value =
                pInit.metric === 'comparison'
                  ? row?.eligible && pInit.national
                    ? (row.p / pInit.national - 1) * 100
                    : undefined
                  : row?.p;
              return {
                ...feature,
                properties: {
                  ...feature.properties,
                  color: priceColor(value, ...pInit.range, pInit.metric),
                  selected: state?.uf === pInit.selection.uf,
                },
              };
            }),
          };

          instance.addSource('states', { type: 'geojson', data: initialStates });
          instance.addLayer(
            {
              id: 'states-fill',
              type: 'fill',
              source: 'states',
              paint: {
                'fill-color': ['coalesce', ['get', 'color'], NO_DATA_FILL],
                'fill-opacity': 0.86,
              },
            },
            firstSymbolId,
          );
          instance.addLayer(
            {
              id: 'states-line',
              type: 'line',
              source: 'states',
              paint: {
                'line-color': '#FFFFFF',
                'line-width': 1.35,
                'line-opacity': 0.95,
              },
            },
            firstSymbolId,
          );
          instance.addLayer(
            {
              id: 'states-selected',
              type: 'line',
              source: 'states',
              filter: ['==', ['get', 'selected'], true],
              paint: {
                'line-color': '#4B287D',
                'line-width': 2.5,
                'line-opacity': 0.9,
              },
            },
            firstSymbolId,
          );

          instance.addSource('cities', { type: 'geojson', data: EMPTY_POLYGONS });
          instance.addLayer(
            {
              id: 'cities-fill',
              type: 'fill',
              source: 'cities',
              paint: {
                'fill-color': ['coalesce', ['get', 'color'], NO_DATA_FILL],
                'fill-opacity': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  5,
                  ['case', ['boolean', ['get', 'hasData'], false], 0.52, 0.16],
                  8.5,
                  ['case', ['boolean', ['get', 'hasData'], false], 0.34, 0.08],
                  10.8,
                  ['case', ['boolean', ['get', 'hasData'], false], 0.08, 0.02],
                  12.5,
                  0.02,
                ],
              },
            },
            firstSymbolId,
          );
          instance.addLayer(
            {
              id: 'cities-line',
              type: 'line',
              source: 'cities',
              paint: {
                'line-color': '#64748B',
                'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.55, 11, 0.85],
                'line-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.42, 11, 0.22, 13, 0.1],
              },
            },
            firstSymbolId,
          );
          instance.addLayer(
            {
              id: 'city-selected',
              type: 'line',
              source: 'cities',
              filter: ['==', ['get', 'selected'], true],
              paint: {
                'line-color': '#00797B',
                'line-width': 2.5,
                'line-dasharray': [2, 1.5],
              },
            },
            firstSymbolId,
          );

          instance.on('mousemove', (event: MapMouseEvent) => {
            if (!instance) return;
            const p = currentProps.current;
            // At street zoom (>= 10.6) inside a UF, let the street map breathe without polygon hover noise
            if (p.selection.uf && instance.getZoom() >= 10.6) {
              setHover(prev => (prev?.clusterInfo ? prev : null));
              instance.getCanvas().style.cursor = '';
              return;
            }

            const queryLayers = p.selection.uf ? ['cities-fill', 'states-fill'] : ['states-fill'];
            const features = instance.queryRenderedFeatures(event.point, { layers: queryLayers });
            const cityFeature = features.find(f => f.layer.id === 'cities-fill');
            const poly = cityFeature || features.find(f => f.layer.id === 'states-fill');
            if (!poly) {
              setHover(prev => (prev?.clusterInfo ? prev : null));
              instance.getCanvas().style.cursor = '';
              return;
            }

            const id = String(poly.properties.codarea);
            const isCity = Boolean(cityFeature);
            instance.getCanvas().style.cursor = 'pointer';

            if (isCity) {
              const place = p.manifest.cities.find(c => c.id === id);
              const row = p.cities.find(c => c.id === id);
              if (!place && !row) {
                setHover(null);
                instance.getCanvas().style.cursor = '';
                return;
              }
              setHover({
                eyebrow: `MUNICÍPIO · ${place?.uf || p.selection.uf || ''}`,
                name: place?.name || `Município IBGE ${id}`,
                row,
                reference: row?.ref,
                referenceName: place?.uf || 'UF',
                x: event.point.x,
                y: event.point.y,
              });
            } else {
              const state = p.manifest.states.find(s => s.id === id);
              const row = p.states.find(s => s.uf === state?.uf);
              setHover({
                eyebrow: `ESTADO · ${(state?.region || '').toUpperCase()}`,
                name: state ? `${state.name} (${state.uf})` : id,
                row,
                reference: p.national,
                referenceName: 'Brasil',
                x: event.point.x,
                y: event.point.y,
              });
            }
          });

          instance.on('mouseout', () => {
            setHover(null);
          });

          instance.on('click', (event: MapMouseEvent) => {
            if (!instance) return;
            const p = currentProps.current;

            if (!p.selection.uf) {
              const features = instance.queryRenderedFeatures(event.point, {
                layers: ['states-fill'],
              });
              const statePoly = features[0];
              if (statePoly) {
                const state = p.manifest.states.find(
                  s => s.id === String(statePoly.properties.codarea),
                );
                if (state) p.onSelect({ uf: state.uf });
              }
              return;
            }

            // At state zoom (< 10.4), clicking a researched municipality drills into it;
            // at street zoom (>= 10.4), clicking empty map clears focused station without hijacking pan.
            if (instance.getZoom() < 10.4) {
              const features = instance.queryRenderedFeatures(event.point, {
                layers: ['cities-fill', 'states-fill'],
              });
              const city = features.find(f => f.layer.id === 'cities-fill');
              if (city) {
                const place = p.manifest.cities.find(
                  c => c.id === String(city.properties.codarea),
                );
                if (place) {
                  p.onSelect({ uf: place.uf, city: place.id });
                  return;
                }
              }
              const statePoly = features.find(f => f.layer.id === 'states-fill');
              if (statePoly) {
                const state = p.manifest.states.find(
                  s => s.id === String(statePoly.properties.codarea),
                );
                if (state && state.uf !== p.selection.uf) {
                  p.onSelect({ uf: state.uf });
                  return;
                }
              }
            }

            if (p.focusedStationKey) {
              p.onFocusStation(null);
            }
          });

          const onCameraChangeEnd = () => {
            if (!instance) return;
            emitViewport(instance);
            renderMarkersFnRef.current();
          };

          instance.on('moveend', onCameraChangeEnd);
          instance.on('zoomend', onCameraChangeEnd);

          const observer = new ResizeObserver(() => {
            instance?.resize();
            renderMarkersFnRef.current();
          });
          observer.observe(containerRef.current!);
          instance.once('remove', () => observer.disconnect());

          if (!currentProps.current.selection.uf) {
            cameraSelectionRef.current = `BR::${currentProps.current.reframeToken}`;
            instance.fitBounds(BRASIL_BOUNDS, {
              padding: BRASIL_FIT_PADDING,
              duration: 0,
            });
          }
          emitViewport(instance);
          setReady(true);
        } catch {
          if (alive) {
            setProblem('A malha cartográfica do IBGE não pôde ser carregada. Tente novamente.');
          }
        }
      });
    });

    return () => {
      alive = false;
      stateLabelsRef.current.forEach(m => m.remove());
      cityLabelsRef.current.forEach(m => m.remove());
      stationMarkersRef.current.forEach(m => m.remove());
      stateLabelsRef.current = [];
      cityLabelsRef.current = [];
      stationMarkersRef.current = [];
      instance?.remove();
      mapRef.current = null;
    };
  }, [props.manifest]);

  // Update State Polygons & Clickable State Pills at Brasil Level
  useEffect(() => {
    if (!ready || !mapRef.current || !stateShapesRef.current) return;
    const p = props;
    const updated: PolyCollection = {
      ...stateShapesRef.current,
      features: stateShapesRef.current.features.map(feature => {
        const state = p.manifest.states.find(s => s.id === String(feature.properties.codarea));
        const row = p.states.find(r => r.uf === state?.uf);
        const value =
          p.metric === 'comparison'
            ? row?.eligible && p.national
              ? (row.p / p.national - 1) * 100
              : undefined
            : row?.p;
        return {
          ...feature,
          properties: {
            ...feature.properties,
            color: priceColor(value, ...p.range, p.metric),
            selected: state?.uf === p.selection.uf,
          },
        };
      }),
    };

    const source = mapRef.current.getSource('states') as GeoJSONSource | undefined;
    source?.setData(updated);
    if (mapRef.current.getLayer('states-fill')) {
      mapRef.current.setPaintProperty('states-fill', 'fill-opacity', p.selection.uf ? 0.03 : 0.86);
    }
    if (mapRef.current.getLayer('states-line')) {
      mapRef.current.setPaintProperty(
        'states-line',
        'line-color',
        p.selection.uf ? '#94A3B8' : '#FFFFFF',
      );
    }

    stateLabelsRef.current.forEach(m => m.remove());
    stateLabelsRef.current = [];

    if (!p.selection.uf) {
      const minStatePrice = p.states.length ? Math.min(...p.states.map(s => s.p)) : undefined;
      updated.features.forEach(feature => {
        const state = p.manifest.states.find(s => s.id === String(feature.properties.codarea));
        if (!state) return;
        const row = p.states.find(r => r.uf === state.uf);
        const isLowest =
          row !== undefined &&
          minStatePrice !== undefined &&
          Math.abs(row.p - minStatePrice) < 0.0005;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `map-state-pill ${isLowest ? 'is-cheapest' : ''}`;
        btn.textContent = state.uf;
        btn.setAttribute(
          'aria-label',
          `Explorar ${state.name}${row ? `, mediana ${money(row.p)}` : ', sem coleta'}`,
        );
        btn.addEventListener('click', ev => {
          ev.stopPropagation();
          currentProps.current.onSelect({ uf: state.uf });
        });
        stateLabelsRef.current.push(
          new maplibregl.Marker({
            element: btn,
            offset: STATE_LABEL_OFFSETS[state.uf] || [0, 0],
          })
            .setLngLat(computeBounds(feature).getCenter())
            .addTo(mapRef.current!),
        );
      });
    }
    setHover(null);
  }, [
    ready,
    props.states,
    props.range,
    props.metric,
    props.selection.uf,
    props.national,
    props.manifest,
  ]);

  // Update Municipality Polygons & Camera Framing on Selection / Reframe
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    let alive = true;
    const instance = mapRef.current;
    const { selection, manifest, reframeToken } = props;
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 580;
    const cameraKey = `${selection.uf || 'BR'}:${selection.city || ''}:${reframeToken}`;
    const shouldMoveCamera = cameraKey !== cameraSelectionRef.current;
    cameraSelectionRef.current = cameraKey;

    cityLabelsRef.current.forEach(m => m.remove());
    cityLabelsRef.current = [];
    setProblem('');

    if (!selection.uf) {
      cityShapesRef.current = null;
      (instance.getSource('cities') as GeoJSONSource | undefined)?.setData(EMPTY_POLYGONS);
      if (shouldMoveCamera) {
        instance.fitBounds(BRASIL_BOUNDS, { padding: BRASIL_FIT_PADDING, duration });
      }
      setLoadingCities(false);
      return;
    }

    const state = manifest.states.find(s => s.uf === selection.uf);
    const stateFeature = stateShapesRef.current?.features.find(
      f => String(f.properties.codarea) === state?.id,
    );
    if (stateFeature && !selection.city && shouldMoveCamera) {
      instance.fitBounds(computeBounds(stateFeature), {
        padding: { top: 56, right: 56, bottom: 64, left: 56 },
        duration,
        maxZoom: 8.2,
      });
    }

    setLoadingCities(true);
    getData<PolyCollection>(manifest.geometry.cityFiles.replace('{uf}', selection.uf))
      .then(shapes => {
        if (!alive || !mapRef.current) return;
        cityShapesRef.current = shapes;
        const p = currentProps.current;
        const colored: PolyCollection = {
          ...shapes,
          features: shapes.features.map(feature => {
            const row = p.cities.find(c => c.id === String(feature.properties.codarea));
            const value =
              p.metric === 'comparison'
                ? row?.eligible && row.ref
                  ? (row.p / row.ref - 1) * 100
                  : undefined
                : row?.p;
            return {
              ...feature,
              properties: {
                ...feature.properties,
                color: priceColor(value, ...p.range, p.metric),
                selected: String(feature.properties.codarea) === selection.city,
                hasData: row !== undefined,
              },
            };
          }),
        };

        (instance.getSource('cities') as GeoJSONSource | undefined)?.setData(colored);
        const selectedCityFeature = colored.features.find(
          f => String(f.properties.codarea) === selection.city,
        );
        if (selectedCityFeature && shouldMoveCamera) {
          instance.fitBounds(computeBounds(selectedCityFeature), {
            padding: { top: 64, right: 64, bottom: 68, left: 64 },
            duration,
            maxZoom: 11.8,
          });
        }

        // Only show floating city pills when street tiles failed to load (vector basemap already labels cities!)
        if (!hasStreetTiles) {
          const shapeCityIds = new Set(shapes.features.map(f => String(f.properties.codarea)));
          const candidates = selection.city
            ? manifest.cities.filter(c => c.id === selection.city)
            : manifest.cities
                .filter(c => shapeCityIds.has(c.id))
                .sort(
                  (a, b) =>
                    (p.cities.find(c => c.id === b.id)?.n || 0) -
                    (p.cities.find(c => c.id === a.id)?.n || 0),
                );
          const labelled: typeof candidates = [];
          for (const candidate of candidates) {
            if (labelled.length >= 6) break;
            const tooClose = labelled.some(
              placed =>
                Math.hypot(placed.lon - candidate.lon, placed.lat - candidate.lat) < 0.55,
            );
            if (!tooClose || selection.city) labelled.push(candidate);
          }
          labelled.forEach(c => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'map-city-pill';
            btn.textContent = c.name;
            btn.addEventListener('click', ev => {
              ev.stopPropagation();
              currentProps.current.onSelect({ uf: c.uf, city: c.id });
            });
            cityLabelsRef.current.push(
              new maplibregl.Marker({ element: btn }).setLngLat([c.lon, c.lat]).addTo(instance),
            );
          });
        }
        setLoadingCities(false);
      })
      .catch(() => {
        if (alive) {
          setProblem('Não foi possível carregar os limites municipais desta UF.');
          setLoadingCities(false);
        }
      });

    return () => {
      alive = false;
    };
  }, [
    ready,
    hasStreetTiles,
    props.selection.uf,
    props.selection.city,
    props.cities,
    props.metric,
    props.range,
    props.manifest,
    props.reframeToken,
    retry,
  ]);

  // FuelWatch WA Cluster Bubbles & Vertical Price Callout Pins Engine
  const renderStationMarkers = () => {
    stationMarkersRef.current.forEach(m => m.remove());
    stationMarkersRef.current = [];

    const instance = mapRef.current;
    const p = currentProps.current;
    if (!instance || !ready || !p.selection.uf || !p.showStations || !p.activeStations.length) {
      return;
    }

    const bounds = instance.getBounds();
    const west = bounds.getWest();
    const east = bounds.getEast();
    const south = bounds.getSouth();
    const north = bounds.getNorth();
    const padLon = Math.max(0.01, (east - west) * 0.16);
    const padLat = Math.max(0.01, (north - south) * 0.16);

    const strictInBounds = p.activeStations.filter(
      s => s.lon >= west && s.lon <= east && s.lat >= south && s.lat <= north,
    );
    const cheapestPool = strictInBounds.length > 0 ? strictInBounds : p.activeStations;
    const minPrice = Math.min(...cheapestPool.map(s => s.price));
    const isCheapestPrice = (val: number) => val <= minPrice + 0.0005;

    const paddedStations = p.activeStations.filter(
      s =>
        s.lon >= west - padLon &&
        s.lon <= east + padLon &&
        s.lat >= south - padLat &&
        s.lat <= north + padLat,
    );

    const z = instance.getZoom();
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const focused = p.focusedStationKey
      ? p.activeStations.find(s => s.key === p.focusedStationKey)
      : undefined;

    const others = focused
      ? paddedStations.filter(s => s.key !== focused.key)
      : paddedStations;

    // Determine pixel grid cell size for WA-style clustering
    const showIndividualPins =
      z >= 10.6 || (strictInBounds.length <= 16 && z >= 9.0);
    const cellSize = z >= 14.4 ? 0 : z >= 13.4 ? 22 : z >= 11.8 ? 48 : 60;

    type Bucket = {
      stations: ActiveStation[];
      sumLon: number;
      sumLat: number;
      minPrice: number;
    };

    const buckets: Bucket[] = [];
    if (cellSize === 0 && others.length <= 85) {
      for (const st of others) {
        buckets.push({
          stations: [st],
          sumLon: st.lon,
          sumLat: st.lat,
          minPrice: st.price,
        });
      }
    } else {
      const effectiveCell = cellSize || 24;
      const grid = new Map<string, Bucket>();
      for (const st of others) {
        const pt = instance.project([st.lon, st.lat]);
        const key = `${Math.floor(pt.x / effectiveCell)}:${Math.floor(pt.y / effectiveCell)}`;
        const existing = grid.get(key);
        if (existing) {
          existing.stations.push(st);
          existing.sumLon += st.lon;
          existing.sumLat += st.lat;
          if (st.price < existing.minPrice) existing.minPrice = st.price;
        } else {
          grid.set(key, {
            stations: [st],
            sumLon: st.lon,
            sumLat: st.lat,
            minPrice: st.price,
          });
        }
      }
      buckets.push(...grid.values());
    }

    // Sort buckets so regular clusters/pins mount first and cheapest mount on top (higher z-index)
    buckets.sort((a, b) => {
      const aCheap = isCheapestPrice(a.minPrice) ? 1 : 0;
      const bCheap = isCheapestPrice(b.minPrice) ? 1 : 0;
      if (aCheap !== bCheap) return aCheap - bCheap;
      return b.minPrice - a.minPrice;
    });

    for (const bucket of buckets) {
      const n = bucket.stations.length;
      const cheap = isCheapestPrice(bucket.minPrice);

      if (n === 1 && showIndividualPins) {
        const st = bucket.stations[0];
        const el = buildPricePinElement(st, p.unit, cheap, false, () => {
          internalClickedKeyRef.current = st.key;
          currentProps.current.onFocusStation(st.key);
          instance.easeTo({
            center: [st.lon, st.lat],
            zoom: Math.max(instance.getZoom(), 13.0),
            duration: reduced ? 0 : 340,
          });
        });
        const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
          .setLngLat([st.lon, st.lat])
          .addTo(instance);
        stationMarkersRef.current.push(marker);
      } else {
        const cLon = bucket.sumLon / n;
        const cLat = bucket.sumLat / n;
        const el = buildClusterElement(
          n,
          bucket.minPrice,
          p.unit,
          cheap,
          () => {
            setHover(null);
            if (n === 1) {
              const lone = bucket.stations[0];
              internalClickedKeyRef.current = lone.key;
              currentProps.current.onFocusStation(lone.key);
              instance.easeTo({
                center: [lone.lon, lone.lat],
                zoom: Math.max(z + 2.5, 13.2),
                duration: reduced ? 0 : 450,
              });
              return;
            }
            const b = new maplibregl.LngLatBounds();
            bucket.stations.forEach(s => b.extend([s.lon, s.lat]));
            const span = Math.max(
              Math.abs(b.getEast() - b.getWest()),
              Math.abs(b.getNorth() - b.getSouth()),
            );
            if (span < 0.0012) {
              instance.easeTo({
                center: [cLon, cLat],
                zoom: Math.min(16, z + 2.6),
                duration: reduced ? 0 : 420,
              });
            } else {
              instance.fitBounds(b, {
                padding: 90,
                maxZoom: Math.max(z + 2.5, 13.2),
                duration: reduced ? 0 : 450,
              });
            }
          },
          ev => {
            const rect = containerRef.current?.getBoundingClientRect();
            if (!rect) return;
            setHover({
              eyebrow: cheap ? 'MENOR PREÇO NA REGIÃO' : 'AGRUPAMENTO DE POSTOS',
              name: `${count(n)} ${n === 1 ? 'posto' : 'postos'} nesta área`,
              x: ev.clientX - rect.left,
              y: ev.clientY - rect.top,
              clusterInfo: { count: n, minPrice: bucket.minPrice },
            });
          },
          () => {
            setHover(prev => (prev?.clusterInfo ? null : prev));
          },
        );
        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat([cLon, cLat])
          .addTo(instance);
        stationMarkersRef.current.push(marker);
      }
    }

    // Always render the focused station on top as a selected WA Price Callout Pin
    if (focused) {
      const cheap = isCheapestPrice(focused.price);
      const el = buildPricePinElement(focused, p.unit, cheap, true, () => {
        currentProps.current.onFocusStation(focused.key);
      });
      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
        .setLngLat([focused.lon, focused.lat])
        .addTo(instance);
      stationMarkersRef.current.push(marker);
    }
  };

  renderMarkersFnRef.current = renderStationMarkers;

  // Re-render station pins whenever station list, selection, visibility, or focused station changes
  useEffect(() => {
    renderStationMarkers();
  }, [
    ready,
    props.activeStations,
    props.showStations,
    props.selection.uf,
    props.focusedStationKey,
    props.unit,
  ]);

  // Resize cleanly when returning from Tendências / Dados subviews while preserving exact camera
  useEffect(() => {
    if (!props.visible || !ready || !mapRef.current) return;
    mapRef.current.resize();
    renderMarkersFnRef.current();
  }, [props.visible, ready]);

  // Smoothly fly to a station selected from the left sidebar or global search
  useEffect(() => {
    const instance = mapRef.current;
    if (!ready || !instance || !props.focusedStationKey) return;

    if (internalClickedKeyRef.current === props.focusedStationKey) {
      internalClickedKeyRef.current = null;
      return;
    }
    internalClickedKeyRef.current = null;

    const target = props.activeStations.find(s => s.key === props.focusedStationKey);
    if (!target) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    instance.easeTo({
      center: [target.lon, target.lat],
      zoom: Math.max(instance.getZoom(), 13.8),
      duration: reduced ? 0 : 480,
    });
  }, [ready, props.focusedStationKey, props.activeStations]);

  const handleRecenter = () => {
    const instance = mapRef.current;
    if (!instance) return;
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 480;

    if (props.selection.city && cityShapesRef.current) {
      const feat = cityShapesRef.current.features.find(
        f => String(f.properties.codarea) === props.selection.city,
      );
      if (feat) {
        instance.fitBounds(computeBounds(feat), { padding: 64, maxZoom: 11.8, duration });
        return;
      }
    }
    if (props.selection.uf && stateShapesRef.current) {
      const st = props.manifest.states.find(s => s.uf === props.selection.uf);
      const feat = stateShapesRef.current.features.find(
        f => String(f.properties.codarea) === st?.id,
      );
      if (feat) {
        instance.fitBounds(computeBounds(feat), { padding: 56, maxZoom: 8.2, duration });
        return;
      }
    }
    instance.fitBounds(BRASIL_BOUNDS, { padding: BRASIL_FIT_PADDING, duration });
  };

  const hoverDelta =
    hover?.row?.eligible && hover.reference
      ? (hover.row.p / hover.reference - 1) * 100
      : undefined;

  return (
    <div className="map-stage">
      <div
        ref={containerRef}
        className="map-canvas"
        role="region"
        aria-label="Mapa interativo de preços de combustíveis no Brasil"
      />

      {/* Top-left floating scope bar */}
      <div className="map-top-controls">
        {props.selection.uf && (
          <button
            type="button"
            className="map-pill-btn"
            onClick={() =>
              props.selection.city
                ? props.onSelect({ uf: props.selection.uf })
                : props.onSelect({})
            }
          >
            <ArrowLeft size={15} />
            <span>{props.selection.city ? `Voltar para ${props.selection.uf}` : 'Visão Brasil'}</span>
          </button>
        )}

        {props.selection.uf && (
          <button
            type="button"
            className={`map-pill-btn ${props.showStations ? 'active' : ''}`}
            aria-pressed={props.showStations}
            onClick={props.onToggleStations}
          >
            {props.showStations ? <Eye size={14} /> : <EyeOff size={14} />}
            <span>
              {props.loadingStations
                ? 'Carregando postos…'
                : `Postos (${count(props.activeStations.length)})`}
            </span>
          </button>
        )}

        {(loadingCities || props.loadingStations) && (
          <span className="map-loading-chip" role="status">
            <span className="spinner-sm" /> Atualizando mapa…
          </span>
        )}
      </div>

      {/* Compact Legend (Brasil view or low-zoom regional view) */}
      {(!props.selection.uf || zoom < 10.2) && showChoroplethLegend && (
        <aside className="wa-map-legend" aria-label="Legenda do mapa">
          <div className="wa-legend-head">
            <span>
              <Layers size={13} />{' '}
              {props.metric === 'comparison'
                ? `Desvio vs. ${props.selection.uf ? props.selection.uf : 'Brasil'}`
                : `Mediana (R$/${unitLabel(props.unit)})`}
            </span>
            <button
              type="button"
              className="legend-hide-btn"
              aria-label="Ocultar legenda"
              onClick={() => setShowChoroplethLegend(false)}
            >
              ×
            </button>
          </div>
          <div className={`wa-legend-ramp ${props.metric}`} />
          <div className="wa-legend-ticks">
            {props.metric === 'comparison' ? (
              <>
                <span>−15%</span>
                <span>0%</span>
                <span>+15%</span>
              </>
            ) : (
              <>
                <span>{moneyCompact(props.range[0])}</span>
                <span>{moneyCompact((props.range[0] + props.range[1]) / 2)}</span>
                <span>{moneyCompact(props.range[1])}</span>
              </>
            )}
          </div>
          {props.selection.uf && (
            <div className="wa-legend-pins">
              <span>
                <i className="dot-crimson" /> Menor preço
              </span>
              <span>
                <i className="dot-purple" /> Agrupamento
              </span>
              <span>
                <i className="dot-teal" /> Posto
              </span>
            </div>
          )}
        </aside>
      )}

      {!showChoroplethLegend && (!props.selection.uf || zoom < 10.2) && (
        <button
          type="button"
          className="wa-legend-reopen"
          onClick={() => setShowChoroplethLegend(true)}
        >
          <Layers size={14} /> Legenda
        </button>
      )}

      {/* FuelWatch WA Bottom-Right Floating Zoom Pill + Recenter Target */}
      <div className="wa-zoom-dock" aria-label="Controles de navegação do mapa">
        <div className="wa-zoom-pill">
          <button
            type="button"
            aria-label="Aproximar mapa"
            title="Aproximar"
            disabled={zoom >= MAX_MAP_ZOOM - 0.05}
            onClick={() => mapRef.current?.zoomIn()}
          >
            <Plus size={18} strokeWidth={2.3} />
          </button>
          <button
            type="button"
            aria-label="Afastar mapa"
            title="Afastar"
            disabled={zoom <= MIN_MAP_ZOOM + 0.05}
            onClick={() => mapRef.current?.zoomOut()}
          >
            <Minus size={18} strokeWidth={2.3} />
          </button>
        </div>
        <button
          type="button"
          className="wa-locate-btn"
          aria-label="Reenquadrar área selecionada"
          title="Reenquadrar mapa"
          onClick={handleRecenter}
        >
          <Crosshair size={18} strokeWidth={2.1} />
        </button>
      </div>

      {/* Attribution */}
      <div className="wa-map-attribution">
        {hasStreetTiles ? (
          <>
            <a href="https://openfreemap.org" target="_blank" rel="noreferrer">
              OpenFreeMap
            </a>{' '}
            · ©{' '}
            <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
              OpenStreetMap
            </a>{' '}
            · Malha IBGE · Dados ANP
          </>
        ) : (
          <>Malha oficial IBGE · Dados históricos ANP</>
        )}
      </div>

      {/* Hover Tooltip */}
      {hover && (
        <div
          className="wa-map-tooltip"
          style={{
            left: Math.min(
              hover.x + 16,
              (containerRef.current?.clientWidth || 500) - 255,
            ),
            top: Math.max(14, hover.y - 16),
          }}
        >
          <span className="eyebrow">{hover.eyebrow}</span>
          <strong>{hover.name}</strong>
          {hover.clusterInfo ? (
            <p className="tooltip-sub">
              A partir de <b className="text-crimson">{money(hover.clusterInfo.minPrice)}</b>/
              {unitLabel(props.unit)} · clique para aproximar
            </p>
          ) : hover.row ? (
            <>
              <div className="tooltip-price-line">
                <b>
                  {money(hover.row.p)}/{unitLabel(props.unit)}
                </b>
                {hoverDelta !== undefined && (
                  <em className={hoverDelta < 0 ? 'down' : hoverDelta > 0 ? 'up' : ''}>
                    {signedPercent(hoverDelta)} vs. {hover.referenceName}
                  </em>
                )}
              </div>
              <small>
                {count(hover.row.n)} postos · {count(hover.row.c)} coletas
              </small>
            </>
          ) : (
            <p className="tooltip-sub">Sem coleta da ANP nesta semana</p>
          )}
        </div>
      )}

      {(problem || props.stationError) && (
        <div className="map-error-toast" role="alert">
          <p>
            {problem ||
              'Não foi possível abrir o arquivo de postos desta UF. Os dados estaduais e municipais seguem disponíveis.'}
          </p>
          <button
            type="button"
            className="wa-btn-secondary"
            onClick={() => setRetry(v => v + 1)}
          >
            Tentar novamente
          </button>
        </div>
      )}
    </div>
  );
}

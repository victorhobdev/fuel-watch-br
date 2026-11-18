import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { type GeoJSONSource, type MapMouseEvent } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { ArrowLeft, Compass, Crosshair, Eye, EyeOff, Minus, Plus } from 'lucide-react';
import {
  count,
  date,
  getData,
  money,
  moneyCompact,
  NO_DATA_FILL,
  priceColor,
  signedPercent,
  unitLabel,
  type ActiveStation,
  type CityRow,
  type Manifest,
  type Metric,
  type Selection,
  type StateRow,
} from './data';

maplibregl.setWorkerUrl(workerUrl);

type PolyFeature = GeoJSON.Feature<
  GeoJSON.Geometry,
  { codarea: string; color?: string; selected?: boolean }
>;
type PolyCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, PolyFeature['properties']>;

type StationMarkerProps = {
  key: string;
  name: string;
  distributor: string;
  address: string;
  complement: string;
  neighborhood: string;
  cep: string;
  municipality: string;
  uf: string;
  accuracyMeters: number;
  origin: string;
  dataObtained: string;
  price: number;
  collections: number;
  deltaPercent?: number;
  color: string;
};
type StationMarkerFeature = GeoJSON.Feature<GeoJSON.Point, StationMarkerProps>;
type StationMarkerCollection = GeoJSON.FeatureCollection<GeoJSON.Point, StationMarkerProps>;

const EMPTY_POLYGONS: PolyCollection = { type: 'FeatureCollection', features: [] };
const EMPTY_STATIONS: StationMarkerCollection = { type: 'FeatureCollection', features: [] };

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
  productLabel: string;
  weekIso: string;
  onSelect: (selection: Selection) => void;
};

type HoverState = {
  eyebrow: string;
  name: string;
  row?: StateRow | CityRow;
  reference?: number;
  referenceName?: string;
  x: number;
  y: number;
  clusterCount?: number;
};

function buildPopupDOM(
  station: StationMarkerProps,
  unit: string,
  productLabel: string,
  weekIso: string,
): HTMLElement {
  const root = document.createElement('div');
  root.className = 'station-popup';

  const eyebrow = document.createElement('span');
  eyebrow.className = 'station-popup-eyebrow';
  eyebrow.textContent = `POSTO INDIVIDUAL · SEMANA ${date(weekIso)}`;
  root.append(eyebrow);

  const name = document.createElement('strong');
  name.className = 'station-popup-name';
  name.textContent = station.name;
  root.append(name);

  if (station.distributor) {
    const brand = document.createElement('span');
    brand.className = 'station-popup-brand';
    brand.textContent = station.distributor;
    root.append(brand);
  }

  const priceWrap = document.createElement('div');
  priceWrap.className = 'station-popup-price-row';

  const price = document.createElement('span');
  price.className = 'station-popup-price';
  price.textContent = `${money(station.price)} / ${unitLabel(unit)}`;
  priceWrap.append(price);

  if (station.deltaPercent !== undefined && Number.isFinite(station.deltaPercent)) {
    const badge = document.createElement('span');
    badge.className = `station-popup-delta ${station.deltaPercent > 0 ? 'up' : station.deltaPercent < 0 ? 'down' : ''}`;
    badge.textContent = `${signedPercent(station.deltaPercent)} vs. UF`;
    priceWrap.append(badge);
  }
  root.append(priceWrap);

  const samples = document.createElement('p');
  samples.className = 'station-popup-samples';
  samples.textContent = `${count(station.collections)} ${station.collections === 1 ? 'coleta' : 'coletas'} na semana · mediana de ${productLabel.toLowerCase()}`;
  root.append(samples);

  const street = [station.address, station.complement]
    .map(part => (part || '').trim())
    .filter(part => part && part !== '.' && part !== '-')
    .join(', ');
  const locality = [station.neighborhood, `${station.municipality} · ${station.uf}`, station.cep]
    .map(part => (part || '').trim())
    .filter(Boolean)
    .join(' · ');

  if (street) {
    const line = document.createElement('div');
    line.className = 'station-popup-address';
    line.textContent = street;
    root.append(line);
  }
  if (locality) {
    const line = document.createElement('div');
    line.className = 'station-popup-locality';
    line.textContent = locality;
    root.append(line);
  }

  const source = document.createElement('small');
  source.className = 'station-popup-source';
  source.textContent = `${station.origin || 'Cadastro ANP'} · obtido em ${station.dataObtained || 'data não informada'} · acurácia ${station.accuracyMeters} m · posição não validada pela ANP`;
  root.append(source);

  return root;
}

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

export default function AtlasMap(props: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const stateShapesRef = useRef<PolyCollection | null>(null);
  const currentProps = useRef(props);
  currentProps.current = props;

  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<HoverState | null>(null);
  const [problem, setProblem] = useState('');
  const [loadingCities, setLoadingCities] = useState(false);
  const [zoom, setZoom] = useState(3.4);
  const [retry, setRetry] = useState(0);

  const stateLabelsRef = useRef<maplibregl.Marker[]>([]);
  const cityLabelsRef = useRef<maplibregl.Marker[]>([]);
  const cameraSelectionRef = useRef('');
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const popupKeyRef = useRef('');
  const popupPinnedRef = useRef(false);
  const internalStationClickRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current) return;
    let alive = true;
    let instance: maplibregl.Map;
    try {
      instance = new maplibregl.Map({
        container: containerRef.current,
        attributionControl: false,
        center: [-52.5, -14.2],
        zoom: 3.4,
        minZoom: 2.3,
        maxZoom: 13.5,
        maxPitch: 0,
        renderWorldCopies: false,
        style: {
          version: 8,
          sources: {},
          layers: [
            {
              id: 'background',
              type: 'background',
              paint: { 'background-color': '#060910' },
            },
          ],
        },
      });
    } catch {
      setProblem('Seu navegador não conseguiu iniciar o motor WebGL do mapa. A busca e os painéis laterais continuam disponíveis.');
      return;
    }

    mapRef.current = instance;
    instance.dragRotate.disable();
    instance.touchZoomRotate.disableRotation();
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    instance.on('load', async () => {
      try {
        const shapes = await getData<PolyCollection>(props.manifest.geometry.statesFile);
        if (!alive) return;
        stateShapesRef.current = shapes;

        const grid: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
        for (let lng = -85; lng <= -25; lng += 5) {
          grid.features.push({
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates: [[lng, -40], [lng, 12]] },
          });
        }
        for (let lat = -35; lat <= 10; lat += 5) {
          grid.features.push({
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates: [[-85, lat], [-25, lat]] },
          });
        }

        instance.addSource('grid', { type: 'geojson', data: grid });
        instance.addLayer({
          id: 'grid',
          type: 'line',
          source: 'grid',
          paint: { 'line-color': '#94a3b8', 'line-opacity': 0.06, 'line-width': 1 },
        });

        instance.addSource('states', { type: 'geojson', data: shapes });
        instance.addLayer({
          id: 'states-fill',
          type: 'fill',
          source: 'states',
          paint: {
            'fill-color': ['coalesce', ['get', 'color'], NO_DATA_FILL],
            'fill-opacity': 0.95,
          },
        });
        instance.addLayer({
          id: 'states-line',
          type: 'line',
          source: 'states',
          paint: { 'line-color': '#080d18', 'line-width': 1.1, 'line-opacity': 0.92 },
        });
        instance.addLayer({
          id: 'states-selected',
          type: 'line',
          source: 'states',
          filter: ['==', ['get', 'selected'], true],
          paint: { 'line-color': '#f8fafc', 'line-width': 2.2 },
        });

        instance.addSource('cities', { type: 'geojson', data: EMPTY_POLYGONS });
        instance.addLayer({
          id: 'cities-fill',
          type: 'fill',
          source: 'cities',
          paint: {
            'fill-color': ['coalesce', ['get', 'color'], NO_DATA_FILL],
            'fill-opacity': 0.96,
          },
        });
        instance.addLayer({
          id: 'cities-line',
          type: 'line',
          source: 'cities',
          paint: { 'line-color': '#080d18', 'line-width': 0.85 },
        });
        instance.addLayer({
          id: 'city-selected',
          type: 'line',
          source: 'cities',
          filter: ['==', ['get', 'selected'], true],
          paint: { 'line-color': '#ffffff', 'line-width': 2.6 },
        });

        instance.addSource('stations', {
          type: 'geojson',
          data: EMPTY_STATIONS,
          cluster: true,
          clusterRadius: 32,
          clusterMaxZoom: 9,
        });
        instance.addLayer({
          id: 'station-clusters-halo',
          type: 'circle',
          source: 'stations',
          minzoom: 4.2,
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': '#38bdf8',
            'circle-radius': ['step', ['get', 'point_count'], 16, 15, 20, 60, 25],
            'circle-opacity': 0.22,
          },
        });
        instance.addLayer({
          id: 'station-clusters',
          type: 'circle',
          source: 'stations',
          minzoom: 4.2,
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': '#0284c7',
            'circle-radius': ['step', ['get', 'point_count'], 10.5, 15, 13.5, 60, 17],
            'circle-opacity': 0.95,
            'circle-stroke-color': '#e0f2fe',
            'circle-stroke-width': 1.6,
          },
        });
        instance.addLayer({
          id: 'station-points',
          type: 'circle',
          source: 'stations',
          minzoom: 8.8,
          filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': ['get', 'color'],
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8.8, 4.6, 12, 6.8],
            'circle-opacity': 0.97,
            'circle-stroke-color': '#0b111e',
            'circle-stroke-width': 1.5,
          },
        });
        instance.addLayer({
          id: 'station-focused',
          type: 'circle',
          source: 'stations',
          filter: ['==', ['get', 'key'], ''],
          paint: {
            'circle-color': ['get', 'color'],
            'circle-radius': 8.5,
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2.8,
          },
        });

        instance.on('mousemove', (event: MapMouseEvent) => {
          const p = currentProps.current;
          if (popupPinnedRef.current) return;
          const queryLayers = p.selection.uf
            ? p.showStations
              ? ['station-points', 'station-clusters', 'cities-fill', 'states-fill']
              : ['cities-fill', 'states-fill']
            : ['states-fill'];
          const features = instance.queryRenderedFeatures(event.point, { layers: queryLayers });

          const station = features.find(f => f.layer.id === 'station-points') as
            | StationMarkerFeature
            | undefined;
          if (station) {
            const [lon, lat] = station.geometry.coordinates;
            if (popupKeyRef.current !== station.properties.key) {
              popupRef.current?.remove();
              const popup = new maplibregl.Popup({
                closeButton: false,
                closeOnClick: false,
                maxWidth: '320px',
                className: 'atlas-station-popup hover-mode',
              })
                .setLngLat([lon, lat])
                .setDOMContent(
                  buildPopupDOM(station.properties, p.unit, p.productLabel, p.weekIso),
                )
                .addTo(instance);
              popupRef.current = popup;
              popupKeyRef.current = station.properties.key;
            }
            setHover(null);
            instance.getCanvas().style.cursor = 'pointer';
            return;
          }

          const cluster = features.find(f => f.layer.id === 'station-clusters');
          if (cluster) {
            popupRef.current?.remove();
            popupKeyRef.current = '';
            instance.getCanvas().style.cursor = 'pointer';
            setHover({
              eyebrow: 'AGRUPAMENTO DE POSTOS',
              name: `${count(Number(cluster.properties.point_count))} postos na região`,
              x: event.point.x,
              y: event.point.y,
              clusterCount: Number(cluster.properties.point_count),
            });
            return;
          }

          popupRef.current?.remove();
          popupRef.current = null;
          popupKeyRef.current = '';

          const cityFeature = features.find(f => f.layer.id === 'cities-fill');
          const poly = cityFeature || features.find(f => f.layer.id === 'states-fill');
          if (!poly) {
            setHover(null);
            instance.getCanvas().style.cursor = '';
            return;
          }

          const id = String(poly.properties.codarea);
          const isCity = Boolean(cityFeature);
          instance.getCanvas().style.cursor = 'pointer';

          if (isCity) {
            const place = p.manifest.cities.find(c => c.id === id);
            const row = p.cities.find(c => c.id === id);
            setHover({
              eyebrow: `MUNICÍPIO · ${place?.uf || ''}`,
              name: place?.name || id,
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
          if (!popupPinnedRef.current) {
            popupRef.current?.remove();
            popupRef.current = null;
            popupKeyRef.current = '';
          }
        });

        instance.on('click', (event: MapMouseEvent) => {
          const p = currentProps.current;
          const queryLayers = p.selection.uf
            ? p.showStations
              ? ['station-points', 'station-clusters', 'cities-fill', 'states-fill']
              : ['cities-fill', 'states-fill']
            : ['states-fill'];
          const features = instance.queryRenderedFeatures(event.point, { layers: queryLayers });

          const station = features.find(f => f.layer.id === 'station-points') as
            | StationMarkerFeature
            | undefined;
          if (station) {
            const [lon, lat] = station.geometry.coordinates;
            popupRef.current?.remove();
            const popup = new maplibregl.Popup({
              closeButton: true,
              closeOnClick: true,
              maxWidth: '320px',
              className: 'atlas-station-popup pinned-mode',
            })
              .setLngLat([lon, lat])
              .setDOMContent(
                buildPopupDOM(station.properties, p.unit, p.productLabel, p.weekIso),
              )
              .addTo(instance);
            popupRef.current = popup;
            popupKeyRef.current = station.properties.key;
            popupPinnedRef.current = true;
            internalStationClickRef.current = true;
            p.onFocusStation(station.properties.key);
            popup.on('close', () => {
              if (popupRef.current === popup) {
                popupRef.current = null;
                popupKeyRef.current = '';
                popupPinnedRef.current = false;
                currentProps.current.onFocusStation(null);
              }
            });
            setHover(null);
            return;
          }

          const cluster = features.find(f => f.layer.id === 'station-clusters');
          if (cluster) {
            popupRef.current?.remove();
            popupRef.current = null;
            popupPinnedRef.current = false;
            p.onFocusStation(null);
            const source = instance.getSource('stations') as GeoJSONSource;
            const coordinates = (cluster.geometry as GeoJSON.Point).coordinates as [number, number];
            void source
              .getClusterExpansionZoom(Number(cluster.properties.cluster_id))
              .then(nextZoom =>
                instance.easeTo({
                  center: coordinates,
                  zoom: Math.min(nextZoom + 0.35, 12.5),
                  duration: reduced ? 0 : 420,
                }),
              );
            setHover(null);
            return;
          }

          popupRef.current?.remove();
          popupRef.current = null;
          popupKeyRef.current = '';
          popupPinnedRef.current = false;
          p.onFocusStation(null);

          const city = features.find(f => f.layer.id === 'cities-fill');
          if (city) {
            const place = p.manifest.cities.find(c => c.id === String(city.properties.codarea));
            if (place) p.onSelect({ uf: place.uf, city: place.id });
            return;
          }

          const statePoly = features.find(f => f.layer.id === 'states-fill');
          if (statePoly) {
            const state = p.manifest.states.find(s => s.id === String(statePoly.properties.codarea));
            if (state) p.onSelect({ uf: state.uf });
          }
        });

        instance.on('zoomend', () => setZoom(instance.getZoom()));
        const observer = new ResizeObserver(() => instance.resize());
        observer.observe(containerRef.current!);
        instance.once('remove', () => observer.disconnect());
        instance.fitBounds(
          [
            [-74.2, -34.0],
            [-34.0, 5.5],
          ],
          { padding: { top: 86, right: 44, bottom: 96, left: 44 }, duration: reduced ? 0 : 650 },
        );
        setReady(true);
      } catch {
        if (alive) {
          setProblem('A malha cartográfica do IBGE não pôde ser carregada. Tente novamente.');
        }
      }
    });

    return () => {
      alive = false;
      stateLabelsRef.current.forEach(m => m.remove());
      cityLabelsRef.current.forEach(m => m.remove());
      stateLabelsRef.current = [];
      cityLabelsRef.current = [];
      instance.remove();
      mapRef.current = null;
    };
  }, [props.manifest]);

  // Update State Polygons & State Labels
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

    (mapRef.current.getSource('states') as GeoJSONSource).setData(updated);
    mapRef.current.setPaintProperty('states-fill', 'fill-opacity', p.selection.uf ? 0.2 : 0.95);

    stateLabelsRef.current.forEach(m => m.remove());
    stateLabelsRef.current = [];

    if (!p.selection.uf) {
      updated.features.forEach(feature => {
        const state = p.manifest.states.find(s => s.id === String(feature.properties.codarea));
        if (!state) return;
        const row = p.states.find(r => r.uf === state.uf);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'map-state-pill';
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
  }, [ready, props.states, props.range, props.metric, props.selection.uf, props.national, props.manifest]);

  // Update Municipality Polygons, Camera & City Labels
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    let alive = true;
    const instance = mapRef.current;
    const { selection, manifest } = props;
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 620;
    const cameraKey = `${selection.uf || 'BR'}:${selection.city || ''}`;
    const shouldMoveCamera = cameraKey !== cameraSelectionRef.current;
    cameraSelectionRef.current = cameraKey;

    cityLabelsRef.current.forEach(m => m.remove());
    cityLabelsRef.current = [];
    setProblem('');

    if (!selection.uf) {
      (instance.getSource('cities') as GeoJSONSource).setData(EMPTY_POLYGONS);
      if (shouldMoveCamera) {
        instance.fitBounds(
          [
            [-74.2, -34.0],
            [-34.0, 5.5],
          ],
          { padding: { top: 86, right: 44, bottom: 96, left: 44 }, duration },
        );
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
        padding: { top: 92, right: 56, bottom: 96, left: 56 },
        duration,
        maxZoom: 8,
      });
    }

    setLoadingCities(true);
    getData<PolyCollection>(manifest.geometry.cityFiles.replace('{uf}', selection.uf))
      .then(shapes => {
        if (!alive) return;
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
              },
            };
          }),
        };

        (instance.getSource('cities') as GeoJSONSource).setData(colored);
        const selectedCityFeature = colored.features.find(
          f => String(f.properties.codarea) === selection.city,
        );
        if (selectedCityFeature && shouldMoveCamera) {
          instance.fitBounds(computeBounds(selectedCityFeature), {
            padding: { top: 96, right: 64, bottom: 100, left: 64 },
            duration,
            maxZoom: 10.2,
          });
        }

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
          if (labelled.length >= 7) break;
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
          btn.setAttribute('aria-label', `Selecionar município ${c.name}`);
          btn.addEventListener('click', ev => {
            ev.stopPropagation();
            currentProps.current.onSelect({ uf: c.uf, city: c.id });
          });
          cityLabelsRef.current.push(
            new maplibregl.Marker({ element: btn }).setLngLat([c.lon, c.lat]).addTo(instance),
          );
        });
        setLoadingCities(false);
      })
      .catch(() => {
        if (alive) {
          setProblem('Não foi possível carregar os polígonos municipais desta UF.');
          setLoadingCities(false);
        }
      });

    return () => {
      alive = false;
    };
  }, [
    ready,
    props.selection.uf,
    props.selection.city,
    props.cities,
    props.metric,
    props.range,
    props.manifest,
    retry,
  ]);

  // Update Station GeoJSON Layer & Layer Visibility
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const instance = mapRef.current;
    const source = instance.getSource('stations') as GeoJSONSource;

    const visibility = props.showStations && props.selection.uf ? 'visible' : 'none';
    for (const layerId of [
      'station-clusters-halo',
      'station-clusters',
      'station-points',
      'station-focused',
    ]) {
      if (instance.getLayer(layerId)) {
        instance.setLayoutProperty(layerId, 'visibility', visibility);
      }
    }

    if (!props.selection.uf || !props.activeStations.length) {
      source.setData(EMPTY_STATIONS);
      popupRef.current?.remove();
      popupRef.current = null;
      popupKeyRef.current = '';
      popupPinnedRef.current = false;
      return;
    }

    const features: StationMarkerFeature[] = props.activeStations.map(st => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [st.lon, st.lat] },
      properties: {
        key: st.key,
        name: st.properties.name,
        distributor: st.properties.distributor,
        address: st.properties.address,
        complement: st.properties.complement,
        neighborhood: st.properties.neighborhood,
        cep: st.properties.cep,
        municipality: st.properties.municipality,
        uf: st.properties.uf,
        accuracyMeters: st.properties.accuracyMeters,
        origin: st.properties.origin,
        dataObtained: st.properties.dataObtained,
        price: st.price,
        collections: st.collections,
        deltaPercent: st.deltaPercent,
        color: st.color,
      },
    }));

    source.setData({ type: 'FeatureCollection', features });
  }, [ready, props.selection.uf, props.activeStations, props.showStations]);

  // Sync Focused Station from Side Explorer / Selection
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const instance = mapRef.current;
    instance.setFilter('station-focused', ['==', ['get', 'key'], props.focusedStationKey || '']);

    if (!props.focusedStationKey) {
      if (popupPinnedRef.current) {
        popupRef.current?.remove();
        popupRef.current = null;
        popupKeyRef.current = '';
        popupPinnedRef.current = false;
      }
      return;
    }

    const target = props.activeStations.find(st => st.key === props.focusedStationKey);
    if (!target) {
      popupRef.current?.remove();
      popupRef.current = null;
      popupKeyRef.current = '';
      popupPinnedRef.current = false;
      return;
    }

    const wasInternalClick = internalStationClickRef.current;
    internalStationClickRef.current = false;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!wasInternalClick) {
      instance.easeTo({
        center: [target.lon, target.lat],
        zoom: Math.max(instance.getZoom(), 11.2),
        duration: reduced ? 0 : 520,
      });
    }

    popupRef.current?.remove();
    const markerProps: StationMarkerProps = {
      key: target.key,
      name: target.properties.name,
      distributor: target.properties.distributor,
      address: target.properties.address,
      complement: target.properties.complement,
      neighborhood: target.properties.neighborhood,
      cep: target.properties.cep,
      municipality: target.properties.municipality,
      uf: target.properties.uf,
      accuracyMeters: target.properties.accuracyMeters,
      origin: target.properties.origin,
      dataObtained: target.properties.dataObtained,
      price: target.price,
      collections: target.collections,
      deltaPercent: target.deltaPercent,
      color: target.color,
    };

    const popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '320px',
      className: 'atlas-station-popup pinned-mode',
    })
      .setLngLat([target.lon, target.lat])
      .setDOMContent(buildPopupDOM(markerProps, props.unit, props.productLabel, props.weekIso))
      .addTo(instance);

    popupRef.current = popup;
    popupKeyRef.current = target.key;
    popupPinnedRef.current = true;
    popup.on('close', () => {
      if (popupRef.current === popup) {
        popupRef.current = null;
        popupKeyRef.current = '';
        popupPinnedRef.current = false;
        currentProps.current.onFocusStation(null);
      }
    });
  }, [ready, props.focusedStationKey, props.activeStations, props.unit, props.productLabel, props.weekIso]);

  const selectedState = props.manifest.states.find(s => s.uf === props.selection.uf);
  const selectedCity = props.manifest.cities.find(c => c.id === props.selection.city);
  const hoverDelta =
    hover?.row && hover.reference && hover.row.eligible
      ? (hover.row.p / hover.reference - 1) * 100
      : undefined;

  const hasCoverage = props.selection.uf
    ? props.cities.some(
        c => props.manifest.cities.find(place => place.id === c.id)?.uf === props.selection.uf,
      )
    : props.states.length > 0;

  const containerW = containerRef.current?.clientWidth || 720;
  const containerH = containerRef.current?.clientHeight || 580;

  return (
    <div className="map-stage">
      <div
        ref={containerRef}
        className="map-canvas"
        aria-label="Mapa geográfico interativo de preços de combustíveis no Brasil"
      />

      <div className="map-hud-top-left">
        {props.selection.uf && (
          <div className="map-back-bar">
            <button
              type="button"
              className="map-pill-btn"
              onClick={() =>
                props.selection.city && props.selection.uf
                  ? props.onSelect({ uf: props.selection.uf })
                  : props.onSelect({})
              }
            >
              <ArrowLeft size={14} />
              <span>
                {props.selection.city ? `Voltar para ${selectedState?.uf}` : 'Voltar ao Brasil'}
              </span>
            </button>
            {props.selection.city && (
              <button
                type="button"
                className="map-pill-btn ghost"
                onClick={() => props.onSelect({})}
              >
                Brasil
              </button>
            )}
          </div>
        )}

        <div className="map-context-title">
          <span className="eyebrow accent">
            {selectedCity
              ? `RECORTE MUNICIPAL · ${selectedCity.uf}`
              : selectedState
                ? `UNIDADE DA FEDERAÇÃO · ${selectedState.region.toUpperCase()}`
                : 'PANORAMA GEOGRÁFICO · 27 UFs'}
          </span>
          <h2>{selectedCity?.name || selectedState?.name || 'Brasil — distribuição regional'}</h2>
          <p>
            {props.selection.uf
              ? !props.showStations
                ? 'Camada de postos oculta. Clique em um município para inspecionar.'
                : zoom < 8.8
                  ? 'Círculos agrupam postos localizados; aproxime ou clique para individualizar.'
                  : 'Cada ponto representa a mediana semanal de um posto localizado.'
              : 'Passe o cursor sobre os estados ou clique em uma UF para abrir municípios e postos.'}
          </p>
        </div>
      </div>

      <div className="map-hud-top-right">
        {props.selection.uf && (
          <button
            type="button"
            className={`map-station-toggle ${props.showStations ? 'active' : ''}`}
            aria-pressed={props.showStations}
            onClick={props.onToggleStations}
          >
            {props.showStations ? <Eye size={15} /> : <EyeOff size={15} />}
            <span>
              Postos ({count(props.activeStations.length)})
            </span>
          </button>
        )}
        <div className="map-compass" aria-hidden="true">
          <Compass size={20} strokeWidth={1.5} />
          <span>N</span>
        </div>
      </div>

      {!ready && !problem && (
        <div className="map-init-overlay" role="status">
          <span className="spinner" />
          <span>Carregando malha cartográfica IBGE…</span>
        </div>
      )}

      {(loadingCities || props.loadingStations) && (
        <div className="map-status-toast" role="status">
          <span className="spinner" />
          <span>
            {loadingCities && props.loadingStations
              ? 'Carregando malha municipal e postos…'
              : loadingCities
                ? 'Carregando malha municipal…'
                : 'Carregando postos localizados…'}
          </span>
        </div>
      )}

      {problem && (
        <div className="map-error-toast" role="alert">
          <span>{problem}</span>
          {ready && (
            <button type="button" onClick={() => setRetry(v => v + 1)}>
              Tentar novamente
            </button>
          )}
        </div>
      )}

      {hover && (
        <div
          className="map-tooltip"
          style={{
            left: Math.min(hover.x + 18, Math.max(16, containerW - 268)),
            top: Math.max(16, Math.min(hover.y - 84, containerH - 188)),
          }}
        >
          <span className="eyebrow accent">{hover.eyebrow}</span>
          <strong>{hover.name}</strong>
          {hover.clusterCount !== undefined ? (
            <p className="tooltip-meta">
              Clique para expandir o agrupamento e inspecionar postos individuais.
            </p>
          ) : hover.row ? (
            <>
              <div className="tooltip-price-row">
                <span className="tooltip-price">
                  {money(hover.row.p)} <small>/ {unitLabel(props.unit)}</small>
                </span>
                {hoverDelta !== undefined && (
                  <span
                    className={`delta-chip ${hoverDelta > 0 ? 'up' : hoverDelta < 0 ? 'down' : ''}`}
                  >
                    {signedPercent(hoverDelta)} vs. {hover.referenceName}
                  </span>
                )}
              </div>
              <div className="tooltip-stats">
                <span>
                  {count(hover.row.n)} {hover.row.n === 1 ? 'posto' : 'postos'} ·{' '}
                  {count(hover.row.c)} {hover.row.c === 1 ? 'coleta' : 'coletas'}
                </span>
                <span>
                  Extremos: {money(hover.row.lo)} — {money(hover.row.hi)}
                </span>
                {hoverDelta === undefined && (
                  <span className="tooltip-warn">Base insuficiente p/ comparação</span>
                )}
              </div>
              <span className="tooltip-cta">Clique para selecionar →</span>
            </>
          ) : (
            <p className="tooltip-meta">Sem coleta registrada neste combustível e semana.</p>
          )}
        </div>
      )}

      <div className="map-zoom-controls" role="group" aria-label="Controles de navegação do mapa">
        <button
          type="button"
          title="Aproximar"
          aria-label="Aproximar mapa"
          onClick={() => mapRef.current?.zoomIn()}
        >
          <Plus size={17} />
        </button>
        <button
          type="button"
          title="Afastar"
          aria-label="Afastar mapa"
          onClick={() => mapRef.current?.zoomOut()}
        >
          <Minus size={17} />
        </button>
        <span className="divider" />
        <button
          type="button"
          title="Enquadrar o Brasil"
          aria-label="Voltar à visão nacional do Brasil"
          onClick={() => {
            props.onSelect({});
            cameraSelectionRef.current = '';
            mapRef.current?.fitBounds(
              [
                [-74.2, -34.0],
                [-34.0, 5.5],
              ],
              { padding: 60, duration: 0 },
            );
          }}
        >
          <Crosshair size={17} />
        </button>
      </div>

      <div className="map-legend-card" aria-label="Legenda cromática do mapa">
        {hasCoverage ? (
          <>
            <div className="legend-head">
              <span>
                {props.metric === 'price'
                  ? `Mediana semanal (R$/${unitLabel(props.unit)})`
                  : `Desvio vs. ${props.selection.uf ? 'UF' : 'Brasil'} (±15%)`}
              </span>
              <span className="legend-nodata">
                <i /> Sem coleta{props.metric === 'comparison' ? ' / s/ base' : ''}
              </span>
            </div>
            <div
              className={`legend-bar ${props.metric === 'comparison' ? 'diverging' : 'sequential'}`}
            />
            <div className="legend-ticks">
              <b>
                {props.metric === 'price'
                  ? moneyCompact(props.range[0])
                  : `≤ −15%`}
              </b>
              <span>
                {props.metric === 'price'
                  ? 'menor → maior'
                  : '0% (em linha)'}
              </span>
              <b>
                {props.metric === 'price'
                  ? moneyCompact(props.range[1])
                  : `≥ +15%`}
              </b>
            </div>
          </>
        ) : (
          <span className="legend-empty">Nenhuma coleta registrada neste recorte.</span>
        )}
      </div>

      <div className="map-provenance-card">
        <div className="prov-row">
          <span className="prov-dot poly" />
          <span>
            {props.selection.uf ? 'Municípios observados (IBGE)' : '27 Unidades da Federação (IBGE)'}
          </span>
        </div>
        {props.selection.uf && props.showStations && (
          <div className="prov-row">
            <span className="prov-dot station" />
            <span>
              {props.loadingStations
                ? 'Carregando postos…'
                : props.stationError
                  ? 'Cadastro de postos indisponível'
                  : props.activeStations.length === 0
                    ? 'Nenhum posto georreferenciado na semana'
                    : `${count(props.activeStations.length)} ${props.activeStations.length === 1 ? 'posto' : 'postos'} com coleta e coordenada`}
            </span>
          </div>
        )}
        <small>
          {props.selection.uf && props.activeStations.length > 0 && props.manifest.stationLayer
            ? `Coordenadas: Cadastro ANP (${date(props.manifest.stationLayer.snapshotAt)}) · posição não validada`
            : 'Fonte: Série Histórica ANP · Reconciliado no Microsoft Fabric'}
        </small>
      </div>
    </div>
  );
}

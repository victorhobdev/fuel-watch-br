import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { type GeoJSONSource, type MapMouseEvent } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { Crosshair, Minus, Plus, Compass } from 'lucide-react';
import { getData, count, date, money, priceColor, unitLabel, type Manifest, type StateRow, type CityRow, type Selection, type Metric, type StationFile, type StationProperties } from './data';

maplibregl.setWorkerUrl(workerUrl);

type Feature = GeoJSON.Feature<GeoJSON.Geometry, { codarea: string; color?: string; selected?: boolean }>;
type Collection = GeoJSON.FeatureCollection<GeoJSON.Geometry, Feature['properties']>;
type Props = {
  manifest: Manifest; states: StateRow[]; cities: CityRow[]; selection: Selection; metric: Metric;
  national?: number; range: [number, number]; unit: string; productId: string; weekIndex: number; onSelect: (s: Selection) => void;
};
type Hover = { name: string; row?: StateRow | CityRow; reference?: number; x: number; y: number; city: boolean; clusterCount?: number };
type StationMapProperties = Omit<StationProperties, 'prices'> & { price: number; collections: number; color: string };
type StationMapFeature = GeoJSON.Feature<GeoJSON.Point, StationMapProperties>;
type StationMapCollection = GeoJSON.FeatureCollection<GeoJSON.Point, StationMapProperties>;
const emptyStationData: StationMapCollection = { type: 'FeatureCollection', features: [] };

function stationPopupContent(p: StationMapProperties, props: Props): HTMLElement {
  const root = document.createElement('div'); root.className = 'station-info';
  const eyebrow = document.createElement('span'); eyebrow.className = 'eyebrow';
  eyebrow.textContent = `PREÇO DO POSTO · ${date(props.manifest.weeks[props.weekIndex])}`;
  root.append(eyebrow);
  const name = document.createElement('strong'); name.className = 'station-name'; name.textContent = p.name;
  root.append(name);
  if (p.distributor) { const brand = document.createElement('span'); brand.className = 'station-brand'; brand.textContent = p.distributor; root.append(brand); }
  const price = document.createElement('div'); price.className = 'station-price';
  price.textContent = `${money(p.price)} / ${unitLabel(props.unit)}`; root.append(price);
  const samples = document.createElement('p'); samples.className = 'station-samples';
  samples.textContent = `${count(p.collections)} coletas · mediana semanal de ${props.manifest.products.find(x => x.id === props.productId)?.label.toLowerCase() || 'combustível'}`;
  root.append(samples);
  const address = [p.address, p.complement].filter(Boolean).join(', ');
  const locality = [p.neighborhood, `${p.municipality} · ${p.uf}`, p.cep].filter(Boolean).join(' · ');
  if (address) { const line = document.createElement('div'); line.className = 'station-address'; line.textContent = address; root.append(line); }
  if (locality) { const line = document.createElement('div'); line.className = 'station-locality'; line.textContent = locality; root.append(line); }
  const accuracy = document.createElement('small'); accuracy.className = 'station-source';
  accuracy.textContent = `${p.origin || 'Cadastro ANP'} · posição obtida ${p.dataObtained || 'sem data'} · acurácia informada ${p.accuracyMeters} m · não validada`;
  root.append(accuracy);
  return root;
}

function bounds(feature: GeoJSON.Feature | Collection): maplibregl.LngLatBounds {
  const b = new maplibregl.LngLatBounds();
  function walk(coords: unknown): void {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === 'number') b.extend(coords as [number, number]);
    else coords.forEach(walk);
  }
  const features = feature.type === 'FeatureCollection' ? feature.features : [feature];
  features.forEach(f => { if (f.geometry.type !== 'GeometryCollection') walk(f.geometry.coordinates); });
  return b;
}

export default function AtlasMap(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const stateShapes = useRef<Collection | null>(null);
  const current = useRef(props); current.current = props;
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<Hover | null>(null);
  const [problem, setProblem] = useState('');
  const [loadingCities, setLoadingCities] = useState(false);
  const [stationFile, setStationFile] = useState<StationFile | null>(null);
  const [loadingStations, setLoadingStations] = useState(false);
  const [stationError, setStationError] = useState(false);
  const [stationCount, setStationCount] = useState(0);
  const [zoom, setZoom] = useState(3);
  const [retry, setRetry] = useState(0);
  const labels = useRef<maplibregl.Marker[]>([]);
  const cityLabels = useRef<maplibregl.Marker[]>([]);
  const cameraSelection = useRef('');
  const stationPopup = useRef<maplibregl.Popup | null>(null);
  const stationPopupKey = useRef('');
  const stationPopupPinned = useRef(false);

  useEffect(() => {
    if (!container.current) return;
    let alive = true;
    let instance: maplibregl.Map;
    try {
      instance = new maplibregl.Map({ container: container.current, attributionControl: false, center: [-53, -14], zoom: 3,
        minZoom: 2, maxZoom: 12, maxPitch: 0, renderWorldCopies: false,
        style: { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#0b0f18' } }] } });
    } catch { setProblem('Seu navegador não conseguiu iniciar o mapa. A busca e a lista continuam disponíveis.'); return; }
    map.current = instance;
    instance.dragRotate.disable(); instance.touchZoomRotate.disableRotation();
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    instance.on('load', async () => {
      try {
        const shapes = await getData<Collection>(props.manifest.geometry.statesFile);
        if (!alive) return;
        stateShapes.current = shapes;
        const grid: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
        for (let lng = -90; lng <= -20; lng += 5) grid.features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[lng, -45], [lng, 15]] } });
        for (let lat = -40; lat <= 15; lat += 5) grid.features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[-90, lat], [-20, lat]] } });
        instance.addSource('grid', { type: 'geojson', data: grid });
        instance.addLayer({ id: 'grid', type: 'line', source: 'grid', paint: { 'line-color': '#99aacc', 'line-opacity': 0.045, 'line-width': 1 } });
        instance.addSource('states', { type: 'geojson', data: shapes });
        instance.addLayer({ id: 'states-fill', type: 'fill', source: 'states', paint: { 'fill-color': ['coalesce', ['get', 'color'], '#293142'], 'fill-opacity': 1 } });
        instance.addLayer({ id: 'states-line', type: 'line', source: 'states', paint: { 'line-color': '#11182b', 'line-width': 0.8, 'line-opacity': 0.8 } });
        instance.addLayer({ id: 'states-selected', type: 'line', source: 'states', filter: ['==', ['get', 'selected'], true], paint: { 'line-color': '#ffffff', 'line-width': 2.4 } });
        instance.addSource('cities', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        instance.addLayer({ id: 'cities-fill', type: 'fill', source: 'cities', paint: { 'fill-color': ['coalesce', ['get', 'color'], '#293142'], 'fill-opacity': 0.97 } });
        instance.addLayer({ id: 'cities-line', type: 'line', source: 'cities', paint: { 'line-color': '#11182b', 'line-width': 0.8 } });
        instance.addLayer({ id: 'city-selected', type: 'line', source: 'cities', filter: ['==', ['get', 'selected'], true], paint: { 'line-color': '#ffffff', 'line-width': 2.5 } });
        instance.addSource('stations', { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, cluster: true, clusterRadius: 30, clusterMaxZoom: 9 });
        instance.addLayer({ id: 'station-clusters', type: 'circle', source: 'stations', minzoom: 4.5, filter: ['has', 'point_count'], paint: { 'circle-color': '#2f63ff', 'circle-radius': ['step', ['get', 'point_count'], 11, 12, 14, 50, 17], 'circle-opacity': 0.92, 'circle-stroke-color': '#f5f7ff', 'circle-stroke-width': 1.3 } });
        instance.addLayer({ id: 'station-points', type: 'circle', source: 'stations', minzoom: 9, filter: ['!', ['has', 'point_count']], paint: { 'circle-color': ['get', 'color'], 'circle-radius': 5, 'circle-opacity': 0.97, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.4 } });
        instance.on('mousemove', (event: MapMouseEvent) => {
          const p = current.current;
          if (stationPopupPinned.current) return;
          const layers = p.selection.uf ? ['station-points', 'station-clusters', 'cities-fill', 'states-fill'] : ['states-fill'];
          const features = instance.queryRenderedFeatures(event.point, { layers });
          const station = features.find(f => f.layer.id === 'station-points') as StationMapFeature | undefined;
          if (station) {
            const [longitude, latitude] = station.geometry.coordinates;
            const key = `${station.properties.name}:${station.properties.address}:${longitude}:${latitude}`;
            if (stationPopupKey.current !== key) {
              stationPopup.current?.remove();
              const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: '310px', className: 'station-hover-popup' })
                .setLngLat([longitude, latitude]).setDOMContent(stationPopupContent(station.properties, current.current)).addTo(instance);
              stationPopup.current = popup; stationPopupKey.current = key;
            }
            setHover(null); instance.getCanvas().style.cursor = 'pointer'; return;
          }
          const cluster = features.find(f => f.layer.id === 'station-clusters');
          if (cluster) {
            stationPopup.current?.remove(); stationPopupKey.current = ''; instance.getCanvas().style.cursor = 'pointer';
            setHover({ name: 'Postos agrupados', x: event.point.x, y: event.point.y, city: false, clusterCount: Number(cluster.properties.point_count) }); return;
          }
          stationPopup.current?.remove(); stationPopup.current = null; stationPopupKey.current = '';
          const cityFeature = features.find(f => f.layer.id === 'cities-fill');
          const feature = cityFeature || features.find(f => f.layer.id === 'states-fill');
          if (!feature) { setHover(null); instance.getCanvas().style.cursor = ''; return; }
          const id = String(feature.properties.codarea);
          const city = Boolean(cityFeature);
          const place = city ? p.manifest.cities.find(c => c.id === id) : p.manifest.states.find(s => s.id === id);
          const row = city ? p.cities.find(c => c.id === id) : p.states.find(s => s.uf === place?.uf);
          instance.getCanvas().style.cursor = 'pointer';
          setHover({ name: place?.name || id, row, reference: city && row && 'ref' in row ? row.ref : p.national, x: event.point.x, y: event.point.y, city });
        });
        instance.on('mouseout', () => { setHover(null); if (!stationPopupPinned.current) { stationPopup.current?.remove(); stationPopup.current = null; stationPopupKey.current = ''; } });
        instance.on('click', (event: MapMouseEvent) => {
          const p = current.current;
          const layers = p.selection.uf ? ['station-points', 'station-clusters', 'cities-fill', 'states-fill'] : ['states-fill'];
          const features = instance.queryRenderedFeatures(event.point, { layers });
          const station = features.find(f => f.layer.id === 'station-points') as StationMapFeature | undefined;
          if (station) {
            const [longitude, latitude] = station.geometry.coordinates;
            stationPopup.current?.remove();
            const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: '310px', className: 'station-hover-popup station-pinned-popup' })
              .setLngLat([longitude, latitude]).setDOMContent(stationPopupContent(station.properties, p)).addTo(instance);
            stationPopup.current = popup; stationPopupKey.current = `${station.properties.name}:${station.properties.address}:${longitude}:${latitude}`;
            stationPopupPinned.current = true;
            popup.on('close', () => { if (stationPopup.current === popup) { stationPopup.current = null; stationPopupKey.current = ''; stationPopupPinned.current = false; } });
            setHover(null); return;
          }
          const cluster = features.find(f => f.layer.id === 'station-clusters');
          if (cluster) {
            stationPopup.current?.remove(); stationPopup.current = null; stationPopupPinned.current = false;
            const source = instance.getSource('stations') as GeoJSONSource;
            const coordinates = (cluster.geometry as GeoJSON.Point).coordinates as [number, number];
            void source.getClusterExpansionZoom(Number(cluster.properties.cluster_id)).then(nextZoom => instance.easeTo({ center: coordinates, zoom: Math.min(nextZoom + 0.2, 12), duration: reduced ? 0 : 400 }));
            setHover(null); return;
          }
          stationPopup.current?.remove(); stationPopup.current = null; stationPopupKey.current = ''; stationPopupPinned.current = false;
          const city = features.find(f => f.layer.id === 'cities-fill');
          if (city) { const c = p.manifest.cities.find(c => c.id === String(city.properties.codarea)); if (c) p.onSelect({ uf: c.uf, city: c.id }); }
          else { const state = p.manifest.states.find(s => s.id === String(features[0]?.properties.codarea)); if (state) p.onSelect({ uf: state.uf }); }
        });
        instance.on('zoomend', () => setZoom(instance.getZoom()));
        const observer = new ResizeObserver(() => instance.resize()); observer.observe(container.current!);
        instance.once('remove', () => observer.disconnect());
        instance.fitBounds([[-74.2, -34], [-34, 5.4]], { padding: { top: 35, right: 25, bottom: 80, left: 25 }, duration: reduced ? 0 : 700 });
        setReady(true);
      } catch { if (alive) setProblem('A malha do IBGE não carregou. Recarregue a página para tentar novamente.'); }
    });
    return () => { alive = false; labels.current.forEach(m => m.remove()); cityLabels.current.forEach(m => m.remove()); labels.current = []; cityLabels.current = []; instance.remove(); map.current = null; };
  }, [props.manifest]);

  useEffect(() => {
    if (!ready || !map.current || !stateShapes.current) return;
    const p = props;
    const data: Collection = { ...stateShapes.current, features: stateShapes.current.features.map(f => {
      const state = p.manifest.states.find(s => s.id === String(f.properties.codarea));
      const row = p.states.find(r => r.uf === state?.uf);
      const value = p.metric === 'comparison' ? row?.eligible && p.national ? (row.p / p.national - 1) * 100 : undefined : row?.p;
      return { ...f, properties: { ...f.properties, color: priceColor(value, ...p.range, p.metric), selected: state?.uf === p.selection.uf } };
    }) };
    (map.current.getSource('states') as GeoJSONSource).setData(data);
    map.current.setPaintProperty('states-fill', 'fill-opacity', p.selection.uf ? 0.25 : 1);
    labels.current.forEach(marker => marker.remove()); labels.current = [];
    if (!p.selection.uf) {
      data.features.forEach(feature => {
        const state = p.manifest.states.find(s => s.id === String(feature.properties.codarea));
        if (!state) return;
        const row = p.states.find(r => r.uf === state.uf);
        const el = document.createElement('button'); el.className = 'state-label';
        el.textContent = state.uf; el.setAttribute('aria-label', `Explorar ${state.name}${row ? `, ${money(row.p)}` : ', sem dado'}`);
        el.addEventListener('click', e => { e.stopPropagation(); current.current.onSelect({ uf: state.uf }); });
        labels.current.push(new maplibregl.Marker({ element: el }).setLngLat(bounds(feature).getCenter()).addTo(map.current!));
      });
    }
    setHover(null);
  }, [ready, props.states, props.range, props.metric, props.selection.uf, props.manifest]);

  useEffect(() => {
    if (!ready || !map.current) return;
    let alive = true;
    const instance = map.current;
    const { selection, manifest } = props;
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 650;
    const cameraKey = `${selection.uf || 'BR'}:${selection.city || ''}`;
    const moveCamera = cameraKey !== cameraSelection.current;
    cameraSelection.current = cameraKey;
    cityLabels.current.forEach(marker => marker.remove()); cityLabels.current = [];
    setProblem('');
    if (!selection.uf) {
      (instance.getSource('cities') as GeoJSONSource).setData({ type: 'FeatureCollection', features: [] });
      if (moveCamera) instance.fitBounds([[-74.2, -34], [-34, 5.4]], { padding: { top: 65, right: 25, bottom: 80, left: 25 }, duration });
      setLoadingCities(false); return;
    }
    const state = manifest.states.find(s => s.uf === selection.uf);
    const shape = stateShapes.current?.features.find(f => String(f.properties.codarea) === state?.id);
    if (shape && !selection.city && moveCamera) instance.fitBounds(bounds(shape), { padding: 85, duration, maxZoom: 8 });
    setLoadingCities(true);
    getData<Collection>(manifest.geometry.cityFiles.replace('{uf}', selection.uf)).then(shapes => {
      if (!alive) return;
      const data: Collection = { ...shapes, features: shapes.features.map(f => {
        const row = current.current.cities.find(c => c.id === String(f.properties.codarea));
        const p = current.current;
        const value = p.metric === 'comparison' ? row?.eligible && row.ref ? (row.p / row.ref - 1) * 100 : undefined : row?.p;
        return { ...f, properties: { ...f.properties, color: priceColor(value, ...p.range, p.metric), selected: String(f.properties.codarea) === selection.city } };
      }) };
      (instance.getSource('cities') as GeoJSONSource).setData(data);
      const city = data.features.find(f => String(f.properties.codarea) === selection.city);
      if (city && moveCamera) instance.fitBounds(bounds(city), { padding: 90, duration, maxZoom: 10 });
      const cityIds = new Set(shapes.features.map(f => String(f.properties.codarea)));
      const labelled = selection.city ? manifest.cities.filter(c => c.id === selection.city) : manifest.cities.filter(c => cityIds.has(c.id)).sort((a,b) => (current.current.cities.find(c => c.id === b.id)?.n || 0) - (current.current.cities.find(c => c.id === a.id)?.n || 0)).slice(0, 8);
      labelled.forEach(c => {
        const el = document.createElement('button'); el.className = 'city-label'; el.textContent = c.name;
        el.setAttribute('aria-label', `Explorar município ${c.name}`);
        el.addEventListener('click', e => { e.stopPropagation(); current.current.onSelect({ uf: c.uf, city: c.id }); });
        cityLabels.current.push(new maplibregl.Marker({element:el}).setLngLat([c.lon,c.lat]).addTo(instance));
      });
      setLoadingCities(false);
    }).catch(() => { if (alive) { setProblem('Não foi possível carregar os limites municipais.'); setLoadingCities(false); } });
    return () => { alive = false; };
  }, [ready, props.selection.uf, props.selection.city, props.cities, props.metric, props.range, props.manifest, retry]);

  useEffect(() => {
    if (!ready || !map.current) return;
    let alive = true;
    const source = map.current.getSource('stations') as GeoJSONSource;
    stationPopup.current?.remove(); stationPopup.current = null; stationPopupKey.current = ''; stationPopupPinned.current = false;
    source.setData(emptyStationData);
    setStationFile(null); setStationCount(0); setStationError(false);
    if (!props.selection.uf || !props.manifest.stationLayer) { setLoadingStations(false); return; }
    const product = props.manifest.products.find(item => item.id === props.productId);
    const path = (product?.stationFile || props.manifest.stationLayer.filePattern)
      .replace('{product}', props.productId).replace('{uf}', props.selection.uf);
    setLoadingStations(true);
    getData<StationFile>(path).then(file => {
      if (alive) { setStationFile(file); setLoadingStations(false); }
    }).catch(() => {
      if (alive) { setStationError(true); setLoadingStations(false); }
    });
    return () => { alive = false; };
  }, [ready, props.selection.uf, props.productId, props.manifest, retry]);

  useEffect(() => {
    if (!ready || !map.current) return;
    const source = map.current.getSource('stations') as GeoJSONSource;
    if (!props.selection.uf || !stationFile) { source.setData(emptyStationData); setStationCount(0); return; }
    const stateRow = props.states.find(row => row.uf === props.selection.uf);
    const features: StationMapFeature[] = [];
    for (const feature of stationFile.features) {
      if (props.selection.city && feature.properties.municipalityId !== props.selection.city) continue;
      const priceRow = feature.properties.prices.find(row => row[0] === props.weekIndex);
      if (!priceRow) continue;
      const price = priceRow[1] / 1000;
      const colorValue = props.metric === 'price' ? price : stateRow?.eligible && stateRow.p ? (price / stateRow.p - 1) * 100 : undefined;
      const { prices: _prices, ...properties } = feature.properties;
      features.push({ ...feature, properties: { ...properties, price, collections: priceRow[2], color: priceColor(colorValue, ...props.range, props.metric) } });
    }
    source.setData({ type: 'FeatureCollection', features });
    setStationCount(features.length);
    stationPopup.current?.remove(); stationPopup.current = null; stationPopupKey.current = ''; stationPopupPinned.current = false;
  }, [ready, stationFile, props.weekIndex, props.states, props.range, props.metric, props.selection.uf, props.selection.city]);

  const delta = hover?.row && hover.reference && hover.row.eligible ? (hover.row.p / hover.reference - 1) * 100 : undefined;
  const hasCoverage = props.selection.uf ? props.cities.some(c => props.manifest.cities.find(place => place.id === c.id)?.uf === props.selection.uf) : props.states.length > 0;
  return <div className="map-stage">
    <div ref={container} className="map-canvas" aria-label="Mapa interativo de preços no Brasil. Use também a busca e a lista para navegar." />
    <div className="map-heading"><span className="eyebrow">ATLAS DE COMBUSTÍVEIS</span><h2>{props.selection.uf ? props.manifest.states.find(s => s.uf === props.selection.uf)?.name : 'Um país. Muitos preços.'}</h2><p>{props.selection.uf ? 'Postos agrupados. Aproxime para ver o preço de cada um.' : 'Passe pelos estados. Descubra as diferenças.'}</p></div>
    <div className="north"><Compass size={23} strokeWidth={1.2}/><span>N</span></div>
    {(loadingCities || loadingStations) && <div className="map-loading" role="status"><span className="spinner"/> {loadingCities && loadingStations ? 'Carregando municípios e postos' : loadingCities ? 'Carregando municípios' : 'Carregando preços por posto'}</div>}
    {problem && <div className="map-problem" role="alert">{problem}{ready && <button onClick={() => setRetry(r => r + 1)}>Tentar novamente</button>}</div>}
    {hover && <div className="map-tooltip" style={{ left: Math.min(hover.x + 20, (container.current?.clientWidth || 600) - 242), top: Math.max(12, Math.min(hover.y - 75, (container.current?.clientHeight || 600) - 160)) }}>
      <span className="eyebrow">{hover.clusterCount !== undefined ? 'POSTOS AGRUPADOS' : hover.city ? 'MUNICÍPIO' : 'ESTADO'}</span><strong>{hover.clusterCount !== undefined ? `${count(hover.clusterCount)} postos` : hover.name}</strong>
      {hover.clusterCount !== undefined ? <p>Clique ou aproxime para ver os preços por posto.</p> : hover.row ? <><div className="tooltip-price">{money(hover.row.p)} <small>/ {unitLabel(props.unit)}</small></div><p>{count(hover.row.n)} postos · {delta === undefined ? 'Comparação indisponível' : `${delta > 0 ? '+' : ''}${delta.toFixed(1).replace('.', ',')}% vs. ${hover.city ? 'UF' : 'Brasil'}`}</p></> : <p>Sem coleta neste produto e semana.</p>}
      {hover.clusterCount === undefined && <span className="tooltip-hint">Clique para explorar ↗</span>}
    </div>}
    <div className="map-controls"><button title="Aproximar" aria-label="Aproximar mapa" onClick={() => map.current?.zoomIn()}><Plus size={18}/></button><button title="Afastar" aria-label="Afastar mapa" onClick={() => map.current?.zoomOut()}><Minus size={18}/></button><span/><button title="Voltar ao Brasil" aria-label="Voltar ao mapa do Brasil" onClick={() => { props.onSelect({}); cameraSelection.current = ''; map.current?.fitBounds([[-74.2,-34],[-34,5.4]], {padding:70,duration:0}); }}><Crosshair size={18}/></button></div>
    <div className="map-caption"><div className="caption-line"><span className="legend-dot"/> {props.selection.uf ? 'Limites dos municípios observados' : '27 unidades da federação'}</div>{props.selection.uf && <div className="caption-line station-caption"><span className="station-dot"/>{loadingStations ? 'Carregando postos…' : stationError ? 'Localização dos postos indisponível' : stationCount === 0 ? 'Sem posto localizado neste recorte' : zoom < 9 ? `${count(stationCount)} postos agrupados · aproxime para individualizar` : `${count(stationCount)} postos com preço · cada ponto é um posto`}</div>}<small>{props.selection.uf && stationCount > 0 && props.manifest.stationLayer ? `Localização: cadastro ANP de ${date(props.manifest.stationLayer.snapshotAt)} · não validada` : 'Malha IBGE · Fonte: ANP / Fabric'}</small></div>
    <div className="map-legend">{hasCoverage ? <><div><span>{props.metric === 'price' ? `Preço mediano · R$/${unitLabel(props.unit)}` : `Diferença vs. ${props.selection.uf ? 'UF' : 'Brasil'}`}</span><span className="no-data"><i/> Sem dado{props.metric === 'comparison' ? ' / sem base' : ''}</span></div><div className={`legend-scale ${props.metric === 'comparison' ? 'diverging' : ''}`}/><div><b>{props.metric === 'price' ? money(props.range[0]) : `≤ ${props.range[0].toFixed(0)}%`}</b><span>{props.metric === 'price' ? 'menor → maior preço' : 'abaixo ← referência → acima'}</span><b>{props.metric === 'price' ? money(props.range[1]) : `≥ +${props.range[1].toFixed(0)}%`}</b></div></> : <span>Nenhuma coleta neste produto e semana.</span>}</div>
  </div>;
}

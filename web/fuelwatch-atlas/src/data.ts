export type State = { id: string; uf: string; name: string; region: string };
export type City = { id: string; name: string; uf: string; lat: number; lon: number };
export type Product = { id: string; label: string; unit: string; file: string; stationFile?: string };
export type Observation = { w: number; p: number; n: number; c: number; lo: number; hi: number; eligible?: boolean };
export type StateRow = Observation & { uf: string };
export type CityRow = Observation & { id: string; ref: number };
export type ProductData = { id: string; unit: string; states: StateRow[]; cities: CityRow[]; national: Observation[] };
export type StationPrice = [week: number, priceMills: number, collections: number];
export type StationProperties = {
  name: string; distributor: string; address: string; complement: string; neighborhood: string; cep: string;
  municipality: string; municipalityId: string; uf: string; accuracyMeters: number; origin: string; dataObtained: string; prices: StationPrice[];
};
export type StationFeature = GeoJSON.Feature<GeoJSON.Point, StationProperties>;
export type StationFile = GeoJSON.FeatureCollection<GeoJSON.Point, StationProperties>;
export type Manifest = {
  dataset: { title: string; periodStart: string; periodEnd: string; snapshotAt: string; observations: number; stations: number; municipalities: number; publicationHash: string; notes: string[] };
  weeks: string[]; products: Product[]; states: State[]; cities: City[];
  geometry: { statesFile: string; cityFiles: string };
  stationLayer?: {
    snapshotAt: string; filePattern: string; stationCount: number; currentCnpjMatches: number;
    historicalStationCount: number; stationWeekRows: number; stationWeekCoveragePercent: number;
    accuracyMeters: { min: number; median: number; max: number }; validationStatus: string;
    source: string; documentation: string; temporalNote: string; coverageNote: string;
  };
};
export type Selection = { uf?: string; city?: string };
export type Metric = 'price' | 'comparison';

const cache = new Map<string, Promise<unknown>>();
export function getData<T>(path: string): Promise<T> {
  if (!cache.has(path)) cache.set(path, fetch(`${import.meta.env.BASE_URL}data/${path}`).then(r => {
    if (!r.ok) throw new Error('Não foi possível carregar este recorte.');
    return r.json();
  }).catch(error => { cache.delete(path); throw error; }));
  return cache.get(path) as Promise<T>;
}
export const money = (v: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
export const count = (v: number) => new Intl.NumberFormat('pt-BR').format(v);
export const unitLabel = (unit: string) => unit === 'm3' ? 'm³' : 'L';
export const date = (value: string, options: Intl.DateTimeFormatOptions = { day: '2-digit', month: 'short', year: 'numeric' }) => new Intl.DateTimeFormat('pt-BR', { ...options, timeZone: 'UTC' }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
export function weekLabel(start: string, end: string) {
  const last = new Date(`${start}T12:00:00Z`);
  last.setUTCDate(last.getUTCDate() + 6);
  return `${date(start, { day: '2-digit', month: 'short' })} — ${date(last.toISOString().slice(0, 10) > end ? end : last.toISOString().slice(0, 10))}`;
}
export const normalize = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export function priceColor(value: number | undefined, min: number, max: number, metric: Metric) {
  if (value === undefined || !Number.isFinite(value)) return '#293142';
  const stops = metric === 'comparison' ? [[47, 99, 255], [232, 237, 246], [255, 118, 46]] : [[47, 99, 255], [137, 108, 235], [255, 118, 46]];
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1))) * 2;
  const i = Math.min(1, Math.floor(t));
  return `rgb(${stops[i].map((v, c) => Math.round(v + (stops[i + 1][c] - v) * (t - i))).join(',')})`;
}

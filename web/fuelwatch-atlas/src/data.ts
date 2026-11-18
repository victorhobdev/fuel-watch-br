export type State = { id: string; uf: string; name: string; region: string };
export type City = { id: string; name: string; uf: string; lat: number; lon: number };
export type Product = {
  id: string;
  label: string;
  source?: string;
  unit: string;
  file: string;
  stationFile?: string;
  stateRows?: number;
  cityRows?: number;
};
export type Observation = {
  w: number;
  p: number;
  n: number;
  c: number;
  lo: number;
  hi: number;
  eligible?: boolean;
};
export type StateRow = Observation & { uf: string };
export type CityRow = Observation & { id: string; ref: number };
export type ProductData = {
  id: string;
  unit: string;
  states: StateRow[];
  cities: CityRow[];
  national: Observation[];
};
export type StationPrice = [week: number, priceMills: number, collections: number];
export type StationProperties = {
  name: string;
  distributor: string;
  address: string;
  complement: string;
  neighborhood: string;
  cep: string;
  municipality: string;
  municipalityId: string;
  uf: string;
  accuracyMeters: number;
  origin: string;
  dataObtained: string;
  prices: StationPrice[];
};
export type StationFeature = GeoJSON.Feature<GeoJSON.Point, StationProperties>;
export type StationFile = GeoJSON.FeatureCollection<GeoJSON.Point, StationProperties>;

export type ActiveStation = {
  key: string;
  lon: number;
  lat: number;
  price: number;
  collections: number;
  deltaPercent?: number;
  color: string;
  properties: StationProperties;
};

export type SourceCheck = {
  rows: number;
  rowGroups: number;
  businessSha256: string;
  reconciledWithFabric: boolean;
};

export type Manifest = {
  dataset: {
    title: string;
    periodStart: string;
    periodEnd: string;
    snapshotAt: string;
    observations: number;
    stations: number;
    municipalities: number;
    publicationHash: string;
    publicationId?: string;
    notes: string[];
  };
  weeks: string[];
  products: Product[];
  states: State[];
  cities: City[];
  geometry: { statesFile: string; cityFiles: string };
  methodology?: {
    national: string;
    collections: string;
    stationCount: string;
    cityCoordinates: string;
    eligibility: string;
  };
  sourceVerification?: Record<string, SourceCheck>;
  stationLayer?: {
    snapshotAt: string;
    filePattern: string;
    stationCount: number;
    currentCnpjMatches: number;
    historicalStationCount: number;
    stationWeekRows: number;
    stationWeekCoveragePercent: number;
    accuracyMeters: { min: number; median: number; max: number };
    validationStatus: string;
    source: string;
    documentation: string;
    temporalNote: string;
    coverageNote: string;
  };
};

export type Selection = { uf?: string; city?: string };
export type Metric = 'price' | 'comparison';
export type SortMode = 'low' | 'high' | 'coverage';
export type ExplorerTab = 'regions' | 'stations';
export type ChartWindow = '26w' | 'all';

const cache = new Map<string, Promise<unknown>>();

export function getData<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const request = fetch(`${import.meta.env.BASE_URL}data/${path}`)
      .then(response => {
        if (!response.ok) throw new Error('Não foi possível carregar este recorte.');
        return response.json();
      })
      .catch(error => {
        cache.delete(path);
        throw error;
      });
    cache.set(path, request);
  }
  return cache.get(path) as Promise<T>;
}

const brlFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
});

const brlCompactFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const intFormatter = new Intl.NumberFormat('pt-BR');

export const money = (value: number) => brlFormatter.format(value);
export const moneyCompact = (value: number) => brlCompactFormatter.format(value);
export const count = (value: number) => intFormatter.format(value);
export const unitLabel = (unit: string) => (unit === 'm3' ? 'm³' : 'L');

export function signedPercent(value: number): string {
  const formatted = Math.abs(value).toFixed(1).replace('.', ',');
  if (Math.abs(value) < 0.05) return '0,0%';
  return `${value > 0 ? '+' : '−'}${formatted}%`;
}

export function date(
  value: string,
  options: Intl.DateTimeFormatOptions = { day: '2-digit', month: 'short', year: 'numeric' },
): string {
  const parsed = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  return new Intl.DateTimeFormat('pt-BR', { ...options, timeZone: 'UTC' }).format(parsed);
}

export function weekLabel(start: string, periodEnd: string): string {
  const last = new Date(`${start}T12:00:00Z`);
  last.setUTCDate(last.getUTCDate() + 6);
  const endIso = last.toISOString().slice(0, 10);
  const clampedEnd = endIso > periodEnd ? periodEnd : endIso;
  return `${date(start, { day: '2-digit', month: 'short' })} — ${date(clampedEnd)}`;
}

export const normalize = (value: string) =>
  value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

export function stationId(feature: StationFeature): string {
  const p = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  return `${p.municipalityId}:${p.name}:${p.address}:${lon.toFixed(6)}:${lat.toFixed(6)}`;
}

const PRICE_STOPS: [number, number, number][] = [
  [2, 132, 199],   // #0284c7 deep sky
  [34, 211, 238],  // #22d3ee luminous cyan
  [250, 204, 21],  // #facc15 warm gold
  [251, 146, 60],  // #fb923c amber
  [244, 63, 94],   // #f43f5e coral rose
];

const COMPARISON_STOPS: [number, number, number][] = [
  [14, 165, 233],  // -15% #0ea5e9 cool azure
  [125, 211, 252], // -7.5% #7dd3fc sky
  [226, 232, 240], //   0% #e2e8f0 neutral ivory-slate
  [253, 186, 116], // +7.5% #fdba74 warm apricot
  [249, 115, 22],  // +15% #f97316 tangerine
];

export const NO_DATA_FILL = '#162032';

export function priceColor(
  value: number | undefined,
  min: number,
  max: number,
  metric: Metric,
): string {
  if (value === undefined || !Number.isFinite(value)) return NO_DATA_FILL;
  const stops = metric === 'comparison' ? COMPARISON_STOPS : PRICE_STOPS;
  const span = max - min || 1;
  const clamped = Math.max(0, Math.min(1, (value - min) / span));
  const scaled = clamped * (stops.length - 1);
  const index = Math.min(stops.length - 2, Math.floor(scaled));
  const localT = scaled - index;
  const start = stops[index];
  const end = stops[index + 1];
  const rgb = start.map((channel, i) => Math.round(channel + (end[i] - channel) * localT));
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

export type SemesterJump = { id: string; label: string; weekIndex: number };

export function semesterMilestones(weeks: string[]): SemesterJump[] {
  if (!weeks.length) return [];
  const targets: [string, string, string][] = [
    ['2024-1', '2024.1', '2024-01-01'],
    ['2024-2', '2024.2', '2024-07-01'],
    ['2025-1', '2025.1', '2025-01-01'],
    ['2025-2', '2025.2', '2025-07-01'],
    ['2026-1', '2026.1', '2026-01-01'],
  ];
  const jumps: SemesterJump[] = [];
  for (const [id, label, isoTarget] of targets) {
    const idx = weeks.findIndex(w => w >= isoTarget);
    if (idx >= 0) jumps.push({ id, label, weekIndex: idx });
  }
  const latestComplete = Math.max(0, weeks.length - 2);
  jumps.push({ id: 'latest', label: 'Última completa', weekIndex: latestComplete });
  return jumps;
}

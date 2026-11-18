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
export type ExplorerTab = 'stations' | 'regions';
export type ChartWindow = '26w' | 'all';
export type AppView = 'map' | 'trends' | 'regional';
export type ViewportBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type DistributorVisual = {
  short: string;
  label: string;
  bg: string;
  fg: string;
  accent?: string;
  isWhiteLabel?: boolean;
};

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

const digitsFormatter = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const digitsPreciseFormatter = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
});

const intFormatter = new Intl.NumberFormat('pt-BR');

export const money = (value: number) => brlFormatter.format(value);
export const moneyCompact = (value: number) => brlCompactFormatter.format(value);
export const priceDigits = (value: number) => {
  const thousandths = Math.round(value * 1000) % 10;
  return thousandths !== 0 ? digitsPreciseFormatter.format(value) : digitsFormatter.format(value);
};
export const count = (value: number) => intFormatter.format(value);
export const unitLabel = (unit: string) => (unit === 'm3' ? 'm³' : 'L');

export function shortFuelName(product: Product): string {
  const map: Record<string, string> = {
    gasolina: 'Gasolina',
    gasolina_aditivada: 'Aditivada',
    etanol: 'Etanol',
    diesel_s10: 'Diesel S10',
    diesel: 'Diesel',
    gnv: 'GNV',
  };
  return map[product.id] || product.label;
}

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
  return `${date(start, { day: '2-digit', month: 'short' })} – ${date(clampedEnd)}`;
}

export function weekCompactLabel(start: string, periodEnd: string): string {
  const last = new Date(`${start}T12:00:00Z`);
  last.setUTCDate(last.getUTCDate() + 6);
  const endIso = last.toISOString().slice(0, 10);
  const clampedEnd = endIso > periodEnd ? periodEnd : endIso;
  return `${date(start, { day: '2-digit', month: 'short' })}–${date(clampedEnd, {
    day: '2-digit',
    month: 'short',
    year: '2-digit',
  })}`;
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

export function sanitizeStreet(address?: string, complement?: string): string {
  const cleanPart = (raw?: string) =>
    (raw || '')
      .replace(/^[:;\-\s]+/, '')
      .replace(/\s*;\s*:\s*/g, ' · ')
      .replace(/\s+/g, ' ')
      .trim();

  const addr = cleanPart(address);
  let comp = cleanPart(complement);
  if (comp === '.' || comp === '-' || comp === 'S/N.' || comp === 'SN') {
    comp = '';
  }
  if (comp.length > 56) {
    comp = comp.split('·')[0].trim();
  }
  return [addr, comp].filter(Boolean).join(', ');
}

export function formatSuburbLine(neighborhood?: string, municipality?: string, uf?: string): string {
  const parts = [
    (neighborhood || '').trim(),
    municipality ? (uf ? `${municipality.trim()} (${uf})` : municipality.trim()) : '',
  ].filter(Boolean);
  return parts.join(' · ').toUpperCase();
}

export const TOP_NATIONAL_DISTRIBUTORS = [
  'BANDEIRA BRANCA',
  'VIBRA',
  'IPIRANGA',
  'RAIZEN',
  'ALE',
  'SABBÁ',
  'NEXTA',
  'RAIZEN MIME',
  'RODOIL',
  "ATEM' S",
  'EQUADOR',
  'TAURUS',
  'CHARRUA',
];

export function distributorVisual(raw?: string): DistributorVisual {
  const clean = (raw || '').trim().toUpperCase();
  if (!clean || clean.includes('BRANCA') || clean === 'SEM BANDEIRA') {
    return {
      short: 'BRANCA',
      label: 'Bandeira Branca',
      bg: '#F1F5F9',
      fg: '#334155',
      accent: '#94A3B8',
      isWhiteLabel: true,
    };
  }
  if (clean.includes('VIBRA') || clean.includes('PETROBRAS')) {
    return { short: 'VIBRA', label: 'Vibra', bg: '#006B54', fg: '#FFFFFF', accent: '#FACC15' };
  }
  if (clean.includes('IPIRANGA')) {
    return { short: 'IPIR', label: 'Ipiranga', bg: '#1D4ED8', fg: '#FACC15', accent: '#F59E0B' };
  }
  if (clean.includes('RAIZEN')) {
    return {
      short: clean.includes('MIME') ? 'MIME' : 'RAÍZ',
      label: clean.includes('MIME') ? 'Raízen Mime' : 'Raízen',
      bg: '#6B21A8',
      fg: '#FFFFFF',
      accent: '#F472B6',
    };
  }
  if (clean === 'ALE' || clean.startsWith('ALE ')) {
    return { short: 'ALE', label: 'ALE', bg: '#0369A1', fg: '#FFFFFF', accent: '#EF4444' };
  }
  if (clean.includes('SABBA') || clean.includes('SABBÁ')) {
    return { short: 'SABBÁ', label: 'Sabbá', bg: '#0F766E', fg: '#FFFFFF', accent: '#5EEAD4' };
  }
  if (clean.includes('RODOIL')) {
    return { short: 'RODO', label: 'Rodoil', bg: '#B91C1C', fg: '#FFFFFF', accent: '#FCA5A5' };
  }
  if (clean.includes('NEXTA')) {
    return { short: 'NEXTA', label: 'Nexta', bg: '#312E81', fg: '#FFFFFF', accent: '#818CF8' };
  }
  if (clean.includes('ATEM')) {
    return { short: 'ATEM', label: "Atem's", bg: '#15803D', fg: '#FFFFFF', accent: '#86EFAC' };
  }
  if (clean.includes('EQUADOR')) {
    return { short: 'EQUA', label: 'Equador', bg: '#B45309', fg: '#FFFFFF', accent: '#FDE68A' };
  }
  if (clean.includes('TAURUS')) {
    return { short: 'TAUR', label: 'Taurus', bg: '#1E3A8A', fg: '#FFFFFF', accent: '#93C5FD' };
  }
  if (clean.includes('CHARRUA')) {
    return { short: 'CHAR', label: 'Charrua', bg: '#991B1B', fg: '#FFFFFF', accent: '#FECACA' };
  }
  if (clean.includes('POTENCIAL')) {
    return { short: 'POT', label: 'Potencial', bg: '#0E7490', fg: '#FFFFFF' };
  }
  if (clean.includes('LARCO')) {
    return { short: 'LARCO', label: 'Larco', bg: '#4338CA', fg: '#FFFFFF' };
  }
  const word = clean.replace(/[^A-Z0-9À-Ú ]/g, '').split(/\s+/)[0] || 'POSTO';
  return {
    short: word.slice(0, 5),
    label: raw || 'Distribuidora',
    bg: '#4B287D',
    fg: '#FFFFFF',
  };
}

// Light-theme FuelWatch choropleth palette (Teal -> Azure -> Gold -> Coral -> Royal Purple)
const PRICE_STOPS: [number, number, number][] = [
  [0, 121, 123],   // #00797B FuelWatch teal (lowest)
  [14, 165, 233],  // #0EA5E9 clear azure
  [245, 158, 11],  // #F59E0B warm amber
  [225, 29, 72],   // #E11D48 crimson rose
  [75, 40, 125],   // #4B287D FuelWatch royal purple (highest)
];

const COMPARISON_STOPS: [number, number, number][] = [
  [0, 121, 123],   // -15% #00797B teal (below ref)
  [94, 234, 212],  // -7.5% #5EEAD4 soft mint-teal
  [226, 232, 240], //   0% #E2E8F0 neutral light slate
  [253, 186, 116], // +7.5% #FDBA74 warm apricot
  [200, 16, 46],   // +15% #C8102E crimson (above ref)
];

export const NO_DATA_FILL = '#E2E8F0';

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

export function isInViewport(lon: number, lat: number, bounds: ViewportBounds | null): boolean {
  if (!bounds) return true;
  return (
    lon >= bounds.west &&
    lon <= bounds.east &&
    lat >= bounds.south &&
    lat <= bounds.north
  );
}

export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number)[][],
): void {
  const escapeCell = (val: string | number) => {
    const str = String(val ?? '');
    if (str.includes(';') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };
  const lines = [
    headers.map(escapeCell).join(';'),
    ...rows.map(row => row.map(escapeCell).join(';')),
  ];
  const blob = new Blob([`\uFEFF${lines.join('\r\n')}`], {
    type: 'text/csv;charset=utf-8;',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

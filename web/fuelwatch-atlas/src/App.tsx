import { useEffect, useMemo, useRef, useState } from 'react';
import { animate, useReducedMotion } from 'motion/react';
import { ArrowDownRight, ArrowUpRight, ArrowRight, ChevronLeft, ChevronRight, Database, Droplet, Fuel, Info, Layers3, MapPin, Search, ShieldCheck, X } from 'lucide-react';
import AtlasMap from './AtlasMap';
import { getData, count, date, money, normalize, unitLabel, weekLabel, type CityRow, type Manifest, type Metric, type Observation, type ProductData, type Selection, type StateRow } from './data';

// Numeric transition inspired by Magic UI's Number Ticker; labels always expose the exact target.
function Price({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const previous = useRef(value);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced) { if (ref.current) ref.current.textContent = money(value); previous.current = value; return; }
    const animation = animate(previous.current, value, { duration: 0.32, ease: 'easeOut', onUpdate: v => { if (ref.current) ref.current.textContent = money(v); } });
    previous.current = value;
    return () => animation.stop();
  }, [value, reduced]);
  return <span aria-label={money(value)}><span ref={ref} aria-hidden="true">{money(value)}</span></span>;
}

function Trend({ rows, week, weeks }: { rows: Observation[]; week: number; weeks: string[] }) {
  const points = rows.filter(r => r.w <= week && r.w >= week - 25);
  if (points.length < 2) return <p className="muted small">Histórico insuficiente para este recorte.</p>;
  const low = Math.min(...points.map(r => r.p)); const high = Math.max(...points.map(r => r.p));
  const start = week - 25; const width = 286; const height = 66;
  const coords = points.map(p => [4 + ((p.w - start) / 25) * width, 8 + (1 - (p.p - low) / (high - low || 1)) * height]);
  // Separate paths across missing weeks, so gaps never imply interpolated observations.
  const path = coords.map((p, i) => `${i === 0 || points[i].w !== points[i - 1].w + 1 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ');
  return <><svg className="trend" viewBox="0 0 294 90" role="img" aria-label={`Histórico de até 26 semanas, de ${money(low)} a ${money(high)}`}><line x1="4" y1="75" x2="290" y2="75" stroke="#dce1e9" strokeDasharray="3 5"/><path d={path} fill="none" stroke="#2f63ff" strokeWidth="2.4" strokeLinejoin="round"/>{coords.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={i === coords.length - 1 ? 3.5 : 1.3} fill="#2f63ff"><title>{date(weeks[points[i].w])}: {money(points[i].p)}</title></circle>)}</svg><div className="trend-labels"><span>{date(weeks[points[0].w], { month: 'short', year: '2-digit' })}</span><span>{date(weeks[points.at(-1)!.w], { month: 'short', year: '2-digit' })}</span></div></>;
}

function Methodology({ manifest, close }: { manifest: Manifest; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="method-dialog" onClose={close} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close(); }}><div className="dialog-top"><span className="eyebrow">POR TRÁS DO MAPA</span><button className="icon-button" aria-label="Fechar metodologia" onClick={() => dialog.current?.close()}><X size={20}/></button></div><h2>Dados reais.<br/>Contexto à vista.</h2><p>Este atlas demonstra os resultados do projeto Fuel Watch no Microsoft Fabric, a partir do levantamento de preços da ANP.</p><div className="method-facts"><div><strong>{count(manifest.dataset.observations)}</strong><span>coletas no histórico</span></div><div><strong>{count(manifest.dataset.stations)}</strong><span>postos no histórico</span></div><div><strong>{manifest.dataset.municipalities}</strong><span>municípios observados</span></div></div><h3>Como ler os valores</h3><p>Primeiro calculamos a mediana de cada posto na semana. As medianas estaduais, municipais e nacional dão um peso a cada posto observado, sem dar peso extra a quem recebeu mais coletas. Os valores são nominais, em reais.</p><h3>Comparações com base suficiente</h3><p>A referência estadual exige pelo menos 10 postos. Um município só recebe comparação quando tem ao menos 3 postos e sua UF atende ao mínimo. O preço pode ser exibido mesmo com base insuficiente, mas a comparação fica indisponível.</p><h3>Cobertura e geografia</h3><p>Sem dado significa ausência de coleta naquele recorte. São 462 municípios observados ao longo do histórico, e a cobertura muda por semana e produto. As malhas simplificadas do IBGE mostram limites geográficos, não localizações de postos.</p>{manifest.stationLayer && <><h3>Postos individualizados</h3><p>A camada usa o cadastro atual da ANP consultado em {date(manifest.stationLayer.snapshotAt)} para localizar postos com preço na semana histórica selecionada. Há {count(manifest.stationLayer.stationCount)} posições publicadas de {count(manifest.stationLayer.historicalStationCount)} postos do histórico; a acurácia informada varia de {manifest.stationLayer.accuracyMeters.min} a {manifest.stationLayer.accuracyMeters.max} m (mediana {manifest.stationLayer.accuracyMeters.median} m). A ANP registra essas coordenadas como “{manifest.stationLayer.validationStatus}”. O ponto pode não representar o endereço do posto na época do preço. No mapa, os pontos ficam agrupados na visão estadual e se individualizam ao aproximar.</p></>}<h3>Período e atualização</h3><p>{date(manifest.dataset.periodStart)} a {date(manifest.dataset.periodEnd)}. A última semana é parcial: 29–30/06/2026. Snapshot de resultados validado em {date(manifest.dataset.snapshotAt)}. Não são preços atuais ou em tempo real. Extremos brutos positivos incomuns foram preservados.</p><div className="lineage"><Database size={18}/><span>ANP → ingestão → Lakehouse → Warehouse → snapshot do atlas</span></div><p className="small muted">As três tabelas de consumo tiveram seus fingerprints de conteúdo reconciliados com as evidências do Fabric antes da exportação.</p><div className="dialog-links"><a href={`${import.meta.env.BASE_URL}data/manifest.json`} target="_blank" rel="noreferrer">Manifesto do snapshot ↗</a><a href={`${import.meta.env.BASE_URL}data/validation.json`} target="_blank" rel="noreferrer">Validação dos dados ↗</a>{manifest.stationLayer && <a href={manifest.stationLayer.documentation} target="_blank" rel="noreferrer">API de revendedores ANP ↗</a>}<a href="https://servicodados.ibge.gov.br/api/docs/malhas?versao=3" target="_blank" rel="noreferrer">Malhas IBGE ↗</a></div></dialog>;
}

export default function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [data, setData] = useState<ProductData | null>(null);
  const [productId, setProductId] = useState('gasolina');
  const [week, setWeek] = useState(129); // Last complete week; the final partial week stays selectable.
  const [selection, setSelection] = useState<Selection>({});
  const [metric, setMetric] = useState<Metric>('price');
  const [query, setQuery] = useState(''); const [searching, setSearching] = useState(false);
  const [methodology, setMethodology] = useState(false);
  const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<'low' | 'high'>('low');
  const [retry, setRetry] = useState(0);
  const searchBox = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    getData<Manifest>('manifest.json').then(m => { if (active) { setManifest(m); setWeek(Math.max(0, m.weeks.length - 2)); setError(''); } }).catch(() => { if (active) { setError('O snapshot não carregou. Verifique sua conexão e tente novamente.'); setLoading(false); } });
    return () => { active = false; };
  }, [retry]);
  useEffect(() => {
    if (!manifest) return;
    let active = true; setLoading(true); setError('');
    const product = manifest.products.find(p => p.id === productId)!;
    getData<ProductData>(product.file).then(d => { if (active) { setData(d); setLoading(false); } }).catch(() => { if (active) { setError('Não foi possível carregar este combustível. Tente novamente.'); setLoading(false); } });
    return () => { active = false; };
  }, [manifest, productId, retry]);
  useEffect(() => {
    const outside = (e: PointerEvent) => { if (!searchBox.current?.contains(e.target as Node)) setSearching(false); };
    document.addEventListener('pointerdown', outside); return () => document.removeEventListener('pointerdown', outside);
  }, []);

  const states = useMemo(() => data?.states.filter(r => r.w === week) || [], [data, week]);
  const cities = useMemo(() => data?.cities.filter(r => r.w === week) || [], [data, week]);
  const national = data?.national.find(r => r.w === week);
  const state = manifest?.states.find(s => s.uf === selection.uf);
  const city = manifest?.cities.find(c => c.id === selection.city);
  const stateRow = states.find(r => r.uf === selection.uf);
  const currentRow: Observation | undefined = selection.city ? cities.find(r => r.id === selection.city) : selection.uf ? stateRow : national;
  const reference = selection.city ? (currentRow as CityRow | undefined)?.ref : national?.p;
  const delta = selection.uf && currentRow?.eligible && reference ? (currentRow.p / reference - 1) * 100 : undefined;
  const product = manifest?.products.find(p => p.id === productId);
  const dataIsCurrent = data?.id === productId;
  const regionName = city?.name || state?.name || 'Brasil';
  const visibleCities = useMemo(() => cities.filter(c => manifest?.cities.find(m => m.id === c.id)?.uf === selection.uf), [cities, manifest, selection.uf]);
  const range = useMemo<[number, number]>(() => {
    if (metric === 'comparison') return [-15, 15];
    const values = (selection.uf ? visibleCities : states).map(r => r.p);
    return values.length ? [Math.min(...values), Math.max(...values)] : [0, 1];
  }, [states, visibleCities, selection.uf, metric]);
  const trendRows = useMemo(() => !data ? [] : selection.city ? data.cities.filter(r => r.id === selection.city) : selection.uf ? data.states.filter(r => r.uf === selection.uf) : data.national, [data, selection.uf, selection.city]);
  const ranked = useMemo(() => {
    const rows = selection.uf ? visibleCities : states;
    return [...rows].sort((a, b) => sort === 'low' ? a.p - b.p : b.p - a.p);
  }, [states, visibleCities, sort, selection.uf]);
  const searchResults = useMemo(() => {
    if (!manifest) return [];
    const q = normalize(query.trim());
    const s = manifest.states.filter(s => normalize(`${s.name} ${s.uf}`).includes(q)).map(s => ({ key: s.uf, name: s.name, meta: `${s.uf} · Estado`, selection: { uf: s.uf } as Selection }));
    const c = q.length >= 2 ? manifest.cities.filter(c => normalize(`${c.name} ${c.uf}`).includes(q)).map(c => ({ key: c.id, name: c.name, meta: `${c.uf} · Município`, selection: { uf: c.uf, city: c.id } as Selection })) : [];
    return [...s, ...c].slice(0, 8);
  }, [manifest, query]);
  const select = (s: Selection) => { setSelection(s); setSearching(false); setQuery(''); };

  if (!manifest) return <div className="initial"><div className="brand"><span className="brand-icon"><Droplet size={21}/></span>fuel<span>watch</span></div>{error ? <><p role="alert">{error}</p><button onClick={() => setRetry(v => v + 1)}>Tentar novamente</button></> : <p role="status"><span className="spinner"/> Abrindo o atlas de combustíveis…</p>}</div>;

  return <div className="app">
    <header className="topbar"><a href={import.meta.env.BASE_URL} className="brand" aria-label="Fuel Watch, início"><span className="brand-icon"><Droplet size={21}/></span>fuel<span>watch</span><small>ATLAS</small></a><nav><span className="nav-current"><Layers3 size={15}/> Explorar preços</span><button onClick={() => setMethodology(true)}>Sobre os dados <ArrowRight size={14}/></button></nav><span className="snapshot-badge"><i/> Snapshot histórico <span>2024 — 2026</span></span></header>
    <div className="intro"><div><div className="eyebrow">INTELIGÊNCIA DE PREÇOS · BRASIL</div><h1>O preço muda.<span> A perspectiva também.</span></h1></div><p>Uma visão geográfica dos combustíveis.<br/><b>Dados públicos, explorados com contexto.</b></p></div>
    <section className="toolbar" aria-label="Filtros do atlas"><div className="product-field"><Fuel size={18}/><label className="sr-only" htmlFor="fuel">Combustível</label><select id="fuel" value={productId} onChange={e => setProductId(e.target.value)}>{manifest.products.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></div><div className="search-box" ref={searchBox}><Search size={17}/><input aria-label="Buscar estado ou município" aria-controls="location-results" aria-expanded={searching} placeholder="Buscar estado ou município" value={query} onFocus={() => setSearching(true)} onKeyDown={e => { if (e.key === 'Escape') setSearching(false); if (e.key === 'ArrowDown') { e.preventDefault(); searchBox.current?.querySelector<HTMLButtonElement>('.search-results button')?.focus(); } if (e.key === 'Enter' && searchResults[0]) select(searchResults[0].selection); }} onChange={e => { setQuery(e.target.value); setSearching(true); }}/>{query && <button className="icon-button" aria-label="Limpar busca" onClick={() => setQuery('')}><X size={14}/></button>}{searching && <div id="location-results" className="search-results"><span className="eyebrow">{query ? 'RESULTADOS' : 'EXPLORE UM ESTADO'}</span>{searchResults.length ? searchResults.map(r => <button key={r.key} onClick={() => select(r.selection)}><MapPin size={15}/><span>{r.name}<small>{r.meta}</small></span><ChevronRight size={15}/></button>) : <p>Nenhum município observado encontrado.</p>}<small className="search-note">Busca nos 27 estados e 462 municípios do histórico.</small></div>}</div><div className="metric-control" role="group" aria-label="Colorir mapa por"><button aria-pressed={metric === 'price'} onClick={() => setMetric('price')}>Preço mediano</button><button aria-pressed={metric === 'comparison'} onClick={() => setMetric('comparison')}>Comparação</button></div><button className="method-button" onClick={() => setMethodology(true)}><Info size={16}/><span>Metodologia</span></button></section>
    <main className="workspace" aria-busy={loading}>
      <aside className="inspector" aria-label="Detalhes do local selecionado"><div className="breadcrumbs"><button onClick={() => select({})}>Brasil</button>{state && <><ChevronRight size={12}/><button onClick={() => select({ uf: state.uf })}>{state.uf}</button></>}{city && <><ChevronRight size={12}/><span>Município</span></>}</div><div className="region-heading"><div><span className="eyebrow">{selection.city ? 'VISÃO MUNICIPAL' : selection.uf ? 'VISÃO ESTADUAL' : 'PANORAMA NACIONAL'}</span><h2>{regionName}</h2></div><span className="region-icon"><MapPin size={19}/></span></div>
        {error && <div className="inline-error" role="alert">{error}<button onClick={() => setRetry(v => v + 1)}>Tentar novamente</button></div>}
        {loading || !dataIsCurrent ? <div className="loading-data" role="status"><span className="spinner"/> Carregando preços…</div> : <>
          <div className="price-block"><span className="small muted">Mediana · {product?.label.toLowerCase()}</span><div className="main-price">{currentRow ? <Price value={currentRow.p}/> : <span>—</span>}<small>/ {unitLabel(product!.unit)}</small></div>{selection.uf ? delta !== undefined ? <div className={`delta ${delta > 0 ? 'positive' : 'negative'}`}>{delta > 0 ? <ArrowUpRight size={16}/> : delta < 0 ? <ArrowDownRight size={16}/> : <ArrowRight size={16}/>}<b>{Math.abs(delta).toFixed(1).replace('.', ',')}% {delta > 0 ? 'acima' : delta < 0 ? 'abaixo' : 'em linha'}</b><span> da {selection.city ? 'UF' : 'mediana Brasil'}</span></div> : <div className="base-warning"><Info size={14}/>{currentRow ? 'Base insuficiente para comparar' : 'Sem dado nesta semana e produto'}</div> : <div className="delta neutral"><span className="tiny-dot"/> Referência dos postos observados no país</div>}</div>
          <div className="coverage"><div><span>Postos na semana</span><strong>{currentRow ? count(currentRow.n) : '—'}</strong></div><div><span>Coletas na semana</span><strong>{currentRow ? count(currentRow.c) : '—'}</strong></div></div>
          {currentRow && <div className="observed-range"><span>Extremos coletados <Info size={12}><title>Preços mínimo e máximo das coletas brutas aceitas.</title></Info></span><b>{money(currentRow.lo)} <span>—</span> {money(currentRow.hi)}</b></div>}
          <section className="trend-section"><div className="section-label"><h3>O caminho do preço</h3><span>ATÉ 26 SEMANAS</span></div><Trend rows={trendRows} week={week} weeks={manifest.weeks}/></section>
          <section className="ranking"><div className="section-label"><h3>{selection.uf ? 'Municípios da UF' : 'Pelos estados'}</h3><label className="sr-only" htmlFor="ranking-sort">Ordenar preços</label><select id="ranking-sort" value={sort} onChange={e => setSort(e.target.value as 'low' | 'high')}><option value="low">Menores preços</option><option value="high">Maiores preços</option></select></div><div className="rank-list">{ranked.length ? ranked.slice(0, 5).map((row, index) => {
            const isCity = 'id' in row; const item = isCity ? manifest.cities.find(c => c.id === row.id) : manifest.states.find(s => s.uf === (row as StateRow).uf);
            if (!item) return null;
            return <button className="rank-row" key={isCity ? row.id : (row as StateRow).uf} onClick={() => select(isCity ? { uf: item.uf, city: row.id } : { uf: item.uf })}><span className="rank-number">0{index + 1}</span><span className="rank-name">{item.name}<small>{count(row.n)} postos{row.eligible ? '' : ' · base limitada'}</small></span><b>{money(row.p)}</b><ChevronRight size={14}/></button>;
          }) : <p className="small muted">Sem coletas neste recorte.</p>}</div><span className="ranking-note">{selection.uf ? visibleCities.length : states.length} {selection.uf ? 'municípios' : 'UFs'} com dados nesta semana</span></section>
        </>}
        <button className="data-proof" onClick={() => setMethodology(true)}><ShieldCheck size={16}/><span>Snapshot validado no Fabric<small>Atualizado em {date(manifest.dataset.snapshotAt)}</small></span><ArrowRight size={14}/></button>
      </aside>
      <div className="map-area">{data && dataIsCurrent ? <AtlasMap manifest={manifest} states={states} cities={cities} selection={selection} metric={metric} national={national?.p} range={range} unit={product!.unit} productId={productId} weekIndex={week} onSelect={select}/> : <div className="map-placeholder"><span className="spinner"/> Preparando o mapa</div>}{loading && <div className="map-busy"/>}</div>
    </main>
    <section className="timeline" aria-label="Período do snapshot"><div className="timeline-label"><span className="eyebrow">UMA SEMANA DE CADA VEZ</span><strong>{weekLabel(manifest.weeks[week], manifest.dataset.periodEnd)}</strong><small>{week === manifest.weeks.length - 1 ? 'Semana parcial · 2 dias de cobertura' : 'Período histórico · semana ISO'}</small></div><div className="time-track"><div className="time-buttons"><button className="icon-button" aria-label="Semana anterior" disabled={week === 0} onClick={() => setWeek(w => w - 1)}><ChevronLeft size={18}/></button><button className="icon-button" aria-label="Próxima semana" disabled={week === manifest.weeks.length - 1} onClick={() => setWeek(w => w + 1)}><ChevronRight size={18}/></button></div><div className="slider-wrap"><label className="sr-only" htmlFor="week">Semana do histórico</label><input id="week" type="range" min={0} max={manifest.weeks.length - 1} value={week} aria-valuetext={weekLabel(manifest.weeks[week], manifest.dataset.periodEnd)} onChange={e => setWeek(Number(e.target.value))}/><div className="slider-labels"><span>JAN 2024</span><span>JAN 2025</span><span>JUN 2026</span></div></div></div><div className="snapshot-note"><Database size={17}/><span>Histórico ANP<b>Não são preços em tempo real</b></span></div></section>
    <footer><span>FUEL WATCH <i> / </i> Do dado público à perspectiva.</span><span>{count(manifest.dataset.observations)} coletas · {count(manifest.dataset.stations)} postos · 462 municípios no histórico</span></footer>
    {methodology && <Methodology manifest={manifest} close={() => setMethodology(false)}/>}
  </div>;
}

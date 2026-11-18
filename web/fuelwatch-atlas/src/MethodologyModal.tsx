import { useEffect, useRef } from 'react';
import { Database, ExternalLink, Layers, ShieldCheck, X } from 'lucide-react';
import { count, date, type Manifest } from './data';

type Props = {
  manifest: Manifest;
  onClose: () => void;
};

export default function MethodologyModal({ manifest, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const checks = manifest.sourceVerification ? Object.entries(manifest.sourceVerification) : [];

  return (
    <dialog
      ref={dialogRef}
      className="method-dialog"
      onClose={onClose}
      onClick={event => {
        if (event.target === event.currentTarget) dialogRef.current?.close();
      }}
    >
      <div className="dialog-header">
        <div>
          <span className="eyebrow accent">ENGENHARIA DE DADOS · MICROSOFT FABRIC</span>
          <h2>Dados públicos auditáveis, da coleta ao mapa.</h2>
        </div>
        <button
          type="button"
          className="icon-btn"
          aria-label="Fechar janela de metodologia"
          onClick={() => dialogRef.current?.close()}
        >
          <X size={20} />
        </button>
      </div>

      <p className="dialog-lead">
        O <strong>Fuel Watch Atlas</strong> consome um snapshot estático reconciliado com o Warehouse Gold do projeto{' '}
        <strong>Fuel Watch BR</strong> no Microsoft Fabric, integrando séries semestrais da ANP, geografia oficial do IBGE
        e validações determinísticas por hash de conteúdo.
      </p>

      <div className="dialog-kpi-strip">
        <div>
          <strong>{count(manifest.dataset.observations)}</strong>
          <span>coletas aceitas</span>
        </div>
        <div>
          <strong>{count(manifest.dataset.stations)}</strong>
          <span>postos observados</span>
        </div>
        <div>
          <strong>{count(manifest.dataset.municipalities)}</strong>
          <span>municípios / 27 UFs</span>
        </div>
        <div>
          <strong>{count(manifest.weeks.length)}</strong>
          <span>semanas ISO</span>
        </div>
      </div>

      <div className="lineage-banner">
        <Database size={18} />
        <div>
          <strong>Linhagem ponta a ponta</strong>
          <span>
            ANP (ZIP/SHA-256) → Bronze Delta → Silver PySpark (validação + IBGE) → Warehouse Gold T-SQL (SCD2 transacional) → Snapshot estático reconciliado
          </span>
        </div>
      </div>

      <div className="method-grid">
        <article className="method-card">
          <h3>1. Mediana em dois estágios</h3>
          <p>
            Primeiro calcula-se a mediana semanal de cada posto (<code>posto_semana</code>). Em seguida, as medianas municipal,
            estadual e nacional atribuem <strong>peso 1 por posto</strong>, evitando que estabelecimentos visitados mais vezes distorçam a referência.
            Preços são nominais em reais, sem misturar litro e m³.
          </p>
        </article>

        <article className="method-card">
          <h3>2. Cobertura mínima e ausências</h3>
          <p>
            A referência estadual exige ao menos <strong>10 postos</strong> na semana. A comparação municipal exige ao menos{' '}
            <strong>3 postos</strong> no município e UF elegível. Abaixo disso, o preço observado continua visível, mas o desvio percentual fica bloqueado.
            Ausência de coleta permanece ausência (nunca zero), e a última semana (<code>29–30/06/2026</code>) é sinalizada como parcial.
          </p>
        </article>

        <article className="method-card">
          <h3>3. Malha IBGE e extremos preservados</h3>
          <p>
            Os polígonos usam a malha simplificada oficial da API v3 do IBGE (snapshot atual, sem reconstituir divisas históricas)
            e os rótulos municipais usam as sedes oficiais (SIRGAS 2000). Extremos positivos incomuns (<code>lo</code> / <code>hi</code>)
            são preservados das coletas aceitas.
          </p>
        </article>

        {manifest.stationLayer && (
          <article className="method-card">
            <h3>4. Postos individualizados (Cadastro ANP)</h3>
            <p>
              Os marcadores carregam sob demanda ao abrir uma UF, cruzando o histórico de preços com o cadastro da API de revendedores
              da ANP consultado em <strong>{date(manifest.stationLayer.snapshotAt)}</strong>:{' '}
              <strong>{count(manifest.stationLayer.stationCount)}</strong> de {count(manifest.stationLayer.historicalStationCount)} postos
              ({manifest.stationLayer.stationWeekCoveragePercent.toFixed(1).replace('.', ',')}% das linhas posto-semana), acurácia informada de{' '}
              {manifest.stationLayer.accuracyMeters.min} a {manifest.stationLayer.accuracyMeters.max} m (mediana{' '}
              {manifest.stationLayer.accuracyMeters.median} m). A ANP classifica essas coordenadas como{' '}
              <em>“{manifest.stationLayer.validationStatus}”</em>, e o endereço atual pode diferir da época da coleta.
            </p>
          </article>
        )}
      </div>

      {checks.length > 0 && (
        <div className="proof-box">
          <div className="proof-box-head">
            <ShieldCheck size={17} />
            <strong>Reconciliação criptográfica com o Microsoft Fabric</strong>
            <span>Snapshot de {date(manifest.dataset.snapshotAt)}</span>
          </div>
          <div className="proof-rows">
            <div className="proof-row">
              <span>Publicação Gold (SHA-256)</span>
              <code>{manifest.dataset.publicationHash.slice(0, 20)}…</code>
            </div>
            {checks.map(([table, spec]) => (
              <div className="proof-row" key={table}>
                <span>
                  <Layers size={13} /> {table} ({count(spec.rows)} linhas)
                </span>
                <code>{spec.businessSha256.slice(0, 20)}…</code>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="dialog-links">
        <a href={`${import.meta.env.BASE_URL}data/manifest.json`} target="_blank" rel="noreferrer">
          Manifesto JSON <ExternalLink size={13} />
        </a>
        <a href={`${import.meta.env.BASE_URL}data/validation.json`} target="_blank" rel="noreferrer">
          Recibo de validação <ExternalLink size={13} />
        </a>
        {manifest.stationLayer && (
          <a href={manifest.stationLayer.documentation} target="_blank" rel="noreferrer">
            Manual API ANP <ExternalLink size={13} />
          </a>
        )}
        <a href="https://servicodados.ibge.gov.br/api/docs/malhas?versao=3" target="_blank" rel="noreferrer">
          Malhas IBGE v3 <ExternalLink size={13} />
        </a>
        <a href="https://github.com/victorhobdev/fuel-watch-br" target="_blank" rel="noreferrer">
          Repositório Fuel Watch BR <ExternalLink size={13} />
        </a>
      </div>
    </dialog>
  );
}

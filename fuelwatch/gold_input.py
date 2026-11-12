"""Contrato de consumo M03 para M04, sem dependência de Spark."""

from uuid import UUID


def select_m03_contract(summaries, manifest, active_snapshot_id):
    """Aceita somente recibos bem-sucedidos da seleção ativa, com identidade/negócio revisados."""
    candidates = []
    fields = ["cnpj", "cnpj_origem", "produto", "data_coleta", "preco_venda", "moeda", "unidade", "uf",
              "municipio_ibge", "municipio_origem", "revenda_observada", "bandeira_observada", "preco_incomum_iqr"]
    for path, summary in summaries:
        if not isinstance(summary, dict) or not isinstance(summary.get("consumer_contract"), dict):
            continue
        contract = summary.get("consumer_contract", {})
        if (summary.get("status") != "m03_official_selection_validated" or summary.get("environment") != "fabric"
                or summary.get("official_integration_implemented") is not True
                or summary.get("replay_without_active_commit") is not True or summary.get("m02_inputs_unchanged") is not True):
            continue
        if (contract.get("table") != "silver_preco_publicado" or contract.get("snapshot_id") != active_snapshot_id
                or contract.get("scope_id") != manifest["scope"]["scope_id"]
                or contract.get("source_sha256") != manifest["source_sha256"]
                or contract.get("ibge_sha256") != manifest["ibge_sha256"] or contract.get("business_fields") != fields):
            continue
        number = contract.get("delta_version")
        try:
            UUID(contract["snapshot_id"])
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        if type(number) is not int or number < 0:
            continue
        if (summary.get("silver_rows"), summary.get("stations"), summary.get("municipalities"), summary.get("unusual_iqr_rows")) != (8052, 502, 27, 26):
            continue
        candidates.append((number, summary.get("finished_at_utc", ""), path, contract))
    if not candidates:
        raise ValueError("Nenhum consumer_contract M03 valido para o snapshot ativo. Concluir notebook 06 antes do M04.")
    _, _, path, contract = max(candidates, key=lambda c: (c[0], c[1], c[2]))
    return path, dict(contract)

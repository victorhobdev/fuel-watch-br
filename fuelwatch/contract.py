from datetime import datetime, date
from decimal import Decimal
import json
import re
import unicodedata


def normalize_name(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).upper().split())


def municipality_lookup(items):
    lookup = {}
    for item in items:
        uf = item["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        key = (uf, normalize_name(item["nome"]))
        lookup.setdefault(key, []).append(str(item["id"]))
    return lookup


def validate_row(raw, lookup, scope):
    """Retorna observação tipada ou motivos; não decide sobre preço incomum."""
    reasons = []
    cnpj_source = raw["CNPJ da Revenda"]
    cnpj = re.sub(r"[./-]", "", cnpj_source.strip())
    if not re.fullmatch(r"\d{14}", cnpj, flags=re.ASCII):
        reasons.append("cnpj_formato_invalido")
    for field in ["Revenda", "Bandeira", "Municipio", "Produto", "Estado - Sigla"]:
        if not raw[field].strip():
            reasons.append("obrigatorio_ausente:" + field)
    collected = None
    value = raw["Data da Coleta"]
    try:
        collected = datetime.strptime(value, "%d/%m/%Y").date()
        if collected.strftime("%d/%m/%Y") != value:
            raise ValueError("Formato não canônico")
        if not date.fromisoformat(scope["date_start"]) <= collected <= date.fromisoformat(scope["date_end"]):
            reasons.append("data_fora_do_semestre")
    except ValueError:
        reasons.append("data_coleta_invalida")
    price = None
    if not re.fullmatch(r"[0-9]{1,7}(,[0-9]{1,3})?", raw["Valor de Venda"]):
        reasons.append("preco_formato_ou_precisao_invalida")
    else:
        price = Decimal(raw["Valor de Venda"].replace(",", ".")).quantize(Decimal("0.001"))
        if price <= 0:
            reasons.append("preco_nao_positivo")
    if raw["Unidade de Medida"].strip() != "R$ / litro":
        reasons.append("unidade_incompativel_com_gasolina")
    codes = lookup.get((raw["Estado - Sigla"].strip(), normalize_name(raw["Municipio"])), [])
    if len(codes) != 1:
        reasons.append("municipio_ambiguo" if codes else "municipio_sem_correspondencia")
    if reasons:
        return None, reasons
    return {
        "cnpj": cnpj, "cnpj_origem": cnpj_source, "produto": raw["Produto"].strip(),
        "data_coleta": collected, "preco_venda": price, "moeda": "BRL", "unidade": "litro",
        "uf": raw["Estado - Sigla"].strip(), "municipio_ibge": codes[0],
        "municipio_origem": raw["Municipio"], "revenda_observada": raw["Revenda"].strip(),
        "bandeira_observada": raw["Bandeira"].strip(),
    }, []


def classify_rows(rows, lookup, scope):
    """Contabiliza inválidas, duplicatas exatas e TODAS as linhas de chaves conflitantes."""
    valid, invalid, duplicates = [], [], []
    seen = set()
    for source_record, raw in rows:
        typed, reasons = validate_row(raw, lookup, scope)
        if reasons:
            invalid.append({"source_record": source_record, "reasons": reasons, "raw": raw})
            continue
        fingerprint = tuple(sorted(raw.items()))
        if fingerprint in seen:
            duplicates.append({"source_record": source_record, "raw": raw})
            continue
        seen.add(fingerprint)
        typed["source_record"] = source_record
        typed["raw_json"] = json.dumps(raw, ensure_ascii=False)
        valid.append(typed)
    groups = {}
    for row in valid:
        key = tuple(row[x] for x in ["cnpj", "produto", "data_coleta", "unidade"])
        groups.setdefault(key, []).append(row)
    accepted, conflicts = [], []
    for group in groups.values():
        (conflicts if len(group) > 1 else accepted).extend(group)
    return accepted, invalid, duplicates, conflicts

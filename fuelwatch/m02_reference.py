"""Contrato de intercâmbio do M02; funções sem dependência de Spark."""

from decimal import Decimal
import gzip
import hashlib
import json
from statistics import quantiles

from fuelwatch.contract import municipality_lookup, normalize_name

RAW_COLUMNS = [
    "regiao_sigla", "uf", "municipio", "revenda", "cnpj_revenda", "nome_rua",
    "numero_rua", "complemento", "bairro", "cep", "produto", "data_coleta",
    "valor_venda", "valor_compra", "unidade_medida", "bandeira",
]
HEADERS = [
    "Regiao - Sigla", "Estado - Sigla", "Municipio", "Revenda", "CNPJ da Revenda",
    "Nome da Rua", "Numero Rua", "Complemento", "Bairro", "Cep", "Produto",
    "Data da Coleta", "Valor de Venda", "Valor de Compra", "Unidade de Medida", "Bandeira",
]
TYPED_FIELDS = [
    "cnpj", "cnpj_origem", "produto", "data_coleta", "preco_venda", "moeda", "unidade",
    "uf", "municipio_ibge", "municipio_origem", "revenda_observada", "bandeira_observada",
]
BUSINESS_FIELDS = TYPED_FIELDS + ["preco_incomum_iqr"]


def decode_reference(payload, expected_sha256):
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("Hash do snapshot IBGE diverge do aprovado")
    decoded = gzip.decompress(payload) if payload.startswith(b"\x1f\x8b") else payload
    items = json.loads(decoded.decode("utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("Snapshot IBGE vazio ou com estrutura inesperada")
    lookup = municipality_lookup(items)
    if len({str(item["id"]) for item in items}) != len(items):
        raise ValueError("Códigos IBGE duplicados")
    if any(len(ids) != 1 or uf != "RJ" for (uf, _), ids in lookup.items()):
        raise ValueError("Referência com ambiguidade ou UF diferente de RJ")
    rows = [{"municipio_ibge": str(item["id"]), "nome": item["nome"], "uf": "RJ",
             "nome_normalizado": normalize_name(item["nome"])} for item in items]
    return rows, lookup


def iqr_fences(prices):
    """Quartis inclusivos exatos, equivalentes ao ensaio local; somente uma fatia."""
    if not prices:
        raise ValueError("Não calcular IQR sem preços aceitos")
    if not all(isinstance(p, Decimal) for p in prices):
        raise TypeError("IQR requer Decimal; não converter preços para float")
    q1, _, q3 = quantiles(sorted(prices), n=4, method="inclusive") if len(prices) > 1 else [prices[0]] * 3
    spread = Decimal("1.5") * (q3 - q1)
    return q1 - spread, q3 + spread


def synthetic_rows():
    """14 entregas sintéticas: 9 aceitas, 2 inválidas, 1 repetição e 2 conflitos."""
    base = dict.fromkeys(RAW_COLUMNS, "")
    base.update({"regiao_sigla": "SE", "uf": "RJ", "municipio": "RIO DE JANEIRO",
                 "revenda": "LAB M02 SINTETICO", "cnpj_revenda": " 00.000.000/0000-00",
                 "produto": "GASOLINA", "valor_venda": "6,10", "unidade_medida": "R$ / litro",
                 "bandeira": "LAB SINTETICA"})
    rows = [{**base, "data_coleta": f"{day:02d}/01/2026"} for day in range(1, 9)]
    rows += [dict(rows[0]), {**base, "data_coleta": "09/01/2026", "valor_venda": "99,90"},
             {**base, "data_coleta": "10/01/2026", "valor_venda": "-1"},
             {**base, "data_coleta": "31/02/2026"},
             {**base, "data_coleta": "11/01/2026", "valor_venda": "6,30"},
             {**base, "data_coleta": "11/01/2026", "valor_venda": "6,40"}]
    return rows

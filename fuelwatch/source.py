import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HEADERS = [
    "Regiao - Sigla", "Estado - Sigla", "Municipio", "Revenda", "CNPJ da Revenda",
    "Nome da Rua", "Numero Rua", "Complemento", "Bairro", "Cep", "Produto",
    "Data da Coleta", "Valor de Venda", "Valor de Compra", "Unidade de Medida", "Bandeira",
]


def source_record(source_id, root=ROOT):
    records = [json.loads(line) for line in (root / "data/manifest/downloads.jsonl").read_text(encoding="utf-8").splitlines()]
    record = next(r for r in reversed(records) if r["source_id"] == source_id and r["status"] in {"downloaded", "identical_content"})
    path = root / record["path"]
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != record["sha256"]:
            raise ValueError("SHA-256 divergente: entrega local alterada")
    return record, path.read_bytes()


def read_anp(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) != 1 or not members[0].filename.lower().endswith(".csv"):
            raise ValueError("Contrato exige ZIP com um único CSV")
        content = archive.read(members[0])
        member = members[0].filename
    # Decode estrito antes do parser: latin-1 aceitaria bytes UTF-8 com texto corrompido.
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";", strict=True)
    if next(reader) != HEADERS:
        raise ValueError("Layout ANP mudou; revisar contrato antes de continuar")
    for number, row in enumerate(reader, start=2):
        if len(row) != len(HEADERS):
            raise ValueError(f"Registro CSV {number} possui {len(row)} campos")
    frame = pd.read_csv(io.BytesIO(content), sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return frame, {"csv_member": member, "csv_sha256": hashlib.sha256(content).hexdigest(),
                   "csv_bytes": len(content), "utf8_bom": content.startswith(b"\xef\xbb\xbf")}


def read_ibge(payload, content_encoding):
    if content_encoding == "gzip":
        payload = gzip.decompress(payload)
    elif content_encoding not in {None, "identity"}:
        raise ValueError(f"Content-Encoding não suportado: {content_encoding}")
    return json.loads(payload.decode("utf-8"))

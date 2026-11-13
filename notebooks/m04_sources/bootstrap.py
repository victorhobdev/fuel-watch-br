"""Célula compartilhada: só carregar o pacote depois de conferir os hashes."""
import hashlib
import json
from pathlib import Path
import sys

bundle_dir = Path(p_bundle_dir).resolve()
files_root = Path("/lakehouse/default/Files").resolve()
if not bundle_dir.is_relative_to(files_root):
    raise ValueError("Bundle deve estar em Files no Lakehouse padrão")
manifest_bytes = (bundle_dir / "manifest.json").read_bytes()
if hashlib.sha256(manifest_bytes).hexdigest() != p_expected_manifest_sha256:
    raise ValueError("Manifesto diferente do pacote aprovado; revisar upload/versão")
manifest = json.loads(manifest_bytes.decode("utf-8"))
for name, spec in manifest["files"].items():
    content = (bundle_dir / name).read_bytes()
    if len(content) != spec["bytes"] or hashlib.sha256(content).hexdigest() != spec["sha256"]:
        raise ValueError(f"Arquivo do bundle não confere: {name}")
rules_path = Path(p_rules_library_path).resolve() if p_rules_library_path else bundle_dir / "fuelwatch_rules.zip"
if not rules_path.is_relative_to(files_root):
    raise ValueError("Biblioteca deve estar em Files no Lakehouse padrao")
if hashlib.sha256(rules_path.read_bytes()).hexdigest() != manifest["files"]["fuelwatch_rules.zip"]["sha256"]:
    raise ValueError("Biblioteca compartilhada difere do pacote aprovado")
spark.sparkContext.addPyFile(str(rules_path))
spark.conf.set("spark.sql.session.timeZone", "UTC")
print(json.dumps({"status": "bundle_verified", "spark_version": spark.version,
                  "python_version": sys.version.split()[0],
                  "manifest_sha256": p_expected_manifest_sha256}))

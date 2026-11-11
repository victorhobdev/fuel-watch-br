"""Preserva entregas oficiais por SHA-256; nunca sobrescreve uma versão anterior."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def download(source_id, spec, root=ROOT):
    run_id = str(uuid.uuid4())
    staging = root / "data" / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    record = {"run_id": run_id, "source_id": source_id, **spec, "started_at_utc": now()}
    temp = None
    try:
        request = urllib.request.Request(spec["url"], headers={"User-Agent": "FuelWatchBR/0.1 (public-data-study)"})
        with urllib.request.urlopen(request, timeout=60) as response:
            record.update({"http_status": response.status, "resolved_url": response.url,
                           "content_type": response.headers.get("Content-Type"),
                           "content_encoding": response.headers.get("Content-Encoding"),
                           "last_modified": response.headers.get("Last-Modified"),
                           "etag": response.headers.get("ETag")})
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=staging, delete=False) as output:
                temp = Path(output.name)
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    output.write(chunk)
            expected = response.headers.get("Content-Length")
            if expected is not None and size != int(expected):
                raise ValueError("Download incompleto: Content-Length divergente")
        sha = digest.hexdigest()
        destination = root / "data" / "raw" / source_id / sha / spec["filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            with destination.open("rb") as preserved:
                preserved_sha = hashlib.file_digest(preserved, "sha256").hexdigest()
            if preserved_sha != sha:
                raise ValueError("Entrega preservada foi alterada localmente")
            temp.unlink()
            state = "identical_content"
        else:
            temp.replace(destination)
            state = "downloaded"
        record.update({"status": state, "sha256": sha, "bytes": size,
                       "path": destination.relative_to(root).as_posix()})
    except Exception as exc:
        record.update({"status": "failed", "error_type": type(exc).__name__})
        raise
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
        record["finished_at_utc"] = now()
        manifest = root / "data" / "manifest" / "downloads.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


if __name__ == "__main__":
    sources = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    for key, spec in sources.items():
        print(json.dumps(download(key, spec), ensure_ascii=False), flush=True)

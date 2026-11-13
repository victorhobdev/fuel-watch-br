"""Confere um refresh real contra a referencia canonica, sem repetir refresh."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

import pyodbc

from client import ROOT
from warehouse import connect, results

parser = argparse.ArgumentParser()
parser.add_argument("job_id")
parser.add_argument("--same-as")
args = parser.parse_args()
folder = ROOT / ".local/m06-api" / args.job_id
accepted = json.loads((folder / "accepted.json").read_text())
state = json.loads((folder / "job.json").read_text())
invalid = accepted["fixture_invalid"]
assert state["status"] == ("Failed" if invalid else "Completed"), state
if invalid:
    error = json.dumps(state.get("failureReason"), ensure_ascii=False)
    assert "M06_REFERENCE_CONTRACT" in error or "Esperados 92 municipios" in error, error

sha = "2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0"
connection = connect()
try:
    cursor = connection.cursor()
    reference = results(cursor.execute("SELECT municipio_ibge,nome,uf FROM [lh_fuelwatch].[dbo].[ref_municipio_ibge] WHERE ibge_sha256=?", sha))[0]
    reference = [{key: value.strip() for key, value in row.items()} for row in reference]
    assert len(reference) == len({row["municipio_ibge"] for row in reference}) == 92
    serialized = sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in reference)
    digest = hashlib.sha256("\n".join(serialized).encode()).hexdigest()
    if args.same_as:
        previous = json.loads((ROOT / args.same_as).read_text(encoding="utf-8"))
        assert digest == previous["reference_projection_sha256"], "Referencia canonica mudou"
    target_rows = None
    column_types = None
    if not invalid:
        deadline = time.monotonic() + 300
        while True:
            try:
                target = results(cursor.execute("SELECT municipio_ibge,nome,uf FROM [lh_fuelwatch].[dbo].[lab_m06_municipios]"))[0]
                break
            except pyodbc.ProgrammingError as error:
                if "208" not in str(error) or time.monotonic() >= deadline:
                    raise
                print(json.dumps({"status": "waiting_for_sql_endpoint_table"}), flush=True)
                time.sleep(15)
        assert len(target) == len({row["municipio_ibge"] for row in target}) == 92
        assert sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in target) == serialized, "Dataflow divergiu da projecao canonica"
        column_types = results(cursor.execute("SELECT COLUMN_NAME,DATA_TYPE FROM [lh_fuelwatch].INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='lab_m06_municipios'"))[0]
        assert len(column_types) == 3 and all(row["DATA_TYPE"] in {"varchar", "nvarchar", "char", "nchar"} for row in column_types)
        target_rows = len(target)
finally:
    connection.close()

report = {"environment": "fabric", "job_id": args.job_id, "case": accepted["case"],
          "status": "m06_refresh_verified", "job_status": state["status"], "fixture_invalid": invalid,
          "failure_reason": state.get("failureReason"), "checked_at_utc": datetime.now(timezone.utc).isoformat(),
          "reference_rows": 92, "target_rows": target_rows, "column_types": column_types,
          "ibge_sha256": sha, "reference_projection_sha256": digest,
          "full_projection_comparison_passed": not invalid, "same_as": args.same_as}
(folder / "verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"job_id": args.job_id, "status": report["status"], "case": accepted["case"]}), flush=True)

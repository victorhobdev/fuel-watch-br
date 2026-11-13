"""Prepara JSON nativo a partir de atividades lidas na interface Fabric.

Os bindings permanecem placeholders no disco. Aplicacao e execucao sao etapas distintas.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "data/artifacts/m05/warehouse"
OUTPUT = ROOT / "data/artifacts/m05/pipeline-template.json"
BASELINES = json.loads((ROOT / "fabric/m05/activity-baselines.json").read_text(encoding="utf-8"))["activities"]
BY_TYPE = {a["type"]: a for a in BASELINES}
EXPRESSIONS = {
    "{{ROOT_RUN_ID}}": "pipeline().RunId",
    "{{BATCH_ID}}": "json(activity('Export_Gold_Input').output.result.exitValue).batch_id",
    "{{FAULT_STAGE}}": "pipeline().parameters.p_fault_stage",
}


def expression(value):
    return {"value": value, "type": "Expression"}


def sql_expression(sql):
    parts = re.split(r"(\{\{(?:ROOT_RUN_ID|BATCH_ID|FAULT_STAGE)\}\})", sql)
    arguments = [EXPRESSIONS[p] if p in EXPRESSIONS else "'" + p.replace("'", "''") + "'"
                 for p in parts if p]
    return expression("@concat(" + ",".join(arguments) + ")")


def dependency(name, status="Succeeded"):
    return [{"activity": name, "dependencyConditions": [status]}] if name else []


def policy(activity):
    activity["policy"].update(timeout="0.00:30:00", retry=0, retryIntervalInSeconds=30)


def script(name, content, previous=None, condition="Succeeded", retries=0):
    item = deepcopy(BY_TYPE["Script"])
    item.update(name=name, dependsOn=dependency(previous, condition))
    policy(item)
    item["policy"]["retry"] = retries
    item["typeProperties"] = {"scripts": [{"type": "Query", "text": sql_expression(content)}],
                              "scriptBlockExecutionTimeout": "00:10:00"}
    return item


def notebook(name, phase, previous):
    item = deepcopy(BY_TYPE["TridentNotebook"])
    item.update(name=name, dependsOn=dependency(previous))
    policy(item)
    values = {"p_root_run_id": expression("@pipeline().RunId"), "p_phase": phase,
              "p_fault_stage": expression("@pipeline().parameters.p_fault_stage"),
              "p_scope_id": expression("@pipeline().parameters.p_scope_id"),
              "p_source_sha256": expression("@pipeline().parameters.p_source_sha256")}
    item["typeProperties"]["parameters"] = {k: {"value": v, "type": "string"} for k, v in values.items()}
    return item


def fail(name, previous, code):
    return {"name": name, "type": "Fail", "dependsOn": dependency(previous),
            "typeProperties": {"errorCode": code,
                               "message": "Falha preservada: consultar a atividade original e o guard da publicacao anterior."}}


def build():
    read = lambda name: (SQL / name).read_text(encoding="utf-8")
    copy = deepcopy(BY_TYPE["Copy"])
    copy.update(name="Copy_ANP", dependsOn=dependency("Capture_Baseline"))
    policy(copy)
    location = copy["typeProperties"]["source"]["datasetSettings"]["typeProperties"]["location"]
    location["relativeUrl"] = expression("@pipeline().parameters.p_source_relative_url")
    activities = [script("Capture_Baseline", read("00_setup.sql") + "\n" + read("01_capture.sql")), copy,
                  notebook("Bronze", "bronze", "Copy_ANP"), notebook("Silver", "silver", "Bronze"),
                  notebook("Export_Gold_Input", "export", "Silver"),
                  script("Import_Gold", read("30_import.sql"), "Export_Gold_Input", retries=3),
                  script("Publish_Gold", read("31_publish.sql"), "Import_Gold"),
                  script("Validate_Gold", read("32_validate.sql"), "Publish_Gold"),
                  script("Guard_Silver_Failure", read("90_assert_unchanged.sql"), "Silver", "Failed"),
                  fail("Fail_Silver", "Guard_Silver_Failure", "M05_SILVER_FAILED"),
                  script("Guard_Gold_Failure", read("90_assert_unchanged.sql"), "Publish_Gold", "Failed"),
                  fail("Fail_Gold", "Guard_Gold_Failure", "M05_GOLD_FAILED")]
    defaults = {
        "p_source_relative_url": "/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/dsas/ca/ca-2026-01.zip",
        "p_source_sha256": "a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c",
        "p_scope_id": "anp-2026-1-rj-gasolina", "p_fault_stage": "none"}
    return {"name": "pl_fuelwatch_master", "properties": {"activities": activities,
            "parameters": {k: {"type": "string", "defaultValue": v} for k, v in defaults.items()},
            "annotations": ["M05 serial laboratory; runtime validation required"]}}


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "m05_pipeline_template_prepared", "activities": 12,
                      "fabric_executed": False, "bindings": "placeholders"}))

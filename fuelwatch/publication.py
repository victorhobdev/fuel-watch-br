"""Contrato de promoção oficial; sem dependência de Spark ou acesso a serviços."""

import re

IDENTITY_FIELDS = ["scope_id", "source_sha256", "ibge_sha256", "contract_version"]


def policy_identity(policy):
    return {"scope_id": policy["scope"]["scope_id"], "source_sha256": policy["source_sha256"],
            "ibge_sha256": policy["ibge_sha256"], "contract_version": policy["scope"]["contract_version"]}


def validate_publication_policy(policy, manifest):
    if policy.get("complete_snapshot") is not True or policy.get("is_synthetic") is not False:
        raise ValueError("Exigir snapshot completo oficial")
    if policy.get("scope") != manifest["scope"] or policy.get("source_id") != manifest["scope"]["anp_source_id"]:
        raise ValueError("Escopo/fonte diferentes do pacote revisado")
    if not re.fullmatch(r"[a-z0-9_-]+", policy["scope"]["scope_id"]):
        raise ValueError("Identificador de escopo inválido")
    for field, expected in [("source_sha256", manifest["anp"]["sha256"]),
                            ("ibge_sha256", manifest["ibge"]["sha256"])]:
        if policy.get(field) != expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Hash não corresponde ao snapshot revisado")
    delta = policy.get("approved_delta")
    if not isinstance(delta, dict) or set(delta) != {"inserted", "removed", "updated"}:
        raise ValueError("Delta revisado ausente")
    if any(type(value) is not int or value < 0 for value in delta.values()):
        raise ValueError("Delta revisado inválido")


def publication_decision(policy, previous_identity, delta, business_equal):
    if previous_identity == policy_identity(policy):
        if any(delta.values()) or business_equal is not True:
            raise ValueError("Mesma identidade produziu negócio diferente; não sobrescrever")
        return "replayed"
    if previous_identity != policy.get("expected_previous_identity"):
        raise ValueError("Seleção anterior diferente da esperada; bloquear promoção desatualizada")
    if delta != policy["approved_delta"]:
        raise ValueError("Inclusões, remoções ou alterações fora do delta revisado")
    return "published"

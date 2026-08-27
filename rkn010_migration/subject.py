from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import SourceRow


class SubjectResolutionError(ValueError):
    pass


def _dig(value: dict[str, Any], *path: str) -> Any:
    current: Any = value
    for item in path:
        if not isinstance(current, dict):
            return None
        current = current.get(item)
    return current


def organisation_name(hit: dict[str, Any]) -> str:
    return str(
        _dig(hit, "subject", "data", "organization", "name")
        or _dig(hit, "data", "organization", "name")
        or _dig(hit, "organization", "name")
        or hit.get("name")
        or hit.get("header")
        or ""
    ).strip()


def build_subject(hit: dict[str, Any], source: SourceRow) -> dict[str, Any]:
    candidate = hit.get("subject") if isinstance(hit.get("subject"), dict) else hit
    candidate = deepcopy(candidate)
    if isinstance(candidate.get("data"), dict) and isinstance(candidate["data"].get("organization"), dict):
        subject = candidate
    else:
        organization = candidate.get("organization") if isinstance(candidate.get("organization"), dict) else candidate
        organization = deepcopy(organization)
        for key in ("_id", "guid", "dateCreation", "dateLastModification", "parentEntries", "entityType"):
            organization.pop(key, None)
        organization.setdefault("ogrn", source.ogrn)
        organization.setdefault("name", source.org_name)
        if source.short_org_name:
            organization.setdefault("shortName", source.short_org_name)
        subject = {
            "data": {"person": {}, "organization": organization},
            "kind": {
                "name": "Участник",
                "type": "participant",
                "subKind": {
                    "name": "Юридическое лицо",
                    "shortHeader": ["f|data.organization.shortName"],
                    "specialTypeId": "ulApplicant",
                },
            },
            "header": f"{source.short_org_name or source.org_name}, ОГРН: {source.ogrn}",
            "shortHeader": source.short_org_name or source.org_name,
            "entityType": "subjects",
            "parentEntries": "RKN010Appeals.subjects",
            "specialTypeId": "ulApplicant",
        }

    organization = _dig(subject, "data", "organization")
    if not isinstance(organization, dict):
        raise SubjectResolutionError("Карточка организации не содержит data.organization")
    if str(organization.get("ogrn") or "") != source.ogrn:
        raise SubjectResolutionError("ОГРН найденного субъекта не совпадает с исходной строкой")

    subject.pop("_id", None)
    subject.pop("dateCreation", None)
    subject.pop("dateLastModification", None)
    subject["entityType"] = "subjects"
    subject["parentEntries"] = "RKN010Appeals.subjects"
    subject.setdefault("specialTypeId", "ulApplicant")
    subject.setdefault("header", f"{source.short_org_name or source.org_name}, ОГРН: {source.ogrn}")
    subject.setdefault("shortHeader", source.short_org_name or source.org_name)
    return subject


def validate_subject(subject: dict[str, Any]) -> list[str]:
    required = {
        "data.organization.ogrn": _dig(subject, "data", "organization", "ogrn"),
        "data.organization.name": _dig(subject, "data", "organization", "name"),
        "kind.type": _dig(subject, "kind", "type"),
        "kind.subKind.specialTypeId": _dig(subject, "kind", "subKind", "specialTypeId"),
        "header": subject.get("header"),
        "specialTypeId": subject.get("specialTypeId"),
    }
    return [path for path, value in required.items() if value in (None, "", {})]

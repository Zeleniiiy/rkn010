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


def _first(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "", {}, [])), None)


def _is_ip(source: SourceRow) -> bool:
    return len(source.ogrn) == 15


def _subject_kind(ip: bool) -> dict[str, Any]:
    special_type = "ipApplicant" if ip else "ulApplicant"
    name = "Индивидуальный предприниматель" if ip else "Юридическое лицо"
    short_header = ["f|data.person.lastName"] if ip else ["f|data.organization.shortName"]
    return {
        "name": "Участник",
        "type": "participant",
        "subKind": {
            "name": name,
            "shortHeader": short_header,
            "specialTypeId": special_type,
        },
    }


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
        ip = _is_ip(source)
        card = candidate.get("organization") if isinstance(candidate.get("organization"), dict) else candidate
        card = deepcopy(card)
        for key in ("_id", "guid", "dateCreation", "dateLastModification", "parentEntries", "entityType"):
            card.pop(key, None)
        xsd_data = deepcopy(candidate.get("xsdData")) if isinstance(candidate.get("xsdData"), dict) else {}
        for field in ("phone", "email", "factAddress", "nameIP", "birthPlace"):
            if field not in xsd_data and card.get(field) not in (None, "", {}, []):
                xsd_data[field] = deepcopy(card[field])
        if ip:
            person_source = card.get("person") if isinstance(card.get("person"), dict) else card
            person = deepcopy(person_source)
            person.setdefault("ogrn", source.ogrn)
            data = {"person": person, "organization": {}}
            special_type = "ipApplicant"
        else:
            organization = card
            organization.setdefault("ogrn", source.ogrn)
            organization.setdefault("name", source.org_name)
            if source.short_org_name:
                organization.setdefault("shortName", source.short_org_name)
            organization.setdefault(
                "organizationalForm",
                _first(card.get("organizationalForm"), card.get("organizationForm")),
            )
            organization.setdefault(
                "registrationAddress",
                _first(card.get("registrationAddress"), card.get("legalAddress"), card.get("baseAddress")),
            )
            data = {"person": {}, "organization": organization}
            special_type = "ulApplicant"
        subject = {
            "data": data,
            "xsdData": xsd_data,
            "kind": _subject_kind(ip),
            "header": f"{source.short_org_name or source.org_name}, ОГРН: {source.ogrn}",
            "shortHeader": source.short_org_name or source.org_name,
            "entityType": "subjects",
            "parentEntries": "RKN010Appeals.subjects",
            "specialTypeId": special_type,
        }

    identity = _dig(subject, "data", "person" if _is_ip(source) else "organization")
    if not isinstance(identity, dict):
        raise SubjectResolutionError("Карточка субъекта не содержит данные требуемого типа")
    if str(identity.get("ogrn") or "") != source.ogrn:
        raise SubjectResolutionError("ОГРН найденного субъекта не совпадает с исходной строкой")

    subject.pop("_id", None)
    subject.pop("dateCreation", None)
    subject.pop("dateLastModification", None)
    subject["entityType"] = "subjects"
    subject["parentEntries"] = "RKN010Appeals.subjects"
    subject.setdefault("specialTypeId", "ipApplicant" if _is_ip(source) else "ulApplicant")
    subject.setdefault("header", f"{source.short_org_name or source.org_name}, ОГРН: {source.ogrn}")
    subject.setdefault("shortHeader", source.short_org_name or source.org_name)
    return subject


def validate_subject(subject: dict[str, Any]) -> list[str]:
    special_type = subject.get("specialTypeId") or _dig(subject, "kind", "subKind", "specialTypeId")
    required: dict[str, Any] = {
        "kind.type": _dig(subject, "kind", "type"),
        "kind.subKind.specialTypeId": _dig(subject, "kind", "subKind", "specialTypeId"),
        "header": subject.get("header"),
        "specialTypeId": subject.get("specialTypeId"),
    }
    if special_type == "ipApplicant":
        required.update(
            {
                "data.person.ogrn": _dig(subject, "data", "person", "ogrn"),
                "data.person.lastName": _dig(subject, "data", "person", "lastName"),
                "data.person.firstName": _dig(subject, "data", "person", "firstName"),
                "data.person.middleName": _dig(subject, "data", "person", "middleName"),
                "data.person.inn": _dig(subject, "data", "person", "inn"),
                "xsdData.nameIP": _dig(subject, "xsdData", "nameIP"),
                "xsdData.birthPlace": _dig(subject, "xsdData", "birthPlace"),
            }
        )
    else:
        required.update(
            {
                "data.organization.ogrn": _dig(subject, "data", "organization", "ogrn"),
                "data.organization.organizationalForm": _dig(subject, "data", "organization", "organizationalForm"),
                "data.organization.name": _dig(subject, "data", "organization", "name"),
                "data.organization.shortName": _dig(subject, "data", "organization", "shortName"),
                "data.organization.inn": _dig(subject, "data", "organization", "inn"),
                "data.organization.registrationAddress": _dig(subject, "data", "organization", "registrationAddress"),
                "xsdData.phone": _dig(subject, "xsdData", "phone"),
                "xsdData.email": _dig(subject, "xsdData", "email"),
                "xsdData.factAddress": _dig(subject, "xsdData", "factAddress"),
            }
        )
    return [path for path, value in required.items() if value in (None, "", {}, [])]

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api import PgsClient, search_conditions
from .config import LICENSE_COLLECTION, ORGANIZATION_COLLECTION, RECORD_COLLECTION
from .mapping import build_license_payload, build_record_payload
from .models import LicensePlan
from .runlog import JsonlWriter
from .state import RunState
from .subject import build_subject, organisation_name, validate_subject


class MigrationError(RuntimeError):
    pass


@dataclass
class MigrationSummary:
    groups_total: int = 0
    groups_completed: int = 0
    groups_skipped: int = 0
    groups_failed: int = 0
    licenses_created: int = 0
    licenses_updated: int = 0
    records_created: int = 0
    records_updated: int = 0

    def to_dict(self) -> dict[str, int]:
        return vars(self).copy()


def _content(result: dict[str, Any]) -> list[dict[str, Any]]:
    content = result.get("content", [])
    return content if isinstance(content, list) else []


def _normalise_name(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", value.casefold().replace("ё", "е"))


def _created_document(response: dict[str, Any], payload: dict[str, Any], collection: str) -> dict[str, Any]:
    result = deepcopy(payload)
    if isinstance(response, dict):
        result.update(response)
    result.setdefault("parentEntries", collection)
    if not result.get("_id") or not result.get("guid"):
        raise MigrationError(f"Create {collection} did not return _id/guid")
    return result


def _preserve_file_metadata(desired: dict[str, Any], existing: Any) -> dict[str, Any]:
    """Keep already uploaded files when refreshing business fields in forRegistry."""
    result = deepcopy(desired)
    if not isinstance(existing, dict):
        return result
    old_orders = existing.get("order") if isinstance(existing.get("order"), list) else []
    for order in result.get("order", []):
        match = next(
            (
                old
                for old in old_orders
                if isinstance(old, dict)
                and old.get("order_num") == order.get("order_num")
                and old.get("order_date") == order.get("order_date")
            ),
            None,
        )
        if match and match.get("orderFile"):
            order["orderFile"] = deepcopy(match["orderFile"])
    old_cancellations = existing.get("cancellation") if isinstance(existing.get("cancellation"), list) else []
    for cancellation in result.get("cancellation", []):
        match = next(
            (
                old
                for old in old_cancellations
                if isinstance(old, dict)
                and old.get("cancellation_num") == cancellation.get("cancellation_num")
                and old.get("cancellation_date") == cancellation.get("cancellation_date")
            ),
            None,
        )
        if match and match.get("orderFile"):
            cancellation["orderFile"] = deepcopy(match["orderFile"])
    old_opinions = existing.get("expertOpinion") if isinstance(existing.get("expertOpinion"), list) else []
    if not result.get("expertOpinion"):
        result["expertOpinion"] = deepcopy(old_opinions)
    else:
        for opinion in result["expertOpinion"]:
            match = next(
                (
                    old
                    for old in old_opinions
                    if isinstance(old, dict) and old.get("opinionDate") == opinion.get("opinionDate")
                ),
                None,
            )
            if match and match.get("opinionFile"):
                opinion["opinionFile"] = deepcopy(match["opinionFile"])
    return result


class Migrator:
    def __init__(
        self,
        client: PgsClient | None,
        *,
        state: RunState,
        events: JsonlWriter,
        logger,
        execute: bool,
        strict_org_name: bool = True,
        operator_mode: bool = False,
        organization_id: str | None = None,
    ) -> None:
        self.client = client
        self.state = state
        self.events = events
        self.logger = logger
        self.execute = execute
        self.strict_org_name = strict_org_name
        self.operator_mode = operator_mode
        self.organization_id = organization_id
        self.summary = MigrationSummary()
        self._organization_cache: dict[str, dict[str, Any]] = {}

    def _require_client(self) -> PgsClient:
        if self.client is None:
            raise MigrationError("API client is required for live migration")
        return self.client

    def _search_organization(self, plan: LicensePlan) -> dict[str, Any]:
        if plan.ogrn in self._organization_cache:
            return self._organization_cache[plan.ogrn]
        client = self._require_client()
        conditions = [
            {"field": "ogrn", "operator": "eq", "value": plan.ogrn}
        ]
        if self.organization_id:
            conditions.append({"field": "_id", "operator": "eq", "value": self.organization_id})
        result = client.search(
            ORGANIZATION_COLLECTION,
            {
                "search": {
                    "search": [
                        {
                            "andSubConditions": conditions
                        }
                    ]
                },
                "size": 2,
            },
        )
        hits = _content(result)
        if len(hits) != 1:
            raise MigrationError(f"ОГРН {plan.ogrn}: найдено организаций {len(hits)}, ожидалась одна")
        found_name = organisation_name(hits[0])
        if self.strict_org_name and found_name and _normalise_name(found_name) != _normalise_name(plan.latest.org_name):
            raise MigrationError(
                f"ОГРН {plan.ogrn}: наименование в organizations не совпадает с Excel: "
                f"{found_name!r} != {plan.latest.org_name!r}"
            )
        self._organization_cache[plan.ogrn] = hits[0]
        return hits[0]

    def _find_license(self, plan: LicensePlan) -> dict[str, Any] | None:
        result = self._require_client().search(
            LICENSE_COLLECTION,
            search_conditions(
                {"field": "subject.data.organization.ogrn", "operator": "eq", "value": plan.ogrn},
                {"field": "number", "operator": "eq", "value": plan.geo_zone},
            ),
        )
        hits = _content(result)
        if len(hits) > 1:
            raise MigrationError(f"{plan.key}: найдено несколько лицензий")
        return hits[0] if hits else None

    def _find_record(self, license_id: str, regno: str, geo_zone: str) -> dict[str, Any] | None:
        result = self._require_client().search(
            RECORD_COLLECTION,
            search_conditions(
                {"field": "licenseId", "operator": "eq", "value": license_id},
                {"field": "xsdData.forRegistry.regno", "operator": "eq", "value": regno},
                {"field": "xsdData.forRegistry.geo_zone", "operator": "eq", "value": int(geo_zone)},
            ),
        )
        hits = _content(result)
        if len(hits) > 1:
            raise MigrationError(f"Лицензия {license_id}, рег. № {regno}: найдено несколько записей")
        return hits[0] if hits else None

    def _active_records(self, license_id: str) -> list[dict[str, Any]]:
        result = self._require_client().search(
            RECORD_COLLECTION,
            {
                **search_conditions(
                    {"field": "licenseId", "operator": "eq", "value": license_id},
                    {"field": "status", "operator": "eq", "value": "active"},
                ),
                "size": 100,
                "sort": "dateCreation,DESC",
            },
        )
        return _content(result)

    def _update_document(self, collection: str, document: dict[str, Any], **changes: Any) -> dict[str, Any]:
        before = deepcopy(document)
        updated = deepcopy(document)
        updated.update(changes)
        result = self._require_client().update(collection, updated)
        self.state.record_updated(collection, before)
        self.summary.records_updated += int(collection == RECORD_COLLECTION)
        self.summary.licenses_updated += int(collection == LICENSE_COLLECTION)
        self.events.write("updated", collection=collection, id=document.get("_id"), changes=changes)
        return result if isinstance(result, dict) else updated

    def _resolve_subject(self, plan: LicensePlan, existing_license: dict[str, Any] | None) -> dict[str, Any]:
        if existing_license and isinstance(existing_license.get("subject"), dict):
            subject = deepcopy(existing_license["subject"])
        else:
            subject = build_subject(self._search_organization(plan), plan.latest)
        missing = validate_subject(subject)
        if missing:
            raise MigrationError(f"{plan.key}: у субъекта отсутствуют обязательные поля: {', '.join(missing)}")
        return subject

    def write_dry_run(self, plans: list[LicensePlan], output: Path) -> MigrationSummary:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as stream:
            for plan in plans:
                fake_hit = {
                    "organization": {
                        "ogrn": plan.ogrn,
                        "name": plan.latest.org_name,
                        "shortName": plan.latest.short_org_name,
                    }
                }
                subject = build_subject(fake_hit, plan.latest)
                license_payload = build_license_payload(plan, subject)
                stream.write(
                    json.dumps(
                        {"kind": "license", "key": plan.key, "payload": license_payload},
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
                for index, row in enumerate(plan.rows):
                    record_payload = build_record_payload(
                        row,
                        subject=subject,
                        license_id=f"<license:{plan.key}>",
                        license_status=plan.license_status,
                        record_status="active" if index == len(plan.rows) - 1 else "reissued",
                        license_date_issued=license_payload.get("dateIssued"),
                        license_date_valid_to=license_payload.get("dateValidTo"),
                    )
                    stream.write(
                        json.dumps(
                            {"kind": "record", "key": row.record_key, "payload": record_payload},
                            ensure_ascii=False,
                            default=str,
                        )
                        + "\n"
                    )
        self.summary.groups_total = len(plans)
        return self.summary

    def migrate(self, plans: list[LicensePlan]) -> MigrationSummary:
        self.summary.groups_total = len(plans)
        for plan in plans:
            if self.state.completed(plan.key):
                self.summary.groups_skipped += 1
                continue
            if any(issue.severity == "error" for issue in plan.issues):
                error = MigrationError("; ".join(issue.message for issue in plan.issues))
                self._handle_failure(plan, error)
                self.summary.groups_failed += 1
                continue
            while True:
                try:
                    self._migrate_group(plan)
                    self.summary.groups_completed += 1
                    break
                except Exception as exc:
                    self._handle_failure(plan, exc)
                    if not self.operator_mode:
                        self.summary.groups_failed += 1
                        break
                    action = input(f"{plan.key}: [r]etry / [s]kip / [a]bort: ").strip().casefold() or "s"
                    if action in {"r", "retry", "п", "повтор"}:
                        continue
                    if action in {"a", "abort", "о", "остановить"}:
                        self.summary.groups_failed += 1
                        raise
                    self.summary.groups_failed += 1
                    break
        return self.summary

    def _handle_failure(self, plan: LicensePlan, exc: Exception) -> None:
        self.state.record_error(plan.key, exc)
        self.state.mark_group(plan.key, "failed", error=str(exc))
        self.events.write("group_failed", key=plan.key, error=str(exc))
        self.logger.error("%s: %s", plan.key, exc)

    def _migrate_group(self, plan: LicensePlan) -> None:
        client = self._require_client()
        self.state.mark_group(plan.key, "running")
        existing_license = self._find_license(plan)
        subject = self._resolve_subject(plan, existing_license)

        if existing_license is None:
            payload = build_license_payload(plan, subject)
            license_doc = _created_document(client.create(LICENSE_COLLECTION, payload), payload, LICENSE_COLLECTION)
            self.state.record_created(license_doc)
            self.summary.licenses_created += 1
            self.events.write("license_created", key=plan.key, id=license_doc["_id"])
        else:
            license_doc = existing_license

        license_id = str(license_doc["_id"])
        exact_records: dict[str, dict[str, Any] | None] = {
            row.record_key: self._find_record(license_id, row.regno, row.geo_zone) for row in plan.rows
        }

        historical_to_reissue: list[dict[str, Any]] = []
        for row in plan.rows[:-1]:
            existing = exact_records[row.record_key]
            if existing is None:
                payload = build_record_payload(
                    row,
                    subject=subject,
                    license_id=license_id,
                    license_status=plan.license_status,
                    record_status="reissued",
                    license_date_issued=license_doc.get("dateIssued"),
                    license_date_valid_to=license_doc.get("dateValidTo"),
                )
                created = _created_document(client.create(RECORD_COLLECTION, payload), payload, RECORD_COLLECTION)
                self.state.record_created(created)
                self.summary.records_created += 1
                self.events.write("record_created", key=row.record_key, id=created["_id"], status="reissued")
            elif existing.get("status") != "reissued":
                # Keep an existing active record untouched until the new active
                # record is safely created/promoted below.
                historical_to_reissue.append(existing)

        latest = plan.latest
        latest_existing = exact_records[latest.record_key]
        old_active = self._active_records(license_id)
        latest_id = str(latest_existing.get("_id")) if latest_existing else None
        old_active = [item for item in old_active if str(item.get("_id")) != latest_id]

        if latest_existing is None:
            payload = build_record_payload(
                latest,
                subject=subject,
                license_id=license_id,
                license_status=plan.license_status,
                record_status="active",
                license_date_issued=license_doc.get("dateIssued"),
                license_date_valid_to=license_doc.get("dateValidTo"),
            )
            latest_doc = _created_document(client.create(RECORD_COLLECTION, payload), payload, RECORD_COLLECTION)
            self.state.record_created(latest_doc)
            self.summary.records_created += 1
            self.events.write("record_created", key=latest.record_key, id=latest_doc["_id"], status="active")
        else:
            latest_doc = latest_existing
            if latest_doc.get("status") != "active":
                latest_doc = self._update_document(RECORD_COLLECTION, latest_doc, status="active")

        reissue_by_id = {
            str(item.get("_id")): item
            for item in [*old_active, *historical_to_reissue]
            if str(item.get("_id")) != str(latest_doc.get("_id"))
        }
        changed_old: list[dict[str, Any]] = []
        try:
            for active in reissue_by_id.values():
                changed_old.append(deepcopy(active))
                self._update_document(RECORD_COLLECTION, active, status="reissued")
        except Exception:
            for before in reversed(changed_old):
                try:
                    client.update(RECORD_COLLECTION, before)
                except Exception:
                    self.logger.exception("Compensation failed for record %s", before.get("_id"))
            if latest_existing is None:
                try:
                    client.delete(latest_doc)
                except Exception:
                    self.logger.exception("Compensation failed for new record %s", latest_doc.get("_id"))
            raise

        desired_license = build_license_payload(plan, subject)
        existing_annulled_at = license_doc.get("dateAnnulled")
        desired_for_registry = _preserve_file_metadata(
            desired_license["forRegistry"], license_doc.get("forRegistry")
        )
        license_changes = {
            "status": desired_license["status"],
            "forRegistry": desired_for_registry,
            "dateAnnulled": (
                existing_annulled_at or desired_license["dateAnnulled"]
                if desired_license["status"] == "annulled"
                else None
            ),
        }
        if existing_license and any(license_doc.get(key) != value for key, value in license_changes.items()):
            license_doc = self._update_document(LICENSE_COLLECTION, license_doc, **license_changes)

        active_after = self._active_records(license_id)
        if len(active_after) != 1 or str(active_after[0].get("_id")) != str(latest_doc.get("_id")):
            raise MigrationError(
                f"{plan.key}: после миграции active-записей {len(active_after)}, ожидалась последняя рег. № {latest.regno}"
            )
        self.state.mark_group(
            plan.key,
            "completed",
            license_id=license_id,
            active_record_id=latest_doc.get("_id"),
            active_regno=latest.regno,
        )
        self.events.write("group_completed", key=plan.key, license_id=license_id)
        self.logger.info("%s: completed", plan.key)

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from rkn010_migration.mapping import build_license_payload, build_record_payload
from rkn010_migration.migrator import Migrator
from rkn010_migration.models import LicensePlan
from rkn010_migration.runlog import JsonlWriter, setup_logging
from rkn010_migration.state import RunState

from conftest import full_subject


def dig(document, path):
    current = document
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


class FakeClient:
    def __init__(self):
        self.collections = {
            "organizations": [
                {
                    "ogrn": "1021600000001",
                    "name": "ПАО ТЕСТОВЫЙ ОПЕРАТОР",
                    "subject": full_subject(),
                }
            ],
            "RKN010_Licenses": [],
            "RKN010_Records": [],
        }
        self.operations = []
        self.next_id = 1

    def search(self, collection, body):
        conditions = body.get("search", {}).get("search", [])
        flat = []
        for condition in conditions:
            flat.extend(condition.get("andSubConditions", [condition]))
        result = []
        for document in self.collections[collection]:
            if all(self._matches(document, condition) for condition in flat):
                result.append(deepcopy(document))
        size = body.get("size", len(result))
        return {"content": result[:size]}

    def _matches(self, document, condition):
        value = dig(document, condition["field"])
        if condition["operator"] == "eq":
            return str(value) == str(condition["value"])
        if condition["operator"] == "notNull":
            return value is not None
        raise AssertionError(condition)

    def create(self, collection, payload):
        document = deepcopy(payload)
        document["_id"] = f"id-{self.next_id}"
        self.next_id += 1
        document.setdefault("guid", str(uuid4()))
        self.collections[collection].append(document)
        self.operations.append(("create", collection, document["_id"], document.get("status")))
        return deepcopy(document)

    def update(self, collection, document):
        for index, existing in enumerate(self.collections[collection]):
            if existing.get("_id") == document.get("_id"):
                self.collections[collection][index] = deepcopy(document)
                self.operations.append(("update", collection, document["_id"], document.get("status")))
                return deepcopy(document)
        raise AssertionError(f"not found: {collection}/{document.get('_id')}")

    def delete(self, document):
        collection = document["parentEntries"]
        self.collections[collection] = [item for item in self.collections[collection] if item.get("_id") != document.get("_id")]
        self.operations.append(("delete", collection, document.get("_id"), None))


def make_migrator(tmp_path: Path, client: FakeClient, suffix="one"):
    run_dir = tmp_path / suffix
    return Migrator(
        client,
        state=RunState(run_dir / "checkpoint.json", profile="test", workbook_hash=suffix),
        events=JsonlWriter(run_dir / "events.jsonl"),
        logger=setup_logging(run_dir),
        execute=True,
    )


def test_full_group_creates_one_license_history_and_active_annulled_record(tmp_path, source_row):
    older = source_row(regno="00000052")
    latest = source_row(
        excel_row=5,
        regno="00000092",
        include_order_number="101",
        exclude_order_number="200",
        exclude_order_date=datetime(2024, 2, 3),
    )
    plan = LicensePlan(older.license_key, older.ogrn, older.geo_zone, [older, latest], "annulled")
    client = FakeClient()
    summary = make_migrator(tmp_path, client).migrate([plan])
    assert summary.groups_completed == 1
    assert len(client.collections["RKN010_Licenses"]) == 1
    assert client.collections["RKN010_Licenses"][0]["status"] == "annulled"
    records = client.collections["RKN010_Records"]
    assert [item["status"] for item in records] == ["reissued", "active"]
    assert records[-1]["license"]["status"] == "annulled"


def test_new_active_is_created_before_old_active_is_reissued(tmp_path, source_row):
    older = source_row(regno="00000052")
    latest = source_row(excel_row=5, regno="00000092")
    plan = LicensePlan(older.license_key, older.ogrn, older.geo_zone, [older, latest], "active")
    client = FakeClient()
    subject = full_subject()
    license_payload = build_license_payload(LicensePlan(older.license_key, older.ogrn, older.geo_zone, [older], "active"), subject)
    license_doc = client.create("RKN010_Licenses", license_payload)
    old_payload = build_record_payload(
        older,
        subject=subject,
        license_id=license_doc["_id"],
        license_status="active",
        record_status="active",
    )
    old_doc = client.create("RKN010_Records", old_payload)
    client.operations.clear()
    make_migrator(tmp_path, client).migrate([plan])
    create_index = next(i for i, op in enumerate(client.operations) if op[0] == "create" and op[1] == "RKN010_Records")
    reissue_index = next(i for i, op in enumerate(client.operations) if op[:3] == ("update", "RKN010_Records", old_doc["_id"]))
    assert create_index < reissue_index
    assert len([item for item in client.collections["RKN010_Records"] if item["status"] == "active"]) == 1


def test_second_run_is_idempotent(tmp_path, source_row):
    row = source_row()
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "active")
    client = FakeClient()
    make_migrator(tmp_path, client, "first").migrate([plan])
    client.operations.clear()
    summary = make_migrator(tmp_path, client, "second").migrate([plan])
    assert summary.licenses_created == 0
    assert summary.records_created == 0
    assert not [op for op in client.operations if op[0] == "create"]


def test_incomplete_subject_is_created_with_warning(tmp_path, source_row):
    row = source_row()
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "active")
    client = FakeClient()
    client.collections["organizations"] = [
        {
            "ogrn": row.ogrn,
            "name": row.org_name,
            "shortName": row.short_org_name,
        }
    ]
    run_dir = tmp_path / "incomplete"

    summary = make_migrator(tmp_path, client, "incomplete").migrate([plan])

    assert summary.groups_completed == 1
    assert summary.licenses_created == 1
    assert summary.records_created == 1
    assert '"event": "subject_incomplete"' in (run_dir / "events.jsonl").read_text(encoding="utf-8")
    subject = client.collections["RKN010_Licenses"][0]["subject"]
    assert subject["data"]["organization"]["ogrn"] == row.ogrn
    assert "inn" not in subject["data"]["organization"]

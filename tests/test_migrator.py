from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from rkn010_migration.mapping import build_license_payload, build_record_payload
from rkn010_migration.migrator import Migrator
from rkn010_migration.models import LicensePlan, ValidationIssue
from rkn010_migration.runlog import JsonlWriter, setup_logging
from rkn010_migration.state import RunState, rollback

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


def test_existing_documents_receive_application_data_and_keep_nsi_metadata(tmp_path, source_row):
    row = source_row()
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "active")
    client = FakeClient()
    subject = full_subject()
    license_payload = build_license_payload(plan, subject)
    license_payload["applicationData"]["licenceNumber1"].update(
        {
            "code": 156,
            "lic_date_start": "2021-01-26",
            "service_name": "Услуги местной телефонной связи",
        }
    )
    license_doc = client.create("RKN010_Licenses", license_payload)
    record_payload = build_record_payload(
        row,
        subject=subject,
        license_id=license_doc["_id"],
        license_status="active",
        record_status="active",
        license_date_issued=license_doc["dateIssued"],
        license_date_valid_to=license_doc["dateValidTo"],
    )
    record_payload["xsdData"] = {"forRegistry": record_payload["xsdData"]["forRegistry"]}
    record_doc = client.create("RKN010_Records", record_payload)
    client.operations.clear()

    summary = make_migrator(tmp_path, client, "sync-application-data").migrate([plan])

    assert summary.groups_completed == 1
    saved_license = client.collections["RKN010_Licenses"][0]
    assert saved_license["applicationData"]["licenceNumber1"]["code"] == 156
    assert saved_license["applicationData"]["licenceNumber1"]["lic_date_start"] == "2021-01-26"
    saved_record = next(item for item in client.collections["RKN010_Records"] if item["_id"] == record_doc["_id"])
    assert saved_record["xsdData"]["applicationData"]["licenceNumber1"]["lic_num"] == "3004"
    assert saved_record["licenseDateValidTo"] == "2029-06-01T00:00:00.000+0000"


def test_rollback_restores_documents_after_schema_sync(tmp_path, source_row):
    older = source_row(regno="00000052")
    latest = source_row(excel_row=5, regno="00000092", include_order_number="101")
    plan = LicensePlan(older.license_key, older.ogrn, older.geo_zone, [older, latest], "active")
    client = FakeClient()
    subject = full_subject()
    original_license = client.create(
        "RKN010_Licenses",
        build_license_payload(
            LicensePlan(older.license_key, older.ogrn, older.geo_zone, [older], "active"),
            subject,
        ),
    )
    original_record = client.create(
        "RKN010_Records",
        build_record_payload(
            older,
            subject=subject,
            license_id=original_license["_id"],
            license_status="active",
            record_status="active",
            license_date_issued=original_license["dateIssued"],
            license_date_valid_to=original_license["dateValidTo"],
        ),
    )
    before_license = deepcopy(original_license)
    before_record = deepcopy(original_record)
    run_dir = tmp_path / "rollback-flow"

    make_migrator(tmp_path, client, "rollback-flow").migrate([plan])
    assert len(client.collections["RKN010_Records"]) == 2
    assert client.collections["RKN010_Records"][0]["status"] == "reissued"

    result = rollback(client, run_dir / "checkpoint.json", dry_run=False)

    assert result["restored"] == 2
    assert result["deleted"] == 1
    assert client.collections["RKN010_Licenses"] == [before_license]
    assert client.collections["RKN010_Records"] == [before_record]


def test_incomplete_subject_from_organizations_is_skipped_without_writes(tmp_path, source_row):
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

    assert summary.groups_completed == 0
    assert summary.groups_skipped == 1
    assert summary.licenses_created == 0
    assert summary.records_created == 0
    assert '"event": "subject_incomplete"' in (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert '"event": "group_skipped"' in (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert client.collections["RKN010_Licenses"] == []
    assert client.collections["RKN010_Records"] == []


def test_missing_organization_uses_complete_excel_subject(tmp_path, source_row):
    row = source_row()
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "active")
    client = FakeClient()
    client.collections["organizations"] = []
    run_dir = tmp_path / "excel-fallback"

    summary = make_migrator(tmp_path, client, "excel-fallback").migrate([plan])

    assert summary.groups_completed == 1
    assert summary.groups_skipped == 0
    subject = client.collections["RKN010_Licenses"][0]["subject"]
    assert subject["data"]["organization"]["inn"] == row.inn
    assert subject["data"]["organization"]["organizationalForm"]["code"] == "12247"
    assert subject["xsdData"]["email"] == row.email
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert '"event": "organization_not_found"' in events
    assert '"source": "excel"' in events


def test_missing_organization_and_incomplete_excel_subject_is_skipped(tmp_path, source_row):
    row = source_row(phone="", email="")
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "active")
    client = FakeClient()
    client.collections["organizations"] = []
    run_dir = tmp_path / "excel-incomplete"

    summary = make_migrator(tmp_path, client, "excel-incomplete").migrate([plan])
    result = rollback(client, run_dir / "checkpoint.json", dry_run=False)

    assert summary.groups_skipped == 1
    assert client.collections["RKN010_Licenses"] == []
    assert client.collections["RKN010_Records"] == []
    assert result["updates_to_restore"] == 0
    assert result["records_to_delete"] == 0
    assert result["skipped_groups"] == 1


def test_duplicate_organizations_selects_most_complete_subject(tmp_path, source_row):
    row = source_row()
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "active")
    client = FakeClient()
    client.collections["organizations"] = [
        {
            "_id": "incomplete",
            "ogrn": row.ogrn,
            "name": row.org_name,
            "shortName": row.short_org_name,
        },
        {
            "_id": "complete",
            "ogrn": row.ogrn,
            "name": row.org_name,
            "subject": full_subject(),
        },
    ]
    run_dir = tmp_path / "duplicates"

    summary = make_migrator(tmp_path, client, "duplicates").migrate([plan])

    assert summary.groups_completed == 1
    subject = client.collections["RKN010_Licenses"][0]["subject"]
    assert subject["data"]["organization"]["inn"] == "1655000000"
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert '"event": "organization_duplicate_selected"' in events
    assert '"selected_id": "complete"' in events


def test_known_historical_rename_does_not_block_subject_lookup(tmp_path, source_row):
    row = source_row(org_name="ОАО ТЕСТОВЫЙ ОПЕРАТОР")
    plan = LicensePlan(
        row.license_key,
        row.ogrn,
        row.geo_zone,
        [row],
        "active",
        issues=[ValidationIssue("name_changed", "Историческое переименование", severity="warning")],
    )
    client = FakeClient()

    summary = make_migrator(tmp_path, client, "historical-rename").migrate([plan])

    assert summary.groups_completed == 1
    events = (tmp_path / "historical-rename" / "events.jsonl").read_text(encoding="utf-8")
    assert '"event": "organization_name_mismatch"' in events

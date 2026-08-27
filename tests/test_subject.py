from __future__ import annotations

from rkn010_migration.subject import build_subject, validate_subject

from conftest import full_subject


def test_reuses_full_subject_and_removes_target_record_metadata(source_row):
    hit = full_subject()
    hit["_id"] = "organization-record-id"
    hit["dateCreation"] = "old"
    subject = build_subject(hit, source_row())
    assert "_id" not in subject
    assert "dateCreation" not in subject
    assert subject["data"]["organization"]["ogrn"] == "1021600000001"
    assert validate_subject(subject) == []


def test_builds_subject_wrapper_from_organization_card(source_row):
    subject = build_subject(
        {"organization": {"ogrn": "1021600000001", "name": "ПАО ТЕСТОВЫЙ ОПЕРАТОР"}},
        source_row(),
    )
    assert subject["specialTypeId"] == "ulApplicant"
    assert validate_subject(subject) == []


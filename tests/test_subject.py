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
        {
            "organization": {
                "ogrn": "1021600000001",
                "inn": "1655000000",
                "name": "ПАО ТЕСТОВЫЙ ОПЕРАТОР",
                "shortName": "ПАО ТЕСТ",
                "organizationalForm": {"code": "12247", "name": "Публичные акционерные общества"},
                "registrationAddress": {"postalCode": "420000", "unrecognizablePart": "г. Казань"},
                "phone": "+7 843 000-00-00",
                "email": "operator@example.test",
                "factAddress": {"postalCode": "420000", "unrecognizablePart": "г. Казань"},
            }
        },
        source_row(),
    )
    assert subject["specialTypeId"] == "ulApplicant"
    assert validate_subject(subject) == []


def test_reports_new_required_legal_entity_fields(source_row):
    subject = build_subject(
        {"organization": {"ogrn": "1021600000001", "name": "ПАО ТЕСТОВЫЙ ОПЕРАТОР"}},
        source_row(),
    )
    missing = validate_subject(subject)
    assert "data.organization.inn" in missing
    assert "data.organization.organizationalForm" in missing
    assert "data.organization.registrationAddress" in missing
    assert "xsdData.phone" in missing
    assert "xsdData.email" in missing
    assert "xsdData.factAddress" in missing


def test_builds_and_validates_ip_subject(source_row):
    row = source_row(
        ogrn="304165500000001",
        org_name="ИП ИВАНОВ ИВАН ИВАНОВИЧ",
        short_org_name="ИП ИВАНОВ И.И.",
    )
    subject = build_subject(
        {
            "person": {
                "ogrn": "304165500000001",
                "inn": "165500000001",
                "lastName": "ИВАНОВ",
                "firstName": "ИВАН",
                "middleName": "ИВАНОВИЧ",
            },
            "nameIP": "ИП ИВАНОВ ИВАН ИВАНОВИЧ",
            "birthPlace": "г. Казань",
        },
        row,
    )
    assert subject["specialTypeId"] == "ipApplicant"
    assert validate_subject(subject) == []

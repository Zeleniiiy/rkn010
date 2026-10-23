from __future__ import annotations

import json

from rkn010_migration.state import RunState, rollback


class RollbackClient:
    def __init__(self):
        self.actions = []

    def update(self, collection, document):
        self.actions.append(("update", collection, document["_id"]))

    def delete(self, document):
        self.actions.append(("delete", document["parentEntries"], document["_id"]))


def test_rollback_restores_updates_then_deletes_in_reverse(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps(
            {
                "updated": [{"collection": "RKN010_Records", "before": {"_id": "old", "guid": "g"}}],
                "created": [
                    {"_id": "license", "guid": "g1", "parentEntries": "RKN010_Licenses"},
                    {"_id": "record", "guid": "g2", "parentEntries": "RKN010_Records"},
                ],
            }
        ),
        encoding="utf-8",
    )
    client = RollbackClient()
    result = rollback(client, path, dry_run=False)
    assert client.actions == [
        ("update", "RKN010_Records", "old"),
        ("delete", "RKN010_Records", "record"),
        ("delete", "RKN010_Licenses", "license"),
    ]
    assert result["restored"] == 1
    assert result["deleted"] == 2
    assert result["rollback_status"] == "completed"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["rollback"]["status"] == "completed"
    assert json.loads((tmp_path / "rollback-report.json").read_text(encoding="utf-8"))["deleted_total"] == 2


def test_completed_rollback_is_safe_to_run_again(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps(
            {
                "updated": [],
                "created": [
                    {"_id": "license", "guid": "g1", "parentEntries": "RKN010_Licenses"},
                    {"_id": "record", "guid": "g2", "parentEntries": "RKN010_Records"},
                ],
            }
        ),
        encoding="utf-8",
    )
    client = RollbackClient()

    first = rollback(client, path, dry_run=False)
    second = rollback(client, path, dry_run=False)

    assert first["deleted"] == 2
    assert second["deleted"] == 0
    assert second["deleted_total"] == 2
    assert second["already_rolled_back"] is True
    assert len(client.actions) == 2


def test_rollback_resumes_after_partial_failure(tmp_path):
    class FailingOnceClient(RollbackClient):
        def __init__(self):
            super().__init__()
            self.failed = False

        def delete(self, document):
            if document["_id"] == "license" and not self.failed:
                self.failed = True
                raise RuntimeError("temporary failure")
            super().delete(document)

    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps(
            {
                "updated": [],
                "created": [
                    {"_id": "license", "guid": "g1", "parentEntries": "RKN010_Licenses"},
                    {"_id": "record", "guid": "g2", "parentEntries": "RKN010_Records"},
                ],
            }
        ),
        encoding="utf-8",
    )
    client = FailingOnceClient()

    try:
        rollback(client, path, dry_run=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError("rollback must expose the first failure")

    resumed = rollback(client, path, dry_run=False)

    assert resumed["deleted"] == 1
    assert resumed["deleted_total"] == 2
    assert client.actions == [
        ("delete", "RKN010_Records", "record"),
        ("delete", "RKN010_Licenses", "license"),
    ]


def test_successful_group_clears_old_reason_and_error(tmp_path):
    path = tmp_path / "checkpoint.json"
    state = RunState(
        path,
        profile="psi",
        workbook_hash="hash",
    )
    state.mark_group("ogrn:471", "skipped", reason="missing email", error="old")

    state.mark_group("ogrn:471", "completed", license_id="license")

    group = json.loads(path.read_text(encoding="utf-8"))["groups"]["ogrn:471"]
    assert group["status"] == "completed"
    assert "reason" not in group
    assert "error" not in group


def test_completed_check_cleans_legacy_reason(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps(
            {
                "profile": "psi",
                "workbook_hash": "hash",
                "groups": {
                    "ogrn:471": {
                        "status": "completed",
                        "reason": "legacy skip reason",
                        "error": "legacy error",
                    }
                },
                "created": [],
                "updated": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    state = RunState(path, profile="psi", workbook_hash="hash")

    assert state.completed("ogrn:471") is True

    group = json.loads(path.read_text(encoding="utf-8"))["groups"]["ogrn:471"]
    assert "reason" not in group
    assert "error" not in group

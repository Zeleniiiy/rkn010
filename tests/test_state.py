from __future__ import annotations

import json

from rkn010_migration.state import rollback


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


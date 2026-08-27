from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunState:
    def __init__(self, path: Path, *, profile: str, workbook_hash: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            if self.data.get("profile") != profile or self.data.get("workbook_hash") != workbook_hash:
                raise ValueError("Checkpoint belongs to another profile or workbook version")
        else:
            self.data: dict[str, Any] = {
                "version": 1,
                "profile": profile,
                "workbook_hash": workbook_hash,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "groups": {},
                "created": [],
                "updated": [],
                "errors": [],
            }

    def save(self) -> None:
        self.data["updated_at"] = utc_now()
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temp.replace(self.path)

    def group(self, key: str) -> dict[str, Any]:
        return self.data["groups"].setdefault(key, {})

    def completed(self, key: str) -> bool:
        return self.group(key).get("status") == "completed"

    def mark_group(self, key: str, status: str, **values: Any) -> None:
        group = self.group(key)
        group.update(values)
        group["status"] = status
        group["updated_at"] = utc_now()
        self.save()

    def record_created(self, document: dict[str, Any]) -> None:
        self.data["created"].append(
            {
                "_id": document.get("_id"),
                "guid": document.get("guid"),
                "parentEntries": document.get("parentEntries"),
                "recorded_at": utc_now(),
            }
        )
        self.save()

    def record_updated(self, collection: str, before: dict[str, Any]) -> None:
        self.data["updated"].append(
            {
                "collection": collection,
                "before": deepcopy(before),
                "recorded_at": utc_now(),
            }
        )
        self.save()

    def record_error(self, key: str, error: Exception) -> None:
        self.data["errors"].append({"key": key, "error": str(error), "recorded_at": utc_now()})
        self.save()


def rollback(client, state_path: Path, *, dry_run: bool = True) -> dict[str, int]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    restored = 0
    deleted = 0
    if not dry_run:
        for entry in reversed(state.get("updated", [])):
            client.update(entry["collection"], entry["before"])
            restored += 1
        for entry in reversed(state.get("created", [])):
            if entry.get("_id") and entry.get("guid") and entry.get("parentEntries"):
                client.delete(entry)
                deleted += 1
    return {
        "updates_to_restore": len(state.get("updated", [])),
        "records_to_delete": len(state.get("created", [])),
        "restored": restored,
        "deleted": deleted,
    }


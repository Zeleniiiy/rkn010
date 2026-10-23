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
        group = self.group(key)
        is_completed = group.get("status") == "completed"
        if is_completed and ("reason" in group or "error" in group):
            group.pop("reason", None)
            group.pop("error", None)
            self.save()
        return is_completed

    def mark_group(self, key: str, status: str, **values: Any) -> None:
        group = self.group(key)
        if status in {"running", "completed"}:
            group.pop("reason", None)
            group.pop("error", None)
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


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    temp = state_path.with_suffix(state_path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(state_path)


def _write_rollback_report(state_path: Path, result: dict[str, Any]) -> None:
    report_path = state_path.with_name("rollback-report.json")
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def rollback(client, state_path: Path, *, dry_run: bool = True) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    skipped_groups = sum(
        1 for group in state.get("groups", {}).values() if group.get("status") == "skipped"
    )
    rollback_state = state.setdefault("rollback", {})
    restored_keys = set(rollback_state.get("restored_entries", []))
    deleted_keys = set(rollback_state.get("deleted_entries", []))
    already_rolled_back = rollback_state.get("status") == "completed"
    restored = 0
    deleted = 0
    if not dry_run and not already_rolled_back:
        rollback_state["status"] = "running"
        rollback_state.setdefault("started_at", utc_now())
        rollback_state["updated_at"] = utc_now()
        rollback_state.setdefault("restored_entries", [])
        rollback_state.setdefault("deleted_entries", [])
        _write_state(state_path, state)
        for entry in reversed(state.get("updated", [])):
            before = entry.get("before", {})
            entry_key = f"{entry.get('collection')}:{before.get('_id')}"
            if entry_key in restored_keys:
                continue
            client.update(entry["collection"], entry["before"])
            restored += 1
            restored_keys.add(entry_key)
            rollback_state["restored_entries"].append(entry_key)
            rollback_state["updated_at"] = utc_now()
            _write_state(state_path, state)
        for entry in reversed(state.get("created", [])):
            entry_key = f"{entry.get('parentEntries')}:{entry.get('_id')}"
            if entry_key in deleted_keys:
                continue
            if entry.get("_id") and entry.get("guid") and entry.get("parentEntries"):
                client.delete(entry)
                deleted += 1
                deleted_keys.add(entry_key)
                rollback_state["deleted_entries"].append(entry_key)
                rollback_state["updated_at"] = utc_now()
                _write_state(state_path, state)
        rollback_state["status"] = "completed"
        rollback_state["completed_at"] = utc_now()
        rollback_state["updated_at"] = utc_now()
        _write_state(state_path, state)
    result = {
        "updates_to_restore": len(state.get("updated", [])),
        "records_to_delete": len(state.get("created", [])),
        "restored": restored,
        "deleted": deleted,
        "restored_total": len(restored_keys),
        "deleted_total": len(deleted_keys),
        "skipped_groups": skipped_groups,
        "already_rolled_back": already_rolled_back,
        "rollback_status": rollback_state.get("status", "not_started"),
    }
    if not dry_run:
        _write_rollback_report(state_path, result)
    return result

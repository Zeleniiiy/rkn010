from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .api import PgsClient
from .excel_input import WorkbookValidationError, raise_for_errors, read_workbook
from .migrator import Migrator
from .planner import build_plan
from .profiles import resolve_profile
from .runlog import JsonlWriter, setup_logging
from .state import RunState, rollback


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_profile_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default="psi", help="dev, psi, prod or custom name")
    parser.add_argument("--base-url")
    parser.add_argument("--ui-base-url")
    parser.add_argument("--jwt-url")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--cookie-file", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--no-verify-tls", action="store_true")
    parser.add_argument("--confirm-prod", action="store_true")


def make_client(args, profile) -> PgsClient:
    auth_dir = Path("auth") / profile.name
    return PgsClient(
        profile.base_url,
        token_file=args.token_file or auth_dir / "token.md",
        cookie_file=args.cookie_file or auth_dir / "cookie.md",
        timeout=args.timeout,
        verify_tls=not args.no_verify_tls,
    )


def require_prod_confirmation(profile, args) -> None:
    if profile.production and getattr(args, "execute", False) and not args.confirm_prod:
        raise SystemExit("Production write requires --confirm-prod")


def command_validate(args) -> int:
    data = read_workbook(args.workbook, args.sheet)
    plans = build_plan(data)
    issues = data.issues + [issue for plan in plans for issue in plan.issues]
    print(json.dumps({"rows": len(data.rows), "groups": len(plans), "issues": [i.to_dict() for i in issues]}, ensure_ascii=False, indent=2, default=str))
    return 2 if any(issue.severity == "error" for issue in issues) else 0


def command_run(args) -> int:
    profile = resolve_profile(
        args.profile,
        base_url=args.base_url,
        ui_base_url=args.ui_base_url,
        jwt_url=args.jwt_url,
    )
    require_prod_confirmation(profile, args)
    workbook = args.workbook.expanduser().resolve()
    digest = file_hash(workbook)
    run_dir = args.workdir.expanduser().resolve() / profile.name / f"{workbook.stem}-{digest[:12]}"
    logger = setup_logging(run_dir, args.verbose)
    data = read_workbook(workbook, args.sheet)
    raise_for_errors(data)
    plans = build_plan(data)
    if args.limit:
        plans = plans[: args.limit]
    plan_path = run_dir / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps([plan.to_dict() for plan in plans], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    state_path = run_dir / "checkpoint.json"
    if state_path.exists() and args.no_resume:
        raise SystemExit(f"Checkpoint already exists: {state_path}; use another --workdir or allow resume")
    state = RunState(state_path, profile=profile.name, workbook_hash=digest)
    events = JsonlWriter(run_dir / "events.jsonl")

    if not args.execute:
        migrator = Migrator(None, state=state, events=events, logger=logger, execute=False)
        summary = migrator.write_dry_run(plans, run_dir / "payloads.jsonl")
        print(json.dumps({"mode": "dry-run", "run_dir": str(run_dir), **summary.to_dict()}, ensure_ascii=False, indent=2))
        return 0

    client = make_client(args, profile)
    client.auth_test()
    migrator = Migrator(
        client,
        state=state,
        events=events,
        logger=logger,
        execute=True,
        strict_org_name=not args.allow_org_name_mismatch,
        operator_mode=args.operator_mode,
    )
    summary = migrator.migrate(plans)
    (run_dir / "summary.json").write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": "execute", "run_dir": str(run_dir), **summary.to_dict()}, ensure_ascii=False, indent=2))
    return 2 if summary.groups_failed else 0


def command_auth(args) -> int:
    profile = resolve_profile(args.profile, base_url=args.base_url, ui_base_url=args.ui_base_url, jwt_url=args.jwt_url)
    make_client(args, profile).auth_test()
    print(f"Authentication OK: {profile.name}")
    return 0


def command_rollback(args) -> int:
    profile = resolve_profile(args.profile, base_url=args.base_url, ui_base_url=args.ui_base_url, jwt_url=args.jwt_url)
    require_prod_confirmation(profile, args)
    client = make_client(args, profile) if args.execute else None
    result = rollback(client, args.state.expanduser().resolve(), dry_run=not args.execute)
    print(json.dumps({"mode": "execute" if args.execute else "dry-run", **result}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RKN010 migration utility")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate workbook without API")
    validate.add_argument("--workbook", required=True, type=Path)
    validate.add_argument("--sheet")
    validate.set_defaults(func=command_validate)

    run = sub.add_parser("run", help="create plan or execute migration")
    run.add_argument("--workbook", required=True, type=Path)
    run.add_argument("--sheet")
    run.add_argument("--workdir", type=Path, default=Path("runs"))
    run.add_argument("--execute", action="store_true", help="perform API writes; omitted means dry-run")
    run.add_argument("--no-resume", action="store_true")
    run.add_argument("--operator-mode", action="store_true")
    run.add_argument("--allow-org-name-mismatch", action="store_true")
    run.add_argument("--limit", type=int)
    run.add_argument("--verbose", action="store_true")
    add_profile_args(run)
    run.set_defaults(func=command_run)

    auth = sub.add_parser("auth", help="test authorization only")
    add_profile_args(auth)
    auth.set_defaults(func=command_auth)

    roll = sub.add_parser("rollback", help="inspect or execute rollback from checkpoint")
    roll.add_argument("--state", required=True, type=Path)
    roll.add_argument("--execute", action="store_true")
    add_profile_args(roll)
    roll.set_defaults(func=command_rollback)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except WorkbookValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())


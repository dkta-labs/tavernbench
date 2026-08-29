"""TavernBench Behavior Lab command entry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import Client, TavernBenchError, verify_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tavernbench", description="TavernBench Behavior Lab owner-key client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    concierge = subparsers.add_parser("concierge", help="run and seal a credential-safe integration handshake episode")
    concierge.add_argument("--participant-code")
    concierge.add_argument("--episode-kind", choices=("initial", "rerun"), default="initial")
    concierge.add_argument("--config-label", required=True)
    concierge.add_argument("--agent-name", default="concierge-agent")
    concierge.add_argument("--export", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "concierge":
        return concierge_main(args)
    return 2


def concierge_main(args: argparse.Namespace) -> int:
    try:
        with Client.from_env() as lab:
            run = lab.start_run(
                participant_code=args.participant_code,
                episode_kind=args.episode_kind,
                agent_metadata={
                    "agent_name": args.agent_name,
                    "client_name": "python-sdk",
                    "client_version": "0.2.0",
                    "config_label": args.config_label,
                    "tools": ["tavernbench-http-v1"],
                },
            )
            receipt = lab.act(run.id, action="observe")
            lab.abort(run.id)
            evidence = lab.export(run.id, args.export)
    except TavernBenchError as error:
        print(json.dumps({"status": "error", "type": type(error).__name__, "message": str(error)}), file=sys.stderr)
        return 1

    summary = {
        "status": "ok",
        "run_id": run.id,
        "run_status": evidence["run"]["status"],
        "action_receipt": receipt["receipt_id"],
        "trace_entries": len(evidence["trace"]),
        "trace_integrity": evidence["integrity"]["status"],
        "trace_verified_by_client": verify_evidence(evidence),
        "scenario_revision": evidence["run"]["scenario"]["revision"],
        "scenario_build": evidence["run"]["scenario"]["build"],
        "export": str(args.export),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

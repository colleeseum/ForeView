from __future__ import annotations

import argparse
from pathlib import Path

from infrastructure.runtime_config import RuntimeConfig
from services.runtime_backup_service import RuntimeBackupService

PROFILE_DATA_DIRS = {
    "dev": Path(__file__).parent / ".runtime" / "dev",
    "prod": Path.home() / ".local" / "share" / "retirement-finance" / "prod",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up or restore one finance runtime")
    runtime_group = parser.add_mutually_exclusive_group(required=True)
    runtime_group.add_argument("--profile", choices=sorted(PROFILE_DATA_DIRS))
    runtime_group.add_argument("--data-dir", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a verified backup directory")
    backup.add_argument("destination", type=Path)
    restore = commands.add_parser("restore", help="Restore a verified backup directory")
    restore.add_argument("source", type=Path)
    restore.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()

    data_dir = arguments.data_dir or PROFILE_DATA_DIRS[arguments.profile]
    runtime = RuntimeConfig.load(data_dir)
    service = RuntimeBackupService()
    if arguments.command == "backup":
        created = service.create(runtime, arguments.destination)
        print(f"Backup created: {created}")
    else:
        safety_backup = service.restore(arguments.source, runtime, replace=arguments.replace)
        print(f"Runtime restored: {runtime.data_dir}")
        if safety_backup:
            print(f"Previous runtime backed up: {safety_backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

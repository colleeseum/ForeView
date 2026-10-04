# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-git-identity.sh"
APPROVED_EMAIL = "serge.colle@mindstep.ca"
INVALID_EMAIL = "invalid@example.test"


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repository(repository: Path) -> None:
    run_git(repository, "init", "--initial-branch=main")
    run_git(repository, "config", "user.name", "Serge Colle")
    run_git(repository, "config", "user.email", APPROVED_EMAIL)
    run_git(repository, "config", "user.useConfigOnly", "true")
    (repository / "record.txt").write_text("approved\n", encoding="utf-8")
    run_git(repository, "add", "record.txt")
    run_git(repository, "commit", "-m", "Approved commit")


def create_invalid_commit(repository: Path) -> str:
    (repository / "record.txt").write_text("invalid\n", encoding="utf-8")
    run_git(repository, "add", "record.txt")
    environment = os.environ | {
        "GIT_AUTHOR_NAME": "Serge Colle",
        "GIT_AUTHOR_EMAIL": INVALID_EMAIL,
        "GIT_COMMITTER_NAME": "Serge Colle",
        "GIT_COMMITTER_EMAIL": INVALID_EMAIL,
    }
    subprocess.run(
        ["git", "commit", "-m", "Invalid identity commit"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return run_git(repository, "rev-parse", "HEAD").stdout.strip()


def run_identity_check(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT)],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


def test_stale_remote_tracking_history_does_not_block_replacement(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    run_git(tmp_path, "switch", "-c", "invalid-history")
    invalid_commit = create_invalid_commit(tmp_path)
    run_git(tmp_path, "update-ref", "refs/remotes/origin/stale", invalid_commit)
    run_git(tmp_path, "switch", "main")
    run_git(tmp_path, "branch", "-D", "invalid-history")

    result = run_identity_check(tmp_path)

    assert result.returncode == 0, result.stderr


def test_invalid_local_branch_still_fails_identity_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    run_git(tmp_path, "switch", "-c", "invalid-history")
    create_invalid_commit(tmp_path)
    run_git(tmp_path, "switch", "main")

    result = run_identity_check(tmp_path)

    assert result.returncode == 1
    assert "Commits use an unapproved email for Serge Colle" in result.stderr
    assert INVALID_EMAIL in result.stderr

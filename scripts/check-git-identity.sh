#!/bin/sh
# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

set -eu

approved_name="Serge Colle"
approved_email="serge.colle@mindstep.ca"
history_only=false

if [ "${1:-}" = "--history-only" ]; then
    history_only=true
elif [ "$#" -ne 0 ]; then
    printf 'Usage: %s [--history-only]\n' "$0" >&2
    exit 2
fi

if [ "$history_only" = false ]; then
    configured_name=$(git config --local --get user.name || true)
    configured_email=$(git config --local --get user.email || true)
    use_config_only=$(git config --local --get user.useConfigOnly || true)

    if [ "$configured_name" != "$approved_name" ] || \
        [ "$configured_email" != "$approved_email" ] || \
        [ "$use_config_only" != "true" ]; then
        printf '%s\n' "Repository Git identity is not configured as required." >&2
        printf '%s\n' "Run ./scripts/configure-git-identity.sh and retry." >&2
        exit 1
    fi
fi

invalid_commits=$(mktemp)
trap 'rm -f "$invalid_commits"' EXIT HUP INT TERM
tab=$(printf '\t')

git log --all --format='%H%x09%an%x09%ae%x09%cn%x09%ce' |
    while IFS="$tab" read -r commit author_name author_email committer_name committer_email; do
        if [ "$author_name" = "$approved_name" ] && [ "$author_email" != "$approved_email" ]; then
            printf '%s author <%s>\n' "$commit" "$author_email" >>"$invalid_commits"
        fi
        if [ "$committer_name" = "$approved_name" ] && \
            [ "$committer_email" != "$approved_email" ]; then
            printf '%s committer <%s>\n' "$commit" "$committer_email" >>"$invalid_commits"
        fi
    done

if [ -s "$invalid_commits" ]; then
    printf '%s\n' "Commits use an unapproved email for Serge Colle:" >&2
    cat "$invalid_commits" >&2
    exit 1
fi

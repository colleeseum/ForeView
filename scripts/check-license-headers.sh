#!/bin/sh
# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

set -eu

copyright_notice="SPDX-FileCopyrightText: 2026 Mindstep Corporation"
license_notice="SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0"

license_missing_file=$(mktemp)
trap 'rm -f "$license_missing_file"' EXIT HUP INT TERM

git ls-files | while IFS= read -r file; do
    case "$file" in
        infrastructure/migrations/*|public_rules/*) continue ;;
        *.py|*.mjs|*.js|*.css|*.html|*.sh|*.yaml|*.yml|Makefile|pyproject.toml) : ;;
        *) continue ;;
    esac

    header=$(sed -n '1,10p' "$file")
    if ! printf '%s\n' "$header" | grep -Fq "$copyright_notice" || \
        ! printf '%s\n' "$header" | grep -Fq "$license_notice"; then
        printf '%s\n' "$file" >>"$license_missing_file"
    fi
done

if [ -s "$license_missing_file" ]; then
    printf '%s\n' "Missing or incomplete license header:" >&2
    cat "$license_missing_file" >&2
    exit 1
fi

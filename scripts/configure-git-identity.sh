#!/bin/sh
# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

set -eu

git config --local user.name "Serge Colle"
git config --local user.email "serge.colle@mindstep.ca"
git config --local user.useConfigOnly true

printf '%s\n' "Repository Git identity configured for Serge Colle <serge.colle@mindstep.ca>."

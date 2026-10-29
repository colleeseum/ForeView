# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Validation for the server-rendered shared icon-action contract."""

ICON_ACTIONS = (
    "edit",
    "delete",
    "view",
    "download",
    "add",
    "expand",
    "collapse",
    "close",
    "help",
    "reset",
)


def validated_icon_label(label: object, action: object) -> str:
    if action not in ICON_ACTIONS or not isinstance(label, str) or not label.strip():
        raise ValueError("An icon action requires a known action and a nonempty label")
    # Do not propagate a Markup subclass's HTML-safe status into an attribute.
    return str(label)

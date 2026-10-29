# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Server-rendered icon actions preserve hooks without interpreting user labels."""

from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import Flask, render_template_string
from markupsafe import Markup

from web.icon_actions import validated_icon_label

ACTIONS = [
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
]


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("action", ACTIONS)
def test_server_actions_escape_identity_and_preserve_safe_workflow_hooks(action):
    application = Flask(
        __name__, template_folder=str(Path(__file__).resolve().parents[1] / "templates")
    )
    application.jinja_env.filters["validated_icon_label"] = validated_icon_label
    with application.app_context():
        html = render_template_string(
            "{% from '_icon_actions.html' import icon_action %}{{ icon_action(action, label, attributes=hooks, busy=true) }}",
            action=action,
            label='Synthetic <script>identity</script> & "label"',
            hooks={
                "id": "record-7",
                "data-record-id": '7" onclick="bad',
                "onclick": "bad()",
                "data-bad onclick": "bad()",
                "aria-expanded": False,
                "data-icon-action": "wrong",
            },
        )
    tags = Tags(html).tags
    assert [tag for tag, _ in tags] == ["button", "span"]
    button, icon = tags[0][1], tags[1][1]
    assert button["type"] == "button"
    assert button["aria-label"] == 'Synthetic <script>identity</script> & "label"'
    assert button["data-icon-action"] == action
    assert button["data-record-id"] == '7" onclick="bad'
    assert button["id"] == "record-7"
    assert button["aria-expanded"] == "false"
    assert button["aria-busy"] == "true"
    assert "disabled" in button
    assert "onclick" not in button
    assert ("fv-button--danger" in button["class"]) == (action == "delete")
    assert icon["aria-hidden"] == "true"


@pytest.mark.parametrize(
    "action,label",
    [
        ("unknown", "Edit synthetic"),
        (None, "Edit synthetic"),
        ("edit", ""),
        ("edit", "   "),
        ("edit", None),
        ("edit", 7),
    ],
)
def test_invalid_server_icon_specs_are_rejected(action, label):
    application = Flask(
        __name__, template_folder=str(Path(__file__).resolve().parents[1] / "templates")
    )
    application.jinja_env.filters["validated_icon_label"] = validated_icon_label
    with application.app_context(), pytest.raises(ValueError, match="nonempty label"):
        render_template_string(
            "{% from '_icon_actions.html' import icon_action %}{{ icon_action(action, label) }}",
            action=action,
            label=label,
        )


def test_undefined_label_is_rejected_and_markup_cannot_bypass_attribute_escaping():
    application = Flask(
        __name__, template_folder=str(Path(__file__).resolve().parents[1] / "templates")
    )
    application.jinja_env.filters["validated_icon_label"] = validated_icon_label
    with application.app_context():
        with pytest.raises(ValueError):
            render_template_string(
                "{% from '_icon_actions.html' import icon_action %}{{ icon_action('edit', missing) }}"
            )
        html = render_template_string(
            "{% from '_icon_actions.html' import icon_action %}{{ icon_action('edit', label) }}",
            label=Markup('Synthetic" onclick="bad'),
        )
    attrs = Tags(html).tags[0][1]
    assert attrs["aria-label"] == 'Synthetic" onclick="bad'
    assert "onclick" not in attrs

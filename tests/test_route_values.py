# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import pytest

from domain.validation_error import ValidationError
from web.route_values import payload_integer, payload_ratio, required_field


def test_request_conversions_preserve_existing_numeric_semantics():
    assert payload_integer(3.8) == 3
    assert payload_integer("42") == 42
    assert payload_integer(True) == 1
    assert payload_ratio("0.25") == 0.25
    assert required_field({"name": "Original evidence"}, "name") == "Original evidence"


@pytest.mark.parametrize(
    ("convert", "value", "code"),
    [
        (payload_integer, "invalid", "input_invalid_integer"),
        (payload_integer, None, "input_invalid_integer"),
        (payload_ratio, "invalid", "input_invalid_number"),
        (payload_ratio, None, "input_invalid_number"),
    ],
)
def test_request_conversions_attach_stable_codes(convert, value, code):
    with pytest.raises(ValidationError) as caught:
        convert(value)
    assert caught.value.code == code
    assert caught.value.values == {"value": str(value)}


def test_required_field_has_explicit_identity_not_diagnostic_text_matching():
    with pytest.raises(ValidationError) as caught:
        required_field({}, "name")
    assert caught.value.code == "input_required_field"
    assert caught.value.values == {"field": "name"}

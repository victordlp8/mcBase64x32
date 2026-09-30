"""Public API error tests."""

import pytest
import bookette


@pytest.mark.parametrize("text", ["", "x", "!" * 8, "ˈ" * 7, "ˈ" * 9])
def test_malformed_text_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        bookette.decode(text)


def test_invalid_public_input_types_are_rejected() -> None:
    with pytest.raises((TypeError, ValueError)):
        bookette.encode("text")  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        bookette.decode(b"bytes")  # type: ignore[arg-type]

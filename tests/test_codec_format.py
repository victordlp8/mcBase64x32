"""Public API tests."""

from pathlib import Path

import pytest
import bookette


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"", "ˈˈˈˈˈˈˈˈ"),
        (
            bytes(range(0x80, 0x100)),
            "ˈˈˈˈˈˈ࡛̍⦙ᩣᛁ⸽ࢭॱꜞ༙ं┊ܿ⸵፧꩝·اᱹᨘꥏ⃓݀!ꥇ़╹᱾꠰ı̩ʽاः⸴⎹ı݀￤ׅ꤫̣׀ִ༐̍︱․᳜꤯܃࣭ꜟי▎ꭵֺ᳜᳜ࠟ۬︙ꜟ܄഻╷࠭݁⎥ꥉꜟ̓⎸︕ៈ྇͘︓᰷;⃓ः֫︳іຸ݄ᨗ݁܁ᩮ࣭ࠠꥇᥣ❘៲⦙⋮︳̩іꥈ꠰▕ਂￜꞋᨗ꞉់ֺ︕়ٜ┊୲ᩩ᠄᳝̍꘡⋮ꥈ㇑ˈ꯬ᨗ࣪¡ꨲꥒ･ꜟ㆐┋Ꭵ⸵",
        ),
    ],
)
def test_golden_vectors(payload: bytes, expected: str) -> None:
    assert bookette.encode(payload) == expected
    assert bookette.decode(expected) == payload


def test_694_byte_page_boundary_golden() -> None:
    expected = Path(__file__).with_name("comparador_694.txt").read_text(
        encoding="utf-8"
    )
    payload = bytes(i % 256 for i in range(694))
    assert bookette.encode(payload) == expected
    assert bookette.decode(expected) == payload


@pytest.mark.parametrize(
    "text",
    ["x", "!" * 8, "ˈ" * 7, "ˈ" * 9, "ʼʼˈˈˈˈˈˈ"],
)
def test_malformed_text_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        bookette.decode(text)


def test_nonzero_payload_padding_raises_value_error() -> None:
    encoded = bookette.encode(b"\x00")
    candidate = encoded[:-1] + "̍"
    with pytest.raises(ValueError):
        bookette.decode(candidate)

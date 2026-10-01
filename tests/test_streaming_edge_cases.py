"""Edge-contract tests for the native streaming iterators.

`encode_pages` / `decode_pages` delegate framing to Rust (`PageEncoder` / `PageDecoder`) while
staying real Python generators. These cover the exhaustion and rejection paths that a single
successful round trip does not exercise.
"""

from __future__ import annotations

import types

import pytest

import bookette

CHARS_PER_PAGE = 1024
BYTES_PAGE_1 = 1020

# A scalar that is definitely absent from the K4-W6 vocabulary.
UNKNOWN_GLYPH = "\x01"


def _pages_for(size: int) -> list[str]:
    return list(bookette.encode_pages(bytes(i % 256 for i in range(size))))


class TestGeneratorContract:
    def test_encode_pages_returns_real_generator(self) -> None:
        gen = bookette.encode_pages(b"abc")
        assert isinstance(gen, types.GeneratorType)

    def test_decode_pages_returns_real_generator(self) -> None:
        gen = bookette.decode_pages(iter([]))
        assert isinstance(gen, types.GeneratorType)

    def test_encode_pages_is_lazy(self) -> None:
        """Pulling one page must not encode the whole payload."""
        payload = bytes(500_000)
        gen = bookette.encode_pages(payload)
        first = next(gen)
        assert len(first) == CHARS_PER_PAGE
        gen.close()

    def test_decode_pages_is_lazy(self) -> None:
        payload = bytes(500_000)
        gen = bookette.decode_pages(bookette.encode_pages(payload))
        chunk = next(gen)
        assert len(chunk) == BYTES_PAGE_1
        gen.close()


class TestExhaustionPaths:
    def test_empty_iterable_yields_nothing(self) -> None:
        """No first page at all is a clean end, not an error."""
        assert list(bookette.decode_pages(iter([]))) == []

    def test_short_first_page_rejected(self) -> None:
        pages = ["ab"]
        with pytest.raises(ValueError, match=r"Page 1 has invalid length: 2"):
            list(bookette.decode_pages(pages))

    def test_short_subsequent_page_rejected(self) -> None:
        pages = _pages_for(3000)
        pages[1] = pages[1][:100]
        with pytest.raises(ValueError, match=r"Page has invalid length: 100"):
            list(bookette.decode_pages(pages))

    def test_truncated_stream_rejected(self) -> None:
        """Header declares 3000 B, page 1 carries 1020, and no page 2 follows."""
        pages = _pages_for(3000)[:1]
        with pytest.raises(ValueError, match=r"Truncated input: expected 1980 more bytes"):
            list(bookette.decode_pages(pages))

    def test_truncated_below_page_one_capacity(self) -> None:
        """Last page cut short still counts as an error, not a short read."""
        pages = _pages_for(1500)[:1]
        with pytest.raises(ValueError, match=r"Truncated input"):
            list(bookette.decode_pages(pages))


class TestCorruptGlyphs:
    def test_unknown_glyph_in_header_rejected(self) -> None:
        pages = _pages_for(100)
        pages[0] = UNKNOWN_GLYPH + pages[0][1:]
        with pytest.raises(ValueError, match="Corrupt header"):
            list(bookette.decode_pages(pages))

    def test_unknown_glyph_in_data_quartet_rejected(self) -> None:
        pages = _pages_for(100)
        # Quartet 1 on page 1 is the first data quartet (quartet 0 is the header).
        pages[0] = pages[0][:4] + UNKNOWN_GLYPH + pages[0][5:]
        with pytest.raises(ValueError, match="Corrupt data quartet"):
            list(bookette.decode_pages(pages))

    def test_unknown_glyph_in_later_page_rejected(self) -> None:
        pages = _pages_for(3000)
        pages[1] = UNKNOWN_GLYPH + pages[1][1:]
        with pytest.raises(ValueError, match="Corrupt data quartet"):
            list(bookette.decode_pages(pages))


class TestParallelEncodeIsIndependentOracle:
    """`encode_rust` takes Rayon for payloads >= 64 KiB; the page iterator does not.

    Comparing them byte-for-byte pins Rayon's page ordering and padding against a serial
    implementation, which a round-trip test alone would not catch.
    """

    @pytest.mark.parametrize(
        "size",
        [0, 1, 1020, 1021, 2045, 102_396, 65_536, 65_537, 200_000],
    )
    def test_encode_matches_page_iterator(self, size: int) -> None:
        payload = bytes(i % 256 for i in range(size))
        assert bookette.encode(payload) == "".join(bookette.encode_pages(payload))

    @pytest.mark.parametrize("size", [0, 1020, 1021, 65_536, 200_000])
    def test_pages_decode_back_to_payload(self, size: int) -> None:
        payload = bytes(i % 256 for i in range(size))
        joined = b"".join(bookette.decode_pages(bookette.encode_pages(payload)))
        assert joined == payload
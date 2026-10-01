"""Public API and K4-B6 format tests."""

import pytest
import bookette


def test_empty_payload_golden() -> None:
    # Length 0 encodes to Quartet 0 = 'ˈˈˈˈ' + 255 null quartets = 'ˈ' * 1024
    expected = "ˈ" * 1024
    encoded = bookette.encode(b"")
    assert encoded == expected
    assert bookette.decode(encoded) == b""


def test_page_boundary_golden() -> None:
    # Page 1 exact boundary: 1020 bytes
    payload_1020 = bytes(i % 256 for i in range(1020))
    enc_1020 = bookette.encode(payload_1020)
    assert len(enc_1020) == 1024
    assert bookette.decode(enc_1020) == payload_1020

    # Spills 1 byte into Page 2: 1021 bytes -> 2 pages = 2048 characters
    payload_1021 = bytes(i % 256 for i in range(1021))
    enc_1021 = bookette.encode(payload_1021)
    assert len(enc_1021) == 2048
    assert bookette.decode(enc_1021) == payload_1021

    # Page 2 exact boundary: 1020 + 1024 = 2044 bytes -> 2048 characters
    payload_2044 = bytes(i % 256 for i in range(2044))
    enc_2044 = bookette.encode(payload_2044)
    assert len(enc_2044) == 2048
    assert bookette.decode(enc_2044) == payload_2044

    # Spills 1 byte into Page 3: 2045 bytes -> 3 pages = 3072 characters
    payload_2045 = bytes(i % 256 for i in range(2045))
    enc_2045 = bookette.encode(payload_2045)
    assert len(enc_2045) == 3072
    assert bookette.decode(enc_2045) == payload_2045


@pytest.mark.parametrize(
    "text",
    ["x", "!", "!" * 3, "ˈ" * 5, "ˈ" * 7, "not_valid_chars"],
)
def test_malformed_text_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        bookette.decode(text)


def test_max_bytes_per_page_constant() -> None:
    assert bookette.MAX_BYTES_PER_PAGE == 1024


def test_encode_decode_pages_streaming() -> None:
    payload = bytes(i % 256 for i in range(3500))  # Spans 4 pages
    pages_gen = bookette.encode_pages(payload)
    import types
    assert isinstance(pages_gen, types.GeneratorType), "encode_pages must be <class 'generator'>"
    assert iter(pages_gen) is pages_gen

    pages_list = []
    for page in pages_gen:
        assert len(page) == 1024, "Each yielded page must have exactly 1024 characters"
        pages_list.append(page)

    assert len(pages_list) == 4

    byte_chunks_gen = bookette.decode_pages(iter(pages_list))
    assert isinstance(byte_chunks_gen, types.GeneratorType), "decode_pages must be <class 'generator'>"
    assert iter(byte_chunks_gen) is byte_chunks_gen
    recovered = b"".join(byte_chunks_gen)
    assert recovered == payload


def test_encode_pages_early_termination_does_not_encode_full_stream() -> None:
    import time
    huge_payload = b"A" * (20 * 1024 * 1024)  # 20 MiB
    pages_gen = bookette.encode_pages(huge_payload)
    
    t0 = time.perf_counter()
    p1 = next(pages_gen)
    t1 = time.perf_counter()
    
    assert len(p1) == 1024
    # Demands < 50ms (fetching 1 page of 20 MiB must not encode the entire 20 MiB)
    assert (t1 - t0) < 0.05

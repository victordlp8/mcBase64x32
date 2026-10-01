"""Public Python wrappers, streaming generators and CLI for the Bookette K4-W6 codec."""

import argparse
import sys
from typing import Iterable, Iterator

from .bookette import encode_rust, decode_rust, encode_u32, decode_u32, MAX_BYTES_PER_PAGE

CHARS_PER_PAGE = 1024
BYTES_PAGE_1 = 1020
BYTES_SUBSEQUENT = 1024

# Null quartet for padding (Bucket 0 value 0: four 'ˈ' characters)
NULL_QUARTET = "ˈˈˈˈ"


def encode(payload: bytes) -> str:
    """Encode bytes as Bookette K4-W6 text (concatenated pages of 1,024 characters)."""
    return encode_rust(payload)


def decode(text_in_bookette: str) -> bytes:
    """Decode Bookette K4-W6 text into original bytes."""
    return decode_rust(text_in_bookette)


def encode_pages(payload: bytes) -> Iterator[str]:
    """Genuine streaming generator: encodes and yields 1,024-character pages on demand.
    
    Processes the input chunk by chunk without pre-encoding the entire payload.
    """
    total_len = len(payload)
    
    # --- Page 1 ---
    # Quartet 0 is the global payload length header L
    header_quartet = encode_u32(total_len)
    p1_data = payload[:BYTES_PAGE_1]
    
    p1_quartets = [header_quartet]
    for i in range(0, len(p1_data), 4):
        chunk = p1_data[i:i + 4]
        if len(chunk) < 4:
            chunk = chunk + b"\x00" * (4 - len(chunk))
        val = int.from_bytes(chunk, "little")
        p1_quartets.append(encode_u32(val))
        
    # Pad Page 1 to 256 quartets (1,024 characters)
    while len(p1_quartets) < 256:
        p1_quartets.append(NULL_QUARTET)
        
    yield "".join(p1_quartets)
    
    # --- Pages 2..N ---
    offset = BYTES_PAGE_1
    while offset < total_len:
        page_data = payload[offset:offset + BYTES_SUBSEQUENT]
        page_quartets = []
        for i in range(0, len(page_data), 4):
            chunk = page_data[i:i + 4]
            if len(chunk) < 4:
                chunk = chunk + b"\x00" * (4 - len(chunk))
            val = int.from_bytes(chunk, "little")
            page_quartets.append(encode_u32(val))
            
        # Pad last page to 256 quartets (1,024 characters)
        while len(page_quartets) < 256:
            page_quartets.append(NULL_QUARTET)
            
        yield "".join(page_quartets)
        offset += BYTES_SUBSEQUENT


def decode_pages(pages: Iterable[str]) -> Iterator[bytes]:
    """Genuine streaming generator: consumes pages one by one from an iterable and yields decoded byte chunks."""
    pages_iter = iter(pages)
    try:
        first_page = next(pages_iter)
    except StopIteration:
        return

    if len(first_page) != CHARS_PER_PAGE:
        raise ValueError(f"Page 1 has invalid length: {len(first_page)} (must be 1024 characters)")

    # Quartet 0 on Page 1 is the global length header L
    q0_chars = [first_page[0], first_page[1], first_page[2], first_page[3]]
    total_len = decode_u32(q0_chars)
    if total_len == 0:
        return

    remaining = total_len

    # --- Page 1 data (up to 255 quartets = 1020 bytes) ---
    p1_bytes_needed = min(remaining, BYTES_PAGE_1)
    p1_q_needed = (p1_bytes_needed + 3) // 4

    p1_buf = bytearray()
    for q_idx in range(1, 1 + p1_q_needed):
        q_chars = [
            first_page[q_idx * 4],
            first_page[q_idx * 4 + 1],
            first_page[q_idx * 4 + 2],
            first_page[q_idx * 4 + 3],
        ]
        val = decode_u32(q_chars)
        p1_buf.extend(val.to_bytes(4, "little"))

    p1_chunk = bytes(p1_buf[:p1_bytes_needed])
    remaining -= len(p1_chunk)
    yield p1_chunk

    # --- Subsequent Pages 2..N (up to 256 quartets = 1024 bytes per page) ---
    while remaining > 0:
        try:
            page = next(pages_iter)
        except StopIteration:
            raise ValueError(f"Truncated input: expected {remaining} more bytes but no more pages provided")

        if len(page) != CHARS_PER_PAGE:
            raise ValueError(f"Page has invalid length: {len(page)} (must be 1024 characters)")

        page_bytes_needed = min(remaining, BYTES_SUBSEQUENT)
        page_q_needed = (page_bytes_needed + 3) // 4

        p_buf = bytearray()
        for q_idx in range(page_q_needed):
            q_chars = [
                page[q_idx * 4],
                page[q_idx * 4 + 1],
                page[q_idx * 4 + 2],
                page[q_idx * 4 + 3],
            ]
            val = decode_u32(q_chars)
            p_buf.extend(val.to_bytes(4, "little"))

        p_chunk = bytes(p_buf[:page_bytes_needed])
        remaining -= len(p_chunk)
        yield p_chunk


def main():
    parser = argparse.ArgumentParser(
        description="Bookette: High-performance binary-to-Minecraft book encoder (K4-W6 codec, 1,024 B/page)"
    )
    parser.add_argument("-e", "--encode", metavar="FILE", help="Encode binary file into Bookette text")
    parser.add_argument("-d", "--decode", metavar="FILE", help="Decode Bookette text file into binary")
    parser.add_argument("-o", "--output", metavar="OUT", help="Output file (default: stdout)")
    args = parser.parse_args()

    if args.encode:
        with open(args.encode, "rb") as f:
            data = f.read()
        output = encode(data)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Encoded {len(data)} bytes to {args.output}")
        else:
            print(output)

    elif args.decode:
        with open(args.decode, "r", encoding="utf-8") as f:
            text = f.read().strip()
        recovered = decode(text)

        if args.output:
            with open(args.output, "wb") as f:
                f.write(recovered)
            print(f"Decoded {len(recovered)} bytes to {args.output}")
        else:
            sys.stdout.buffer.write(recovered)

    else:
        message = "Hello World using Bookette K4-W6!"
        encoded = encode(message.encode())
        decoded = decode(encoded).decode()
        print(f"Demo: {message} -> {len(encoded)} chars -> {decoded}")
        print(f"MAX_BYTES_PER_PAGE: {MAX_BYTES_PER_PAGE}")


if __name__ == "__main__":
    main()

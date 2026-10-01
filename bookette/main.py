"""Public Python wrappers, streaming generators and CLI for the Bookette K4-W6 codec."""

import argparse
import sys
from typing import Iterable, Iterator

from .bookette import (
    PageDecoder,
    PageEncoder,
    decode_rust,
    decode_u32,
    encode_rust,
    encode_u32,
    MAX_BYTES_PER_PAGE,
)

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

    Page framing is built in Rust (see :class:`PageEncoder`); the global length header sits in
    Quartet 0 of page 1, later pages carry 1,024 payload bytes each, and every page is padded to
    256 quartets. Wrapping the native iterator in a generator keeps the public API lazy and
    preserves ``types.GeneratorType``.
    """
    yield from PageEncoder(payload)


def decode_pages(pages: Iterable[str]) -> Iterator[bytes]:
    """Genuine streaming generator: consumes pages one by one from an iterable and yields decoded byte chunks.

    Consuming and decoding happen in Rust (see :class:`PageDecoder`); pages are pulled from any
    iterable on demand, so memory stays bounded by a single page regardless of payload size.
    """
    yield from PageDecoder(pages)


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

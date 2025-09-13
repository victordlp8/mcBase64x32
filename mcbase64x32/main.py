"""mcbase64x32 implementation using Rust for high performance."""

from .mcbase64x32 import encode_rust, decode_rust

MAX_BYTES_PER_PAGE = 694

def encode(payload: bytes) -> str:
    """Encodes into mcBase64x32 using Rust implementation."""
    return encode_rust(payload)

def decode(text_in_mcbase64x32: str) -> bytes:
    """Decodes from mcBase64x32 using Rust implementation."""
    return decode_rust(text_in_mcbase64x32)

def main():
    """Demo function showing basic usage."""
    message = "aaaaaaaaaa"
    encoded = encode(message.encode())
    decoded = decode(encoded).decode()

    print(f"{message} -> {encoded}    -> {decoded}")
    print(f"Compression: {len(message)} chars -> {len(encoded)} chars")
    print("Using Rust: True")


if __name__ == "__main__":
    main()
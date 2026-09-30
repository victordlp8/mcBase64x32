"""Public Python wrappers for the Bookette codec."""

from .bookette import encode_rust, decode_rust


def encode(payload: bytes) -> str:
    """Encode bytes as Bookette text."""
    return encode_rust(payload)


def decode(text_in_bookette: str) -> bytes:
    """Decode Bookette text."""
    return decode_rust(text_in_bookette)


def main():
    """Demo function showing basic usage."""
    message = "Hello World using Bookette!"
    encoded = encode(message.encode())
    decoded = decode(encoded).decode()

    print(f"{message} -> {encoded} -> {decoded}")
    print(f"Encoded scalars: {len(encoded)}")
    print("Using Rust: True")


if __name__ == "__main__":
    main()
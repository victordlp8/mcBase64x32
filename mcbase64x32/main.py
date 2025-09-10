"""mcbase64x32 implementation using Rust for high performance."""

from .mcbase64x32 import encode, decode

MAX_BYTES_PER_PAGE = 694

def main():
    """Demo function showing basic usage."""
    message = "Hello from mcbase64x32!"
    encoded = encode(message.encode())
    decoded = decode(encoded).decode()

    print(f"{message} -> {encoded}    -> {decoded}")
    print(f"Compression: {len(message)} chars -> {len(encoded)} chars")
    print("Using Rust: True")


if __name__ == "__main__":
    main()
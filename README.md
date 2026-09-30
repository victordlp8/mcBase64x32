<p align="center">
    <a href="https://pypi.org/project/bookette/" alt="PyPi Website">
        <img src="https://img.shields.io/pypi/v/bookette?label=pypi%20bookette" /></a>
    <a href="https://pypi.org/project/bookette/" alt="Downloads per month">
        <img src="https://img.shields.io/pypi/dm/bookette" /></a>
    <a href="https://pypi.org/project/bookette/" alt="Total downloads">
        <img src="https://img.shields.io/pepy/dt/bookette" /></a>
</p>

# Bookette
Bookette v3.0.0, previously mcBase64x32.

A Rust package that encodes binary data as Unicode text for Minecraft books.

<p align="center">
    <img width="438" height="540" alt="Minecraft book page filled with Bookette characters" src="https://github.com/user-attachments/assets/2fcb931c-4512-4465-9734-2a9a5b19f388" />
    <br>
    <sub><em>Minecraft book page filled with Bookette characters</em></sub>
</p>

## Overview

Bookette encodes bytes as Unicode text for Minecraft books, using ordered one-width and two-width glyph vocabularies.

The encoding uses one 8-scalar header containing the byte length of the whole payload. Payload data follows in 63-bit big-endian blocks. For multi-page text, concatenate pages in order and decode the result once. The maximum bytes per page has not been measured.

## Features

- Encoding and decoding use a Rust extension.
- Multi-page payloads decode after page text is concatenated in order.
- The Python package has no runtime dependencies.

## Installation

### Using [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended)

```bash
uv add bookette
```

### Using pip

```bash
pip install bookette
```

### From source

```bash
git clone https://github.com/victordlp8/bookette.git
cd bookette
uv sync
uv tool install -e .
```

## Quick start

```python
import bookette


# Encode data
data = b"Hello, Minecraft World!"
encoded = bookette.encode(data)
print(f"Encoded: {encoded}")

# Decode data
decoded = bookette.decode(encoded)
print(f"Decoded: {decoded.decode()}")

# Encoded text is Unicode; len() counts its scalar values.
print(f"Encoded scalars: {len(encoded)}")
```

## API reference

### Functions

#### `encode(payload: bytes) -> str`

Encodes bytes as Unicode text, preceded by one whole-payload length header.

#### `decode(text_in_bookette: str) -> bytes`

Decodes concatenated text into the original bytes. Malformed text raises `ValueError`.

### Format

The format uses one 8-scalar length header for the whole payload, followed by 63-bit big-endian blocks. Concatenate page fragments in order before calling `decode`. The verified per-page maximum has not yet been measured.

## How it works

Each full 63-bit block maps to eight Unicode scalars. The final partial block is left-aligned and zero-padded; the decoder rejects nonzero padding.

## Performance

Encoding and decoding run in the Rust extension.

## Testing

Run the test suite:

```bash
# Using uv
uv run pytest

# Using pytest directly
pytest

# With coverage
uv run pytest --cov=bookette
```

## Requirements

- Python >= 3.13
- No Python runtime dependencies
- A Rust toolchain is required to build from source

## Development

### Set up the development environment

```bash
git clone https://github.com/victordlp8/bookette.git
cd bookette
uv sync
```

### Run tests

```bash
uv run pytest
```

### Build the package

```bash
uv build
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Authors

- **ThorTuwy** - *Initial work and inventor of the custom base*
- **victordlp8** - *Main developer and maintainer*

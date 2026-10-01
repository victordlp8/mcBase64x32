<p align="center">
    <a href="https://pypi.org/project/bookette/" alt="PyPi Website">
        <img src="https://img.shields.io/pypi/v/bookette?label=pypi%20bookette" /></a>
    <a href="https://pypi.org/project/bookette/" alt="Downloads per month">
        <img src="https://img.shields.io/pypi/dm/bookette" /></a>
    <a href="https://pypi.org/project/bookette/" alt="Total downloads">
        <img src="https://img.shields.io/pepy/dt/bookette" /></a>
</p>

# Bookette
Bookette v4.0.0, previously mcBase64x32.

A high-performance Rust package that encodes binary data as Unicode text for Minecraft books with certified **1,024 Bytes per page**.

<p align="center">
    <img width="438" height="540" alt="Minecraft book page filled with Bookette characters" src="https://github.com/user-attachments/assets/2fcb931c-4512-4465-9734-2a9a5b19f388" />
    <br>
    <sub><em>Minecraft book page filled with Bookette characters</em></sub>
</p>

## Overview

Bookette v4.0.0 implements the **K4-W6 codec**, which encodes binary data into Minecraft book pages using fixed 4-character quartets ($K=4$) with maximum glyph advance $\le 6\text{ px}$ across 15 structural mixed-radix buckets.

Each quartet maps bijectively to a 32-bit unsigned integer (`u32`), encoding exactly 4 raw bytes into 4 Unicode characters. Page 1 stores a 4-byte little-endian length header plus 255 data quartets (**1,020 Bytes** of useful payload). Pages 2 to $N$ store 256 data quartets (**1,024 Bytes** each). Total characters per page is always exactly 1,024, fitting strictly within Minecraft's 1,024 character and 14-line boundaries.

## Features

- **Certified Capacity:** 1,024 Bytes per page (1,020 Bytes on Page 1, 1,024 Bytes on subsequent pages).
- **High Performance:** Implemented in pure Rust with zero allocations in the hot path.
- **Streaming Generators:** Memory-efficient page-by-page generator pipeline (`encode_pages`, `decode_pages`).
- **Zero Dependencies:** The Python package has no runtime dependencies.

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
uv run maturin develop --release
```

## Quick start

```python
import bookette

# Encode data (returns concatenated 1,024-character pages)
data = b"Hello, Minecraft World!"
encoded = bookette.encode(data)
print(f"Encoded text length: {len(encoded)} characters")

# Decode data
decoded = bookette.decode(encoded)
assert decoded == data

# Streaming page-by-page generator for large data
for page in bookette.encode_pages(data):
    print(f"Page (1,024 chars): {page[:40]}...")
```

## API reference

### Constants

- `MAX_BYTES_PER_PAGE = 1024`: Full data capacity per Minecraft book page (Pages 2..$N$; Page 1 carries 1,020 useful bytes due to the 4-byte `u32` length header).

### Functions

#### `encode(payload: bytes) -> str`
Encodes bytes as a concatenated string of 1,024-character Minecraft book pages.

#### `decode(text: str) -> bytes`
Decodes Bookette K4-W6 text into original bytes. Malformed text or corrupted quartets raise `ValueError`.

#### `encode_pages(payload: bytes) -> Iterator[str]`
Streaming generator that encodes and yields 1,024-character Minecraft book pages on demand.

#### `decode_pages(pages: Iterable[str]) -> Iterator[bytes]`
Streaming generator that consumes 1,024-character pages one by one from an iterable and yields decoded byte chunks.

### Format Specification

Bookette K4-W6 encodes 4-byte integers (`u32`) into 4-character Unicode quartets using 15 structural buckets over three verified alphabets: $A_1$ (106 chars, 1 px), $A_2$ (211 chars, 2 px), and $A_3$ (38 chars, 3 px). Maximum advance per quartet is $6\text{ px}$, ensuring no page ever overflows Minecraft's 14-line limit ($19 \times 6\text{ px} = 114\text{ px}$ per line).

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

<p align="center">
    <a href="https://pypi.org/project/mcbase64x32/" alt="PyPi Website">
        <img src="https://img.shields.io/pypi/v/mcbase64x32?label=pypi%20mcbase64x32" /></a>
    <a href="https://pypi.org/project/mcbase64x32/" alt="Downloads per month">
        <img src="https://img.shields.io/pypi/dm/mcbase64x32" /></a>
    <a href="https://pypi.org/project/mcbase64x32/" alt="Total downloads">
        <img src="https://img.shields.io/pepy/dt/mcbase64x32" /></a>
</p>

# mcBase64x32

A high-performance Base64x32 implementation specialized for maximizing data storage in Minecraft books using numpy vectorized operations.

## Overview

mcBase64x32 is a custom encoding scheme designed specifically for storing data efficiently in Minecraft books. It uses a 64x32-2-character alphabet using Unicode characters of pixel width of 1 and 2 and by combining these characters we achieve optimal compression while keeping the Minecraft book limits of characters and pixels.

We basically use a bunch of 1 and 2 pixel width Unicode characters to build 2048 unique pairs of them that then we use to encode and decode data.

## Features

- **High Performance**: Uses numpy vectorized operations for ultra-fast encoding/decoding
- **Minecraft Optimized**: Designed specifically for maximum data storage in Minecraft books

## Installation

### Using [uv](https://docs.astral.sh/uv/getting-started/installation/) (Recommended)

```bash
uv add mcbase64x32
```

### Using pip

```bash
pip install mcbase64x32
```

### From Source

```bash
git clone https://github.com/victordlp8/mcBase64x32.git
cd mcBase64x32
uv sync
uv run pip install -e .
```

## Quick Start

```python
import mcbase64x32

# Encode data
data = b"Hello, Minecraft World!"
encoded = mcbase64x32.encode(data)
print(f"Encoded: {encoded}")

# Decode data
decoded = mcbase64x32.decode(encoded)
print(f"Decoded: {decoded.decode()}")

# Check compression ratio
original_size = len(data)
encoded_size = len(encoded)
compression_ratio = original_size / encoded_size
print(f"Compression ratio: {compression_ratio:.2f}x")
```

## API Reference

### Functions

#### `encode(payload: bytes) -> str`

Encodes binary data into mcBase64x32 format.

**Parameters:**
- `payload` (bytes): The binary data to encode

**Returns:**
- `str`: The encoded string in mcBase64x32 format

#### `decode(text_in_mcbase64x32: str) -> bytes`

Decodes mcBase64x32 string back to binary data.

**Parameters:**
- `text_in_mcbase64x32` (str): The encoded string to decode

**Returns:**
- `bytes`: The decoded binary data

**Raises:**
- `ValueError`: If the encoded string contains invalid characters

### Constants

#### `MAX_BYTES_PER_PAGE`

The maximum number of bytes that can be stored per Minecraft book page (694 bytes).

## How It Works

mcBase64x32 uses a custom encoding scheme that:

1. **Converts data to 11-bit chunks**: Each chunk represents a value from 0-2047
2. **Maps to Unicode characters**: Uses a custom built 64x32-2-character alphabet made of pairs of Unicode characters
3. **Optimizes for Minecraft**: Designed specifically for maximum data storage in Minecraft books
4. **Includes dynamic length header**: up to 32-bit length prefix ensures proper decoding
5. **Uses vectorized operations**: numpy arrays for maximum performance

## Performance

The implementation is optimized for speed using:

- **Numpy vectorization**: All operations use numpy arrays for maximum performance
- **Pre-computed lookup tables**: Character mappings are pre-calculated
- **Bit manipulation**: Efficient binary operations for encoding/decoding
- **Memory optimization**: Minimal memory allocations during processing

## Testing

Run the test suite:

```bash
# Using uv
uv run pytest

# Using pytest directly
pytest

# With coverage
uv run pytest --cov=mcbase64x32
```

## Requirements

- Python >= 3.13
- numpy >= 2.3.2

## Development

### Setup Development Environment

```bash
git clone https://github.com/victordlp8/mcBase64x32.git
cd mcBase64x32
uv sync
```

### Running Tests

```bash
uv run pytest
```

### Building Package

```bash
uv build
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Authors

- **ThorTuwy** - *Initial work and inventor of the custom base*
- **victordlp8** - *Main developer and maintainer*

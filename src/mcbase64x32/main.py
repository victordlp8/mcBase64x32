"""mcbase64x32 implementation using numpy vectorized operations for high performance."""

import json
import numpy as np
from pathlib import Path

# Get the directory where this module is located
module_dir = Path(__file__).parent
json_path = module_dir / "utils" / "baseList.json"

with open(json_path, "r", encoding="utf-8") as f:
    base_dict = json.load(f)

# Pre-compute lookup arrays for ultra-fast access
ENCODE_ARRAY = np.array([base_dict["encode"][str(i)] for i in range(2048)], dtype=object)
DECODE_TABLE = base_dict["decode"]

# Pre-compute power arrays to avoid recalculation (HYPER optimization)
POWERS_11 = 2 ** np.arange(10, -1, -1, dtype=np.int32)
POWERS_8 = 2 ** np.arange(7, -1, -1, dtype=np.int32)

MAX_BYTES_PER_PAGE = 694


def encode(payload: bytes) -> str:
    """Encodes into mcBase64x32 using numpy vectorized operations."""
    if not isinstance(payload, bytes):
        raise TypeError(f"encode() expects bytes, got {type(payload).__name__}")
    
    if not payload:
        return ""
    
    original_length = len(payload)
    
    # Convert to numpy array for vectorized operations
    data_array = np.frombuffer(payload, dtype=np.uint8)
    
    # Create length header (32 bits)
    length_bits = np.array([int(b) for b in f"{original_length:032b}"], dtype=np.uint8)
    
    # Convert bytes to bits vectorized
    data_bits = np.unpackbits(data_array)
    
    # Combine length + data
    all_bits = np.concatenate([length_bits, data_bits])
    
    # Add padding for 11-bit alignment
    padding_needed = (11 - (len(all_bits) % 11)) % 11
    if padding_needed:
        padding = np.zeros(padding_needed, dtype=np.uint8)
        all_bits = np.concatenate([all_bits, padding])
    
    # Reshape into 11-bit chunks
    num_chunks = len(all_bits) // 11
    bit_chunks = all_bits[:num_chunks * 11].reshape(-1, 11)
    
    # Convert binary chunks to decimal values using pre-computed powers
    decimal_values = np.dot(bit_chunks, POWERS_11).astype(np.int32)
    
    # Use vectorized lookup
    encoded_chars = ENCODE_ARRAY[decimal_values]
    
    return ''.join(encoded_chars)


def decode(text_in_mcbase64x32: str) -> bytes:
    """Decodes from mcBase64x32 using numpy vectorized operations."""
    if not isinstance(text_in_mcbase64x32, str):
        raise TypeError(f"decode() expects str, got {type(text_in_mcbase64x32).__name__}")
    
    if not text_in_mcbase64x32:
        return b""
    
    # Extract character pairs
    char_pairs = [text_in_mcbase64x32[i:i+2] for i in range(0, len(text_in_mcbase64x32), 2)]
    
    # Decode pairs to decimal values
    try:
        decimal_values = np.array([DECODE_TABLE[pair] for pair in char_pairs], dtype=np.int32)
    except KeyError as e:
        raise ValueError(f"Invalid character pair in encoded string: {e}")
    
    # Convert decimal values to 11-bit binary arrays
    binary_matrix = np.zeros((len(decimal_values), 11), dtype=np.uint8)
    
    for i in range(11):
        binary_matrix[:, i] = (decimal_values >> (10 - i)) & 1
    
    # Flatten to single bit array
    all_bits = binary_matrix.flatten()
    
    # Extract length (first 32 bits)
    if len(all_bits) < 32:
        return b""
    
    length_bits = all_bits[:32]
    data_bits = all_bits[32:]
    
    # Convert length bits to integer
    original_length = int(''.join(map(str, length_bits)), 2)
    
    # Convert data bits to bytes
    # Pad to byte boundary
    remainder = len(data_bits) % 8
    if remainder:
        padding = np.zeros(8 - remainder, dtype=np.uint8)
        data_bits = np.concatenate([data_bits, padding])
    
    # Reshape to bytes and convert using pre-computed powers
    byte_chunks = data_bits.reshape(-1, 8)
    byte_values = np.dot(byte_chunks, POWERS_8).astype(np.uint8)
    
    # Return only original length
    return bytes(byte_values[:original_length])


def main():
    """Demo function showing basic usage."""
    message = "Hello from mcbase64x32!"
    encoded = encode(message.encode())
    decoded = decode(encoded).decode()

    print(f"{message} -> {encoded} -> {decoded}")
    print(f"Compression: {len(message)} chars -> {len(encoded)} chars")


if __name__ == "__main__":
    main()
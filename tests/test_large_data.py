"""Large data stress tests for mcbase64x32 library.

This module tests the library's ability to handle large binary payloads
including memory usage and performance characteristics.
"""

import os
import pytest
import random
import time
from typing import Generator
import mcbase64x32


class TestLargeData:
    """Test handling of large binary data."""

    @pytest.mark.slow
    @pytest.mark.parametrize("size_mb", [1, 5, 10, 50])
    def test_large_binary_data(self, size_mb: int):
        """Test encoding/decoding of large binary data (1MB, 5MB, 10MB)."""
        size_bytes = size_mb * 1024 * 1024
        print(f"\nTesting {size_mb}MB ({size_bytes:,} bytes)...")
        
        # Generate large random binary data efficiently
        start_time = time.time()
        payload = os.urandom(size_bytes)
        gen_time = time.time() - start_time
        print(f"Data generation took: {gen_time:.2f}s")
        
        # Test encoding
        start_time = time.time()
        encoded = mcbase64x32.encode(payload)
        encode_time = time.time() - start_time
        print(f"Encoding took: {encode_time:.2f}s")
        print(f"Encoded size: {len(encoded):,} characters")
        print(f"Compression ratio: {len(encoded) / len(payload):.2f}x")
        
        # Test decoding
        start_time = time.time()
        decoded = mcbase64x32.decode(encoded)
        decode_time = time.time() - start_time
        print(f"Decoding took: {decode_time:.2f}s")
        
        # Verify integrity
        assert payload == decoded, f"Round-trip failed for {size_mb}MB data"
        print(f"✅ {size_mb}MB test passed!")

    @pytest.mark.slow
    def test_extremely_large_data_50mb(self):
        """Test 50MB data - only run if explicitly requested."""
        size_bytes = 50 * 1024 * 1024  # 50MB
        print(f"\nTesting 50MB ({size_bytes:,} bytes)...")
        
        # Generate data efficiently
        start_time = time.time()
        payload = os.urandom(size_bytes)
        gen_time = time.time() - start_time
        print(f"Data generation took: {gen_time:.2f}s")
        
        # Test encoding
        start_time = time.time()
        encoded = mcbase64x32.encode(payload)
        encode_time = time.time() - start_time
        print(f"Encoding took: {encode_time:.2f}s")
        print(f"Encoded size: {len(encoded):,} characters")
        
        # Test decoding
        start_time = time.time()
        decoded = mcbase64x32.decode(encoded)
        decode_time = time.time() - start_time
        print(f"Decoding took: {decode_time:.2f}s")
        
        # Verify integrity
        assert payload == decoded, "Round-trip failed for 50MB data"
        print("✅ 50MB test passed!")

    @pytest.mark.slow
    def test_memory_efficiency_pattern(self):
        """Test memory efficiency with repetitive patterns."""
        # Create a 5MB file with repetitive pattern
        pattern = b"mcbase64x32_test_pattern_" * 100  # ~2.5KB pattern
        size_target = 5 * 1024 * 1024  # 5MB
        repeats = size_target // len(pattern)
        payload = pattern * repeats
        
        print(f"\nTesting repetitive pattern: {len(payload):,} bytes")
        
        start_time = time.time()
        encoded = mcbase64x32.encode(payload)
        encode_time = time.time() - start_time
        
        start_time = time.time()
        decoded = mcbase64x32.decode(encoded)
        decode_time = time.time() - start_time
        
        print(f"Pattern encoding: {encode_time:.2f}s")
        print(f"Pattern decoding: {decode_time:.2f}s")
        
        assert payload == decoded, "Round-trip failed for repetitive pattern"
        print("✅ Repetitive pattern test passed!")

    def test_progressive_sizes(self):
        """Test progressively larger sizes to find performance characteristics."""
        sizes = [1024, 10240, 102400, 1024000]  # 1KB, 10KB, 100KB, 1MB
        results = []
        
        for size in sizes:
            # Much faster random data generation using os.urandom
            payload = os.urandom(size)
            
            # Measure encoding time
            start_time = time.time()
            encoded = mcbase64x32.encode(payload)
            encode_time = time.time() - start_time
            
            # Measure decoding time
            start_time = time.time()
            decoded = mcbase64x32.decode(encoded)
            decode_time = time.time() - start_time
            
            # Verify integrity
            assert payload == decoded, f"Round-trip failed for {size} bytes"
            
            results.append({
                'size': size,
                'size_str': f"{size//1024}KB" if size >= 1024 else f"{size}B",
                'encode_time': encode_time,
                'decode_time': decode_time,
                'total_time': encode_time + decode_time,
                'encoded_size': len(encoded)
            })
        
        # Print performance summary
        print("\nPerformance Summary:")
        print("Size     | Encode  | Decode  | Total   | Output Size")
        print("---------|---------|---------|---------|------------")
        for r in results:
            print(f"{r['size_str']:8} | {r['encode_time']:6.3f}s | {r['decode_time']:6.3f}s | {r['total_time']:6.3f}s | {r['encoded_size']:,}")
        
        # Check that performance scales reasonably (not exponentially)
        for i in range(1, len(results)):
            size_ratio = results[i]['size'] / results[i-1]['size']
            time_ratio = results[i]['total_time'] / results[i-1]['total_time']
            
            # Time should scale roughly linearly (allow up to 2x for overhead)
            assert time_ratio < size_ratio * 2, (
                f"Performance degraded significantly: "
                f"{size_ratio}x size increase caused {time_ratio:.2f}x time increase"
            )

    @pytest.mark.slow
    def test_edge_case_sizes(self):
        """Test edge cases around specific sizes that might cause issues."""
        edge_sizes = [
            2047, 2048, 2049,  # Around 2KB boundary
            8191, 8192, 8193,  # Around 8KB boundary  
            65535, 65536, 65537,  # Around 64KB boundary
            1048575, 1048576, 1048577,  # Around 1MB boundary
        ]
        
        for size in edge_sizes:
            payload = os.urandom(size)
            
            encoded = mcbase64x32.encode(payload)
            decoded = mcbase64x32.decode(encoded)
            
            assert payload == decoded, f"Round-trip failed for edge case size {size}"
            
        print(f"✅ All {len(edge_sizes)} edge case sizes passed!")

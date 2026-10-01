#!/usr/bin/env python3
"""Benchmark script for Bookette K4-W6 codec across all payload tiers.

Covers payload sizes from small chunks (1 B), single page (1,020 B / 1,024 B),
half book (50 pages), full book (100 pages), multi-MB (1, 10, 50, 100 MB),
1 GB (1 GiB), up to the theoretical codec maximum of 4 GB (4,294,967,295 B).
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import bookette


# --- System Memory Helper ---

def get_system_memory() -> Dict[str, float]:
    """Retrieve total and available physical RAM in GB (Windows / cross-platform)."""
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return {
                "total_phys_gb": stat.ullTotalPhys / (1024**3),
                "avail_phys_gb": stat.ullAvailPhys / (1024**3),
                "avail_page_gb": stat.ullAvailPageFile / (1024**3),
            }
        except Exception:
            pass
    return {"total_phys_gb": 0.0, "avail_phys_gb": 0.0, "avail_page_gb": 0.0}


# --- Tier Definitions ---

BYTES_PER_PAGE_RAW = 1024
BYTES_PAGE_1_USEFUL = 1020
BYTES_SUBSEQUENT_PAGE = 1024
MAX_BOOK_PAGES = 100

HALF_BOOK_PAGES = 50
HALF_BOOK_BYTES = BYTES_PAGE_1_USEFUL + (HALF_BOOK_PAGES - 1) * BYTES_SUBSEQUENT_PAGE  # 51,196 B

FULL_BOOK_PAGES = 100
FULL_BOOK_BYTES = BYTES_PAGE_1_USEFUL + (FULL_BOOK_PAGES - 1) * BYTES_SUBSEQUENT_PAGE  # 102,396 B

U32_MAX = 4_294_967_295  # 4 GiB - 1 byte (0xFFFFFFFF)


@dataclass
class TierSpec:
    category: str
    name: str
    size_bytes: int
    default_iterations: int
    is_protected_4gb: bool = False


ALL_TIERS: List[TierSpec] = [
    # Pequeñas
    TierSpec("small", "1 B", 1, 10),
    TierSpec("small", "64 B", 64, 10),
    TierSpec("small", "256 B", 256, 10),
    # Una página
    TierSpec("page", "1,020 B (Pág 1 útil)", 1020, 10),
    TierSpec("page", "1,024 B (Pág 1+2 frontera)", 1024, 10),
    # Medio libro (50 págs de Minecraft)
    TierSpec("book", "51,196 B (Medio libro: 50 págs)", HALF_BOOK_BYTES, 5),
    # Libro entero (100 págs de Minecraft)
    TierSpec("book", "102,396 B (Libro entero: 100 págs)", FULL_BOOK_BYTES, 5),
    # Más MBs
    TierSpec("mbs", "1 MB (1,048,576 B)", 1024 * 1024, 3),
    TierSpec("mbs", "10 MB (10,485,760 B)", 10 * 1024 * 1024, 3),
    TierSpec("mbs", "50 MB (52,428,800 B)", 50 * 1024 * 1024, 2),
    TierSpec("mbs", "100 MB (104,857,600 B)", 100 * 1024 * 1024, 1),
    # 1 GB
    TierSpec("1gb", "1 GB (1,073,741,824 B)", 1024 * 1024 * 1024, 1),
    # Máximo 4 GB (u32::MAX)
    TierSpec("4gb", "4 GB (Máximo 4 GiB - 1: 4,294,967,295 B)", U32_MAX, 1, is_protected_4gb=True),
]


# --- Data Generation Helpers ---

def generate_payload(size: int, pattern: str) -> bytes:
    """Efficiently generate test payload without excessive memory fragmentation."""
    if size == 0:
        return b""
    if pattern == "zeros":
        return b"\x00" * size

    if pattern == "cyclic":
        # Generate 1 MB base cyclic block and tile it
        base_size = min(size, 1024 * 1024)
        base = bytes(i % 256 for i in range(base_size))
        repeats = size // base_size
        remainder = size % base_size
        if repeats == 0:
            return base[:remainder]
        chunks = [base] * repeats
        if remainder:
            chunks.append(base[:remainder])
        return b"".join(chunks)

    if pattern == "pseudorandom":
        # Deterministic 1 MB PRNG block
        # Simple fast LCG to generate deterministic bytes
        base_size = min(size, 1024 * 1024)
        buf = bytearray(base_size)
        state = 0x12345678
        for i in range(base_size):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            buf[i] = (state >> 16) & 0xFF
        base = bytes(buf)
        repeats = size // base_size
        remainder = size % base_size
        if repeats == 0:
            return base[:remainder]
        chunks = [base] * repeats
        if remainder:
            chunks.append(base[:remainder])
        return b"".join(chunks)

    raise ValueError(f"Unknown pattern: {pattern}")


# --- Benchmark Result Dataclass ---

@dataclass
class BenchRunResult:
    category: str
    tier_name: str
    size_bytes: int
    pattern: str
    mode: str
    iterations: int
    encode_time_sec: float
    encode_speed_mb_s: float
    decode_time_sec: Optional[float]
    decode_speed_mb_s: Optional[float]
    encoded_chars: int
    verified: Optional[bool]

# --- Benchmark Runners ---

def benchmark_oneshot(
    payload: bytes,
    tier: TierSpec,
    pattern: str,
    iterations: int,
    verify: bool,
) -> BenchRunResult:
    """Benchmark Rust native bookette.encode and bookette.decode."""
    # Warmup
    _ = bookette.encode(payload[: min(len(payload), 1024)])

    gc.collect()

    # Time Encode
    t_enc_start = time.perf_counter_ns()
    encoded: str = ""
    for _ in range(iterations):
        encoded = bookette.encode(payload)
    t_enc_end = time.perf_counter_ns()
    enc_duration = (t_enc_end - t_enc_start) / (1e9 * iterations)

    gc.collect()

    # Time Decode
    t_dec_start = time.perf_counter_ns()
    decoded: bytes = b""
    for _ in range(iterations):
        decoded = bookette.decode(encoded)
    t_dec_end = time.perf_counter_ns()
    dec_duration = (t_dec_end - t_dec_start) / (1e9 * iterations)

    # Verification: None when disabled, True/False when evaluated
    verified: Optional[bool] = None
    if verify:
        if tier.size_bytes >= 10 * 1024 * 1024:
            verified = (hashlib.sha256(decoded).digest() == hashlib.sha256(payload).digest())
        else:
            verified = (decoded == payload)
    size_mb = tier.size_bytes / (1024 * 1024)
    enc_speed = (size_mb / enc_duration) if enc_duration > 0 else 0.0
    dec_speed = (size_mb / dec_duration) if dec_duration > 0 else 0.0

    return BenchRunResult(
        category=tier.category,
        tier_name=tier.name,
        size_bytes=tier.size_bytes,
        pattern=pattern,
        mode="oneshot (Rust)",
        iterations=iterations,
        encode_time_sec=enc_duration,
        encode_speed_mb_s=enc_speed,
        decode_time_sec=dec_duration,
        decode_speed_mb_s=dec_speed,
        encoded_chars=len(encoded),
        verified=verified,
    )


def benchmark_streaming(
    payload: bytes,
    tier: TierSpec,
    pattern: str,
    iterations: int,
    verify: bool,
) -> BenchRunResult:
    """Benchmark streaming bookette.encode_pages and bookette.decode_pages with O(1) memory."""
    gc.collect()

    # Time Encode (O(1) memory: iterate without retaining pages in a list)
    t_enc_start = time.perf_counter_ns()
    total_chars = 0
    for _ in range(iterations):
        total_chars = 0
        for page in bookette.encode_pages(payload):
            total_chars += len(page)
    t_enc_end = time.perf_counter_ns()
    enc_duration = (t_enc_end - t_enc_start) / (1e9 * iterations)

    gc.collect()

    # Time Decode:
    # Only pre-encode into a list to measure pure decode if size <= 10 MB.
    # For sizes > 10 MB, streaming decode is skipped to avoid retaining millions
    # of page strings in RAM or mislabeling pipeline time as pure decode time.
    verified: Optional[bool] = None
    dec_duration: Optional[float] = None
    dec_speed: Optional[float] = None

    if tier.size_bytes <= 10 * 1024 * 1024:
        pages = list(bookette.encode_pages(payload))
        gc.collect()
        expected_hash = hashlib.sha256(payload).digest() if verify else None
        t_dec_start = time.perf_counter_ns()
        for _ in range(iterations):
            hasher = hashlib.sha256() if verify else None
            for chunk in bookette.decode_pages(pages):
                if hasher:
                    hasher.update(chunk)
            if hasher and hasher.digest() == expected_hash:
                verified = True
            elif hasher:
                verified = False
        t_dec_end = time.perf_counter_ns()
        dec_duration = (t_dec_end - t_dec_start) / (1e9 * iterations)
        del pages
        size_mb = tier.size_bytes / (1024 * 1024)
        dec_speed = (size_mb / dec_duration) if dec_duration > 0 else 0.0
    else:
        dec_duration = None
        dec_speed = None
        verified = None
    size_mb = tier.size_bytes / (1024 * 1024)
    enc_speed = (size_mb / enc_duration) if enc_duration > 0 else 0.0
    return BenchRunResult(
        category=tier.category,
        tier_name=tier.name,
        size_bytes=tier.size_bytes,
        pattern=pattern,
        mode="streaming (Python)",
        iterations=iterations,
        encode_time_sec=enc_duration,
        encode_speed_mb_s=enc_speed,
        decode_time_sec=dec_duration,
        decode_speed_mb_s=dec_speed,
        encoded_chars=total_chars,
        verified=verified,
    )

def stage_disk_fixture(
    payload: bytes,
    tier: TierSpec,
    verify: bool,
    fixture_dir: Optional[str] = None,
) -> Optional[Tuple[str, Optional[str], float, float, int]]:
    """Write encoded pages to a disk fixture with O(1) memory and return metadata."""
    import os
    import shutil
    import tempfile

    target_dir = fixture_dir or ".scratch"
    os.makedirs(target_dir, exist_ok=True)

    estimated_bytes = int(tier.size_bytes * 2.8)
    try:
        _, _, free_bytes = shutil.disk_usage(target_dir)
        if free_bytes < estimated_bytes * 1.2:
            print(
                f"  -> Disk Decode: Skipped for {tier.name} (insufficient disk space: "
                f"needs ~{estimated_bytes / (1024**3):.2f} GB, free: {free_bytes / (1024**3):.2f} GB)."
            )
            return None
    except Exception as exc:
        print(f"  -> Disk Decode: Skipped for {tier.name} (could not verify disk space: {exc}).")
        return None

    with tempfile.NamedTemporaryFile(
        dir=target_dir,
        prefix=f"bench_fixture_{tier.category}_{tier.size_bytes}_",
        suffix=".txt",
        delete=False,
    ) as tmp_f:
        fixture_file = tmp_f.name

    expected_hash = hashlib.sha256(payload).hexdigest() if verify else None

    success = False
    try:
        print(f"  -> Disk Decode: Generating disk fixture ({tier.name})...", flush=True)
        t_gen_start = time.perf_counter_ns()
        page_count = 0
        total_chars = 0
        with open(fixture_file, "w", encoding="utf-8") as f:
            for page in bookette.encode_pages(payload):
                f.write(page + "\n")
                page_count += 1
                total_chars += len(page)
        t_gen_end = time.perf_counter_ns()
        gen_duration = (t_gen_end - t_gen_start) / 1e9
        actual_file_size = os.path.getsize(fixture_file)

        size_mb = tier.size_bytes / (1024 * 1024)
        enc_speed = (size_mb / gen_duration) if gen_duration > 0 else 0.0

        print(
            f"     Fixture: {actual_file_size / (1024*1024):.2f} MB ({page_count} pages) "
            f"written in {gen_duration:.2f}s ({enc_speed:.2f} MB/s)",
            flush=True,
        )

        success = True
        return fixture_file, expected_hash, gen_duration, enc_speed, total_chars
    finally:
        if not success and os.path.exists(fixture_file):
            try:
                os.remove(fixture_file)
            except OSError:
                pass
def measure_disk_decode(
    fixture_file: str,
    tier: TierSpec,
    pattern: str,
    expected_hash: Optional[str],
    gen_duration: float,
    enc_speed: float,
    total_chars: int,
    verify: bool,
    keep_fixture: bool = False,
) -> BenchRunResult:
    """Perform timed disk-backed decode pass with O(1) memory and verify SHA-256."""
    import os

    try:
        def read_pages(path: str) -> Iterator[str]:
            with open(path, "r", encoding="utf-8") as pf:
                for line in pf:
                    yield line.rstrip("\r\n")

        print(f"  -> Disk Decode: Running timed decode pass with incremental hash...", flush=True)
        t_dec_start = time.perf_counter_ns()
        hasher = hashlib.sha256() if verify else None
        decoded_bytes = 0
        for chunk in bookette.decode_pages(read_pages(fixture_file)):
            decoded_bytes += len(chunk)
            if hasher:
                hasher.update(chunk)
        t_dec_end = time.perf_counter_ns()
        dec_duration = (t_dec_end - t_dec_start) / 1e9
        size_mb = tier.size_bytes / (1024 * 1024)
        dec_speed = (size_mb / dec_duration) if dec_duration > 0 else 0.0

        verified: Optional[bool] = False
        if hasher and expected_hash:
            verified = (hasher.hexdigest() == expected_hash and decoded_bytes == tier.size_bytes)
        elif not verify:
            verified = None

        return BenchRunResult(
            category=tier.category,
            tier_name=tier.name,
            size_bytes=tier.size_bytes,
            pattern=pattern,
            mode="disk-stream (Python)",
            iterations=1,
            encode_time_sec=gen_duration,
            encode_speed_mb_s=enc_speed,
            decode_time_sec=dec_duration,
            decode_speed_mb_s=dec_speed,
            encoded_chars=total_chars,
            verified=verified,
        )
    finally:
        if not keep_fixture:
            try:
                if os.path.exists(fixture_file):
                    os.remove(fixture_file)
            except OSError:
                pass

# --- Table & Report Formatting ---

def format_time(seconds: Optional[float]) -> str:
    """Format time adaptively from microseconds to seconds, or N/A."""
    if seconds is None:
        return "       N/A"
    if seconds < 1e-4:
        return f"{seconds * 1e6:6.1f} µs"
    if seconds < 1.0:
        return f"{seconds * 1e3:6.2f} ms"
    return f"{seconds:6.3f} s "


def print_results_table(results: List[BenchRunResult]) -> None:
    """Print ASCII summary table to stdout."""
    header = (
        f"{'Tier / Size':<36} | {'Mode':<18} | {'Enc Time':>10} | {'Enc Speed':>12} | "
        f"{'Dec Time':>10} | {'Dec Speed':>12} | {'Verify':^6}"
    )
    sep = "-" * len(header)
    print("\n" + sep)
    print(header)
    print(sep)

    for r in results:
        if r.verified is None:
            v_str = " N/A "
        elif r.verified:
            v_str = " OK  "
        else:
            v_str = "FAIL "

        enc_s = f"{r.encode_speed_mb_s:8.2f} MB/s" if r.size_bytes >= 1020 else f"{r.encode_speed_mb_s:8.4f} MB/s"
        if r.decode_speed_mb_s is not None:
            dec_s = f"{r.decode_speed_mb_s:8.2f} MB/s" if r.size_bytes >= 1020 else f"{r.decode_speed_mb_s:8.4f} MB/s"
        else:
            dec_s = "         N/A"

        print(
            f"{r.tier_name:<36} | {r.mode:<18} | {format_time(r.encode_time_sec):>10} | "
            f"{enc_s:>12} | {format_time(r.decode_time_sec):>10} | {dec_s:>12} | {v_str:^6}"
        )
    print(sep + "\n")

def generate_markdown_report(results: List[BenchRunResult], metadata: Dict[str, Any]) -> str:
    """Generate Markdown report with benchmark metadata and metrics."""
    lines = [
        "# Bookette K4-W6 Codec Benchmark Report",
        "",
        f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"- **Platform:** {sys.platform} (Python {sys.version.split()[0]})",
        f"- **RAM:** Total {metadata.get('total_phys_gb', 0):.1f} GB, Available {metadata.get('avail_phys_gb', 0):.1f} GB",
        f"- **Page Spec:** {bookette.MAX_BYTES_PER_PAGE} Bytes/Page, 1,024 Chars/Page",
        "",
        "| Tier / Size | Mode | Encode Time | Encode Speed | Decode Time | Decode Speed | Verified |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|",
    ]
    for r in results:
        v_str = "✓" if r.verified is True else ("✗" if r.verified is False else "N/A")
        dec_t = format_time(r.decode_time_sec).strip()
        dec_s = f"{r.decode_speed_mb_s:.2f} MB/s" if r.decode_speed_mb_s is not None else "N/A"
        lines.append(
            f"| `{r.tier_name}` | {r.mode} | {format_time(r.encode_time_sec).strip()} | "
            f"{r.encode_speed_mb_s:.2f} MB/s | {dec_t} | "
            f"{dec_s} | {v_str} |"
        )
    lines.append("")
    return "\n".join(lines)


# --- Main CLI ---

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bookette K4-W6 multi-tier benchmark runner (small, page, book, MBs, 1GB, 4GB)."
    )
    parser.add_argument(
        "--tier",
        nargs="+",
        choices=["small", "page", "book", "mbs", "1gb", "4gb", "safe", "all"],
        default=["safe"],
        help="Tier selection: 'safe' runs up to 100 MB, 'all' includes 1 GB and 4 GB (requires --allow-4gb), or specific tier(s) (e.g. --tier small page book).",
    )
    parser.add_argument(
        "--pattern",
        choices=["cyclic", "zeros", "pseudorandom"],
        default="cyclic",
        help="Payload pattern: cyclic (0..255), zeros (Bucket 0 stress), or pseudorandom.",
    )
    parser.add_argument(
        "--mode",
        choices=["oneshot", "streaming", "disk", "both", "all"],
        default="oneshot",
        help="Benchmark mode: 'oneshot' (Rust engine), 'streaming' (generator), 'disk' (disk-backed page fixture), 'both' (oneshot+streaming), or 'all'.",
    )
    parser.add_argument(
        "--disk-fixture",
        action="store_true",
        help="Automatically use a disk-backed page fixture for tiers > 10 MB in streaming mode to benchmark independent decode.",
    )
    parser.add_argument(
        "--fixture-dir",
        default=".scratch",
        help="Directory to store temporary disk fixture files (default: .scratch).",
    )
    parser.add_argument(
        "--keep-fixtures",
        action="store_true",
        help="Retain temporary fixture files on disk instead of deleting them after benchmark.",
    )
    parser.add_argument(
        "--allow-large-oneshot",
        action="store_true",
        help="Allow oneshot (contiguous buffer) encode for >= 1 GiB payloads. Default is to skip >= 1 GiB in oneshot to prevent CPython allocator panic.",
    )
    parser.add_argument(
        "--allow-4gb",
        action="store_true",
        help="Safety opt-in flag required to allocate and benchmark the 4 GB (4,294,967,295 B) tier.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify roundtrip byte-for-byte parity (enabled by default).",
    )
    parser.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        help="Disable roundtrip verification to measure pure raw throughput.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Path to export results as JSON.",
    )
    parser.add_argument(
        "--markdown",
        dest="md_path",
        help="Path to export results as Markdown report.",
    )

    args = parser.parse_args()

    mem = get_system_memory()
    print("=" * 60)
    print("🚀 Bookette K4-W6 Codec Benchmark Suite")
    print("=" * 60)
    print(f"System RAM: Total {mem['total_phys_gb']:.2f} GB | Available {mem['avail_phys_gb']:.2f} GB")
    print(f"Pattern: {args.pattern} | Mode: {args.mode} | Verify: {args.verify}")
    print("=" * 60)

    # Filter tiers
    tier_requests = set(args.tier)
    selected_tiers: List[TierSpec] = []
    for t in ALL_TIERS:
        if "all" in tier_requests:
            selected_tiers.append(t)
        elif "safe" in tier_requests and not t.is_protected_4gb and t.category != "1gb":
            selected_tiers.append(t)
        elif t.category in tier_requests:
            selected_tiers.append(t)
    # Check 4 GB protection
    has_4gb = any(t.is_protected_4gb for t in selected_tiers)
    if has_4gb and not args.allow_4gb:
        print("\n⚠️  [SAFETY GUARD] 4 GB tier requested but --allow-4gb was not passed.")
        print(f"   A 4 GB payload in memory requires ~20-28 GB combined RAM during encode.")
        print(f"   Current available RAM is {mem['avail_phys_gb']:.2f} GB.")
        print("   Skipping 4 GB tier. Pass --allow-4gb explicitly if your system has sufficient RAM/paging.\n")
        selected_tiers = [t for t in selected_tiers if not t.is_protected_4gb]

    # Check 1 GB RAM warning
    has_1gb = any(t.category == "1gb" for t in selected_tiers)
    if has_1gb and mem["avail_phys_gb"] > 0 and mem["avail_phys_gb"] < 4.0:
        print("\n⚠️  [MEMORY WARNING] Available RAM is under 4 GB. 1 GB tier may cause swapping.\n")

    results: List[BenchRunResult] = []

    for tier in selected_tiers:
        print(f"Running [{tier.category.upper()}] {tier.name} (pattern={args.pattern})...", flush=True)

        # Determine runnable modes for this tier before allocating payload
        can_run_oneshot = args.mode in ("oneshot", "both", "all")
        oneshot_skipped = can_run_oneshot and (tier.size_bytes >= 1024 * 1024 * 1024 and not args.allow_large_oneshot)
        run_oneshot = can_run_oneshot and not oneshot_skipped

        can_run_streaming = args.mode in ("streaming", "both", "all")
        streaming_skipped = can_run_streaming and (tier.size_bytes > 50 * 1024 * 1024 and not ({"1gb", "4gb"} & tier_requests))
        run_streaming = can_run_streaming and not streaming_skipped

        run_disk = args.mode in ("disk", "all") or (
            args.disk_fixture and tier.size_bytes > 10 * 1024 * 1024 and args.mode in ("streaming", "both")
        )

        if not (run_oneshot or run_streaming or run_disk):
            if oneshot_skipped:
                print(
                    f"  -> Oneshot:   Skipped for {tier.name} (>= 1 GiB requires --allow-large-oneshot; "
                    f"use --mode disk for O(1) RAM streaming)."
                )
            if streaming_skipped:
                print(f"  -> Streaming: Skipped for {tier.name} (> 50 MB, pure Python generator).")
            continue

        if oneshot_skipped:
            print(
                f"  -> Oneshot:   Skipped for {tier.name} (>= 1 GiB requires --allow-large-oneshot; "
                f"use --mode disk for O(1) RAM streaming)."
            )
        if streaming_skipped:
            print(f"  -> Streaming: Skipped for {tier.name} (> 50 MB, pure Python generator).")

        payload = generate_payload(tier.size_bytes, args.pattern)

        # Run oneshot
        if run_oneshot:
            try:
                res_oneshot = benchmark_oneshot(
                    payload, tier, args.pattern, tier.default_iterations, args.verify
                )
                results.append(res_oneshot)
                print(
                    f"  -> Oneshot:   Encode {res_oneshot.encode_speed_mb_s:7.2f} MB/s | "
                    f"Decode {res_oneshot.decode_speed_mb_s:7.2f} MB/s | Verified={res_oneshot.verified}"
                )
            except MemoryError:
                print(f"  -> Oneshot:   FAILED with MemoryError (Out of Memory)!")

        # Run streaming
        if run_streaming:
            try:
                res_streaming = benchmark_streaming(
                    payload, tier, args.pattern, 1, args.verify
                )
                results.append(res_streaming)
                dec_str = (
                    f"{res_streaming.decode_speed_mb_s:7.2f} MB/s"
                    if res_streaming.decode_speed_mb_s is not None
                    else "    N/A"
                )
                v_str = (
                    str(res_streaming.verified)
                    if res_streaming.verified is not None
                    else "N/A"
                )
                print(
                    f"  -> Streaming: Encode {res_streaming.encode_speed_mb_s:7.2f} MB/s | "
                    f"Decode {dec_str} | Verified={v_str}"
                )
            except MemoryError:
                print(f"  -> Streaming: FAILED with MemoryError (Out of Memory)!")
        disk_stage = None
        if run_disk:
            try:
                disk_stage = stage_disk_fixture(
                    payload,
                    tier,
                    args.verify,
                    fixture_dir=args.fixture_dir,
                )
            except (MemoryError, OSError) as exc:
                print(f"  -> Disk Decode: FAILED ({type(exc).__name__}: {exc}) during staging!")

        # Explicit free and GC before decode pass guarantees O(1) memory
        del payload
        gc.collect()

        if disk_stage is not None:
            fixture_file, exp_hash, gen_dur, enc_spd, tot_chars = disk_stage
            try:
                res_disk = measure_disk_decode(
                    fixture_file=fixture_file,
                    tier=tier,
                    pattern=args.pattern,
                    expected_hash=exp_hash,
                    gen_duration=gen_dur,
                    enc_speed=enc_spd,
                    total_chars=tot_chars,
                    verify=args.verify,
                    keep_fixture=args.keep_fixtures,
                )
                results.append(res_disk)
                print(
                    f"  -> Disk Stream: Encode {res_disk.encode_speed_mb_s:7.2f} MB/s | "
                    f"Decode {res_disk.decode_speed_mb_s:7.2f} MB/s | Verified={res_disk.verified}"
                )
            except (MemoryError, OSError) as exc:
                print(f"  -> Disk Stream: FAILED ({type(exc).__name__}: {exc}) during decode!")

    print_results_table(results)

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        print(f"Saved JSON report to: {args.json_path}")

    if args.md_path:
        md_text = generate_markdown_report(results, mem)
        with open(args.md_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        print(f"Saved Markdown report to: {args.md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

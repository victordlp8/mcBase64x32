#!/usr/bin/env python3
"""Benchmark script generating a high-resolution throughput plot for Bookette K4-W6.

Measures encode and decode speeds across payload sizes (1 KB to 50 MB) and
plots them with the exact detected processor name in the chart header.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import statistics
import sys
import time
from typing import Dict, List, Tuple

import bookette


def get_processor_name() -> str:
    """Retrieve the human-readable CPU brand string."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return val.strip()
        except Exception:
            pass
    proc = platform.processor()
    if proc:
        return proc
    return platform.machine()


def generate_payload(size: int, pattern: str = "cyclic") -> bytes:
    """Generate test payload of specified byte size."""
    if pattern == "zeros":
        return b"\x00" * size
    if pattern == "cyclic":
        base_size = min(size, 1024 * 1024)
        base = bytes(i % 256 for i in range(base_size))
        repeats = size // base_size
        rem = size % base_size
        return (base * repeats) + base[:rem]
    # pseudorandom LCG
    state = 0x12345678
    buf = bytearray(size)
    for i in range(size):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        buf[i] = (state >> 16) & 0xFF
    return bytes(buf)


def timed_median(fn, iters: int, rounds: int = 5) -> float:
    """Execute fn() and return median elapsed time per iteration in seconds."""
    fn()  # Warmup
    samples: List[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for _ in range(iters):
            _ = fn()
        samples.append((time.perf_counter() - t0) / iters)
    return statistics.median(samples)


def run_benchmark(
    sizes: List[Tuple[str, int]],
    pattern: str = "cyclic",
) -> Dict[str, List[float]]:
    """Run encode, decode, and streaming benchmarks across all payload sizes."""
    data: Dict[str, List[float]] = {
        "sizes_bytes": [],
        "encode_mbs": [],
        "decode_mbs": [],
        "encode_pages_mbs": [],
        "decode_pages_mbs": [],
    }

    print("=" * 80)
    print("🚀 RUNNING BOOKETTE K4-W6 BENCHMARK SUITE")
    print("=" * 80)
    print(f"{'Size':<12} | {'Encode (Rust)':>14} | {'Decode (Rust)':>14} | {'Enc Pages':>14} | {'Dec Pages':>14}")
    print("-" * 80)

    for label, size in sizes:
        p = generate_payload(size, pattern)
        iters = 3 if size >= 10 * 1024 * 1024 else (10 if size >= 1024 * 1024 else 30)

        # 1. Whole-buffer encode
        t_enc = timed_median(lambda: bookette.encode(p), iters)
        enc_str = bookette.encode(p)

        # 2. Whole-buffer decode
        t_dec = timed_median(lambda: bookette.decode(enc_str), iters)
        dec_bytes = bookette.decode(enc_str)
        assert dec_bytes == p, f"Decode mismatch at size {size}!"

        # 3. Streaming encode_pages
        t_enc_p = timed_median(lambda: sum(1 for _ in bookette.encode_pages(p)), iters)
        pages = list(bookette.encode_pages(p))

        # 4. Streaming decode_pages
        t_dec_p = timed_median(lambda: sum(len(c) for c in bookette.decode_pages(pages)), iters)
        dec_pages_bytes = b"".join(bookette.decode_pages(pages))
        assert dec_pages_bytes == p, f"Streaming decode mismatch at size {size}!"

        mb = size / (1024 * 1024)
        s_enc = mb / t_enc
        s_dec = mb / t_dec
        s_enc_p = mb / t_enc_p
        s_dec_p = mb / t_dec_p

        data["sizes_bytes"].append(size)
        data["encode_mbs"].append(s_enc)
        data["decode_mbs"].append(s_dec)
        data["encode_pages_mbs"].append(s_enc_p)
        data["decode_pages_mbs"].append(s_dec_p)

        print(f"{label:<12} | {s_enc:10.2f} MB/s | {s_dec:10.2f} MB/s | {s_enc_p:10.2f} MB/s | {s_dec_p:10.2f} MB/s")

    print("-" * 80)
    return data


def plot_results(
    data: Dict[str, List[float]],
    cpu_name: str,
    output_path: str = "benchmark_throughput.png",
) -> None:
    """Generate dark-mode publication-quality plot using matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            f"\n⚠️  matplotlib is not installed in the current environment.\n"
            f"   Table results were printed above. To generate the chart graphic, run:\n"
            f"     uv run --with matplotlib python scripts/plot_benchmark.py\n"
            f"   or install it via:\n"
            f"     pip install matplotlib\n"
        )
        return
    sizes_bytes = data["sizes_bytes"]
    sizes_kb = [s / 1024.0 for s in sizes_bytes]

    # Dark mode theme
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)

    # Background colors
    fig.patch.set_facecolor("#0a0f1d")
    ax.set_facecolor("#0f172a")

    # Grid
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, color="#334155", alpha=0.7)

    # Plot curves
    ax.plot(
        sizes_kb,
        data["encode_mbs"],
        color="#38bdf8",
        marker="o",
        linewidth=2.5,
        markersize=7,
        label="Whole-Buffer Encode (Rust + Rayon ≥64KB)",
    )
    ax.plot(
        sizes_kb,
        data["decode_mbs"],
        color="#34d399",
        marker="s",
        linewidth=2.5,
        markersize=7,
        label="Whole-Buffer Decode (Rust 128 KiB LUT)",
    )
    ax.plot(
        sizes_kb,
        data["encode_pages_mbs"],
        color="#fbbf24",
        marker="^",
        linewidth=2.0,
        markersize=6,
        linestyle="--",
        label="Streaming Page Encode (Native PageEncoder)",
    )
    ax.plot(
        sizes_kb,
        data["decode_pages_mbs"],
        color="#c084fc",
        marker="d",
        linewidth=2.0,
        markersize=6,
        linestyle="--",
        label="Streaming Page Decode (Native PageDecoder)",
    )

    # Annotate peak values
    max_enc = max(data["encode_mbs"])
    idx_max_enc = data["encode_mbs"].index(max_enc)
    ax.annotate(
        f"Peak Encode: {max_enc:.1f} MB/s",
        xy=(sizes_kb[idx_max_enc], max_enc),
        xytext=(sizes_kb[idx_max_enc] * 0.4, max_enc * 1.05),
        arrowprops=dict(facecolor="#38bdf8", shrink=0.08, width=1.5, headwidth=6),
        fontsize=9,
        fontweight="bold",
        color="#38bdf8",
        bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", ec="#38bdf8", lw=1),
    )

    max_dec = max(data["decode_mbs"])
    idx_max_dec = data["decode_mbs"].index(max_dec)
    ax.annotate(
        f"Peak Decode: {max_dec:.1f} MB/s",
        xy=(sizes_kb[idx_max_dec], max_dec),
        xytext=(sizes_kb[idx_max_dec] * 1.5, max_dec * 0.95),
        arrowprops=dict(facecolor="#34d399", shrink=0.08, width=1.5, headwidth=6),
        fontsize=9,
        fontweight="bold",
        color="#34d399",
        bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", ec="#34d399", lw=1),
    )

    # X-axis scale (logarithmic with friendly labels)
    ax.set_xscale("log")
    ax.set_xlim(min(sizes_kb) * 0.7, max(sizes_kb) * 1.4)

    # Custom ticks
    x_ticks = [1, 4, 16, 64, 256, 1024, 4096, 16384, 51200]
    x_labels = ["1 KB", "4 KB", "16 KB", "64 KB", "256 KB", "1 MB", "4 MB", "16 MB", "50 MB"]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, fontsize=9, color="#94a3b8")

    # Titles & Labels
    ax.set_title(
        "Bookette K4-W6 Codec — Throughput Scaling vs Payload Size",
        fontsize=16,
        fontweight="bold",
        color="#f8fafc",
        pad=22,
    )
    fig.text(
        0.5,
        0.915,
        f"Processor: {cpu_name}  |  Platform: {sys.platform}  |  Threads: {os.cpu_count() or 1}",
        ha="center",
        fontsize=10,
        color="#94a3b8",
        fontfamily="monospace",
    )

    ax.set_xlabel("Payload Size (Log Scale)", fontsize=11, fontweight="semibold", color="#cbd5e1", labelpad=10)
    ax.set_ylabel("Throughput (MB/s)", fontsize=11, fontweight="semibold", color="#cbd5e1", labelpad=10)

    # Legend
    ax.legend(
        loc="upper left",
        frameon=True,
        facecolor="#1e293b",
        edgecolor="#475569",
        fontsize=9,
        labelcolor="#e2e8f0",
    )

    # Ticks styling
    ax.tick_params(colors="#94a3b8", which="both")
    for spine in ax.spines.values():
        spine.set_color("#475569")

    # Watermark / Footer
    fig.text(
        0.98,
        0.02,
        "Bookette K4-W6 v4.0.0  •  1,024 B/Page Minecraft Java Edition 26.3 Certified",
        ha="right",
        fontsize=8,
        color="#64748b",
        fontstyle="italic",
    )

    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"\n📊 Benchmark chart successfully saved to: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Bookette K4-W6 codec and generate throughput plot."
    )
    parser.add_argument(
        "--output",
        "-o",
        default="benchmark_throughput.png",
        help="Output PNG path (default: benchmark_throughput.png).",
    )
    parser.add_argument(
        "--pattern",
        choices=["cyclic", "zeros", "pseudorandom"],
        default="cyclic",
        help="Data pattern for test payloads (default: cyclic).",
    )
    args = parser.parse_args()

    cpu_name = get_processor_name()
    print("=" * 80)
    print(f"Processor: {cpu_name}")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {platform.python_version()}")
    print("=" * 80)

    sizes: List[Tuple[str, int]] = [
        ("1 KB", 1024),
        ("4 KB", 4 * 1024),
        ("16 KB", 16 * 1024),
        ("64 KB", 64 * 1024),
        ("256 KB", 256 * 1024),
        ("1 MB", 1024 * 1024),
        ("4 MB", 4 * 1024 * 1024),
        ("16 MB", 16 * 1024 * 1024),
        ("50 MB", 50 * 1024 * 1024),
    ]

    data = run_benchmark(sizes, pattern=args.pattern)
    plot_results(data, cpu_name, output_path=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

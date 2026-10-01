use pyo3::exceptions::{PyStopIteration, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};
use std::sync::LazyLock;

use rayon::prelude::*;

const WIDTH_1_CHARS: &str = include_str!("1_width.txt");
const WIDTH_2_CHARS: &str = include_str!("2_width.txt");
const WIDTH_3_CHARS: &str = include_str!("3_width.txt");

pub const N1: usize = 106;
pub const N2: usize = 211;
pub const N3: usize = 38;

const N1_U64: u64 = N1 as u64;
const N2_U64: u64 = N2 as u64;
const N3_U64: u64 = N3 as u64;

pub const MAX_BYTES_PER_PAGE: usize = 1024;
const QUARTETS_PER_PAGE: usize = 256;
const CHARS_PER_PAGE: usize = QUARTETS_PER_PAGE * 4; // 1024 characters per page
const DATA_QUARTETS_PAGE_1: usize = 255; // 1020 bytes of payload on Page 1
const DATA_QUARTETS_SUBSEQUENT: usize = 256; // 1024 bytes of payload on Pages 2..N
const BYTES_PAGE_1: usize = DATA_QUARTETS_PAGE_1 * 4; // 1020 payload bytes on Page 1
const BYTES_SUBSEQUENT: usize = DATA_QUARTETS_SUBSEQUENT * 4; // 1024 payload bytes on Pages 2..N

/// The 15 normative K4-W6 bucket glyph widths in ascending capacity order.
pub const BUCKET_WIDTHS: [[u8; 4]; 15] = [
    [1, 1, 1, 1], // 0
    [2, 1, 1, 1],
    [1, 2, 1, 1],
    [1, 1, 2, 1],
    [1, 1, 1, 2], // 1..4
    [3, 1, 1, 1],
    [1, 3, 1, 1],
    [1, 1, 3, 1],
    [1, 1, 1, 3], // 5..8
    [2, 2, 1, 1],
    [2, 1, 2, 1],
    [2, 1, 1, 2], // 9..11
    [1, 2, 2, 1],
    [1, 2, 1, 2],
    [1, 1, 2, 2], // 12..14
];

const fn width_to_radix(w: u8) -> u64 {
    match w {
        1 => N1_U64,
        2 => N2_U64,
        _ => N3_U64,
    }
}

#[derive(Clone, Copy)]
pub struct BucketInfo {
    pub offset: u64,
    pub widths: [u8; 4],
    pub radices: [u64; 3], // S2, S3, S4
}

/// Fully derived at compile-time: offsets and radices for all 15 buckets.
pub const BUCKET_TABLE: [BucketInfo; 15] = {
    let mut table = [BucketInfo {
        offset: 0,
        widths: [0; 4],
        radices: [0; 3],
    }; 15];
    let mut off = 0u64;
    let mut i = 0;
    while i < 15 {
        let w = BUCKET_WIDTHS[i];
        let s2 = width_to_radix(w[1]);
        let s3 = width_to_radix(w[2]);
        let s4 = width_to_radix(w[3]);
        let cap = width_to_radix(w[0]) * s2 * s3 * s4;
        table[i] = BucketInfo {
            offset: off,
            widths: w,
            radices: [s2, s3, s4],
        };
        off += cap;
        i += 1;
    }
    table
};

pub const OFFSETS: [u64; 15] = {
    let mut offs = [0u64; 15];
    let mut i = 0;
    while i < 15 {
        offs[i] = BUCKET_TABLE[i].offset;
        i += 1;
    }
    offs
};

pub const BUCKET_14_CUTOFF: u64 = (1u64 << 32) - BUCKET_TABLE[14].offset;

static CHARS_A1: LazyLock<Vec<char>> = LazyLock::new(|| WIDTH_1_CHARS.chars().collect());
static CHARS_A2: LazyLock<Vec<char>> = LazyLock::new(|| WIDTH_2_CHARS.chars().collect());
static CHARS_A3: LazyLock<Vec<char>> = LazyLock::new(|| WIDTH_3_CHARS.chars().collect());

/// Flat 128 KiB decode table indexed by BMP code point.
///
/// Entry layout: bits 0..=9 hold `index + 1`, bits 10..=11 hold the glyph width (1..=3),
/// and `0` means "not in the vocabulary". Every vocabulary glyph is BMP, so two bytes per
/// code point cover the whole domain. Measured end-to-end on this crate's own benchmark, the
/// lookup plus dispatch change below raised whole-buffer decode by 2.7x-3.9x, with the largest
/// gains on incompressible input. The prototype that motivated it is
/// `.scratch/prototypes/proto4_branchless.rs`; it did not collect branch or cache counters, so
/// treat "binary search" as the thing replaced, not a proven cost attribution.
static CHAR_LUT: LazyLock<Box<[u16; 65536]>> = LazyLock::new(|| {
    let mut lut = Box::new([0u16; 65536]);
    for (width, set) in [(1u16, &*CHARS_A1), (2, &*CHARS_A2), (3, &*CHARS_A3)] {
        for (i, &ch) in set.iter().enumerate() {
            // Invariant: the catalog is BMP-only, which is what makes a 65536-entry table
            // sufficient. Assert rather than truncate, so a non-BMP catalog fails loudly
            // instead of silently losing glyphs.
            let cp = ch as u32;
            assert!(
                cp < 65536,
                "catalog glyph {ch:?} (U+{cp:04X}) is outside the BMP"
            );
            lut[cp as usize] = (width << 10) | ((i as u16) + 1);
        }
    }
    lut
});

/// Branchless bucket dispatch. `combo` packs the four glyph widths in base 3:
/// `(w1-1)*27 + (w2-1)*9 + (w3-1)*3 + (w4-1)`, range `0..=80`.
///
/// The payload is `(offset, S2, S3, S4)` for the corresponding bucket; `S2 == 0` marks a
/// width pattern the format never produces. Replacing the 15-arm `match` with this lookup was
/// the larger half of the measured decode gain above; no counter-based attribution was taken.
const COMBO_PARAMS: [(u64, u64, u64, u64); 81] = {
    let mut table = [(0u64, 0u64, 0u64, 0u64); 81];
    let mut id = 0;
    while id < 15 {
        let b = BUCKET_TABLE[id];
        let w = b.widths;
        let combo = ((w[0] - 1) as usize) * 27
            + ((w[1] - 1) as usize) * 9
            + ((w[2] - 1) as usize) * 3
            + ((w[3] - 1) as usize);
        table[combo] = (b.offset, b.radices[0], b.radices[1], b.radices[2]);
        id += 1;
    }
    table
};

/// Bounds-safe glyph read: code points outside the BMP, or absent from the vocabulary, yield `0`.
///
/// The BMP guard is required — indexing the table with an astral scalar would panic.
#[inline(always)]
fn char_lut_read(c: char) -> u16 {
    let cp = c as u32;
    if cp >= 65536 {
        0
    } else {
        CHAR_LUT[cp as usize]
    }
}

#[inline]
pub fn encode_u32(val: u32) -> [char; 4] {
    let v = val as u64;
    let bucket_id = OFFSETS.partition_point(|&off| off <= v) - 1;
    let b = &BUCKET_TABLE[bucket_id];
    let mut rem = v - b.offset;

    let i4 = (rem % b.radices[2]) as usize;
    rem /= b.radices[2];
    let i3 = (rem % b.radices[1]) as usize;
    rem /= b.radices[1];
    let i2 = (rem % b.radices[0]) as usize;
    let i1 = (rem / b.radices[0]) as usize;

    let a1 = &*CHARS_A1;
    let a2 = &*CHARS_A2;
    let a3 = &*CHARS_A3;
    let glyph = |w: u8, idx: usize| match w {
        1 => a1[idx],
        2 => a2[idx],
        _ => a3[idx],
    };
    [
        glyph(b.widths[0], i1),
        glyph(b.widths[1], i2),
        glyph(b.widths[2], i3),
        glyph(b.widths[3], i4),
    ]
}

#[inline]
pub fn decode_u32(q: &[char; 4]) -> Result<u32, &'static str> {
    let e1 = char_lut_read(q[0]);
    let e2 = char_lut_read(q[1]);
    let e3 = char_lut_read(q[2]);
    let e4 = char_lut_read(q[3]);

    // Each glyph must resolve on its own. A combined mask would let a single unknown glyph
    // through and underflow the `(entry >> 10) - 1` / `(entry & 0x3FF) - 1` extractions.
    if e1 == 0 || e2 == 0 || e3 == 0 || e4 == 0 {
        return Err("Invalid character in quartet");
    }

    // Non-zero entries always carry width 1..=3, so the subtractions below cannot underflow.
    let combo = (((e1 >> 10) - 1) as usize) * 27
        + (((e2 >> 10) - 1) as usize) * 9
        + (((e3 >> 10) - 1) as usize) * 3
        + (((e4 >> 10) - 1) as usize);

    let (off, s2, s3, s4) = COMBO_PARAMS[combo];
    if s2 == 0 {
        return Err("Invalid quartet width pattern");
    }

    let i1 = ((e1 & 0x3FF) - 1) as u64;
    let i2 = ((e2 & 0x3FF) - 1) as u64;
    let i3 = ((e3 & 0x3FF) - 1) as u64;
    let i4 = ((e4 & 0x3FF) - 1) as u64;

    let val = ((i1 * s2 + i2) * s3 + i3) * s4 + i4 + off;

    // Bucket 14 is truncated: `OFF_14 + BUCKET_14_CUTOFF == 2^32`, so any value at or above
    // 2^32 is a discarded residue. No other bucket can reach this, so no index check is needed.
    if val >= (1u64 << 32) {
        return Err("Quartet value exceeds bucket 14 cutoff");
    }

    Ok(val as u32)
}

/// Payloads at or above this size encode their Pages 2..N in parallel. Below it, dispatching
/// work to Rayon's pool costs more than it saves: a measured sweep put the crossover between
/// 16 KiB and 64 KiB on a 24-thread host.
const PARALLEL_ENCODE_THRESHOLD: usize = 64 * 1024;

/// Encode one headerless page body (up to 1,024 payload bytes) into exactly 1,024 characters,
/// padded with the Bucket 0 null quartet.
fn encode_page_body(bytes: &[u8]) -> String {
    let mut page = String::with_capacity(CHARS_PER_PAGE * 3);
    let mut quartets = 0usize;
    for chunk in bytes.chunks(4) {
        let mut buf = [0u8; 4];
        buf[..chunk.len()].copy_from_slice(chunk);
        for &ch in &encode_u32(u32::from_le_bytes(buf)) {
            page.push(ch);
        }
        quartets += 1;
    }
    let null = CHARS_A1[0];
    while quartets < QUARTETS_PER_PAGE {
        page.push(null);
        page.push(null);
        page.push(null);
        page.push(null);
        quartets += 1;
    }
    page
}

#[pyfunction]
pub fn encode_rust(input: &[u8]) -> String {
    let len_u32 = u32::try_from(input.len()).expect("Payload length exceeds u32::MAX");
    let total_data_quartets = input.len().div_ceil(4);

    let total_pages = if total_data_quartets <= DATA_QUARTETS_PAGE_1 {
        1
    } else {
        1 + (total_data_quartets - DATA_QUARTETS_PAGE_1).div_ceil(DATA_QUARTETS_SUBSEQUENT)
    };

    let null = CHARS_A1[0];
    let mut result = String::with_capacity(total_pages * CHARS_PER_PAGE * 3);

    // --- Page 1: global length header plus up to 1,020 payload bytes ---
    let p1_bytes = input.len().min(BYTES_PAGE_1);
    for &ch in &encode_u32(len_u32) {
        result.push(ch);
    }
    for chunk in input[..p1_bytes].chunks(4) {
        let mut buf = [0u8; 4];
        buf[..chunk.len()].copy_from_slice(chunk);
        for &ch in &encode_u32(u32::from_le_bytes(buf)) {
            result.push(ch);
        }
    }
    for _ in (1 + p1_bytes.div_ceil(4))..QUARTETS_PER_PAGE {
        result.push(null);
        result.push(null);
        result.push(null);
        result.push(null);
    }

    // --- Pages 2..N: independent page bodies ---
    let rest = &input[p1_bytes..];
    if !rest.is_empty() {
        let bodies: Vec<&[u8]> = rest.chunks(BYTES_SUBSEQUENT).collect();
        if input.len() >= PARALLEL_ENCODE_THRESHOLD {
            // Parallel path: pages are materialised first and concatenated afterwards, so peak
            // memory holds both the per-page strings and the assembled result.
            let pages: Vec<String> = bodies.par_iter().map(|b| encode_page_body(b)).collect();
            for page in &pages {
                result.push_str(page);
            }
        } else {
            for body in &bodies {
                result.push_str(&encode_page_body(body));
            }
        }
    }

    result
}

/// Decode `quartets_to_read` data quartets from a char iterator directly into `output`.
#[inline]
fn decode_quartets_into(
    char_iter: &mut impl Iterator<Item = char>,
    quartets_to_read: usize,
    output: &mut Vec<u8>,
) -> PyResult<()> {
    for _ in 0..quartets_to_read {
        let c0 = char_iter
            .next()
            .ok_or_else(|| PyValueError::new_err("Corrupt data quartet: incomplete"))?;
        let c1 = char_iter
            .next()
            .ok_or_else(|| PyValueError::new_err("Corrupt data quartet: incomplete"))?;
        let c2 = char_iter
            .next()
            .ok_or_else(|| PyValueError::new_err("Corrupt data quartet: incomplete"))?;
        let c3 = char_iter
            .next()
            .ok_or_else(|| PyValueError::new_err("Corrupt data quartet: incomplete"))?;
        let val = decode_u32(&[c0, c1, c2, c3])
            .map_err(|e| PyValueError::new_err(format!("Corrupt data quartet: {e}")))?;
        output.extend_from_slice(&val.to_le_bytes());
    }
    Ok(())
}

/// Skip padding quartets without decoding them.
#[inline]
fn skip_quartets(char_iter: &mut impl Iterator<Item = char>, quartets: usize) {
    for _ in 0..quartets * 4 {
        char_iter.next();
    }
}

#[pyfunction]
pub fn decode_rust(input: &str) -> PyResult<Vec<u8>> {
    let char_count = input.chars().count();
    if char_count == 0 {
        return Err(PyValueError::new_err("Input text is empty"));
    }
    if char_count < 4 || char_count % 4 != 0 {
        return Err(PyValueError::new_err(format!(
            "Input character count {} is not a multiple of 4",
            char_count
        )));
    }

    let mut char_iter = input.chars();

    // Decode Quartet 0 (chars 0..4)
    let c0 = char_iter.next().unwrap();
    let c1 = char_iter.next().unwrap();
    let c2 = char_iter.next().unwrap();
    let c3 = char_iter.next().unwrap();
    let len = decode_u32(&[c0, c1, c2, c3])
        .map_err(|e| PyValueError::new_err(format!("Corrupt header: {e}")))? as usize;

    if len == 0 {
        return Ok(Vec::new());
    }

    let total_data_quartets = len.div_ceil(4);
    let max_possible_quartets = (char_count - 4) / 4;
    let safe_capacity_quartets = total_data_quartets.min(max_possible_quartets);
    let mut output = Vec::with_capacity(safe_capacity_quartets * 4);

    // If formatted as pages (multiples of 1024 chars):
    if char_count >= CHARS_PER_PAGE && char_count % CHARS_PER_PAGE == 0 {
        let total_pages = char_count / CHARS_PER_PAGE;
        let mut data_quartets_read = 0;

        // Page 1
        let p1_needed = total_data_quartets.min(DATA_QUARTETS_PAGE_1);
        decode_quartets_into(&mut char_iter, p1_needed, &mut output)?;
        data_quartets_read += p1_needed;
        skip_quartets(&mut char_iter, DATA_QUARTETS_PAGE_1 - p1_needed);

        // Subsequent pages
        for _p in 1..total_pages {
            if data_quartets_read >= total_data_quartets {
                break;
            }
            let p_needed = (total_data_quartets - data_quartets_read).min(DATA_QUARTETS_SUBSEQUENT);
            decode_quartets_into(&mut char_iter, p_needed, &mut output)?;
            data_quartets_read += p_needed;
            skip_quartets(&mut char_iter, DATA_QUARTETS_SUBSEQUENT - p_needed);
        }

        if data_quartets_read < total_data_quartets {
            return Err(PyValueError::new_err(format!(
                "Payload requires {total_data_quartets} quartets, but only {data_quartets_read} read across pages"
            )));
        }
    } else {
        // Fallback for unpadded continuous streams
        let available_data_quartets = (char_count / 4) - 1;
        if available_data_quartets < total_data_quartets {
            return Err(PyValueError::new_err(format!(
                "Payload requires {total_data_quartets} quartets, but only {available_data_quartets} available"
            )));
        }
        decode_quartets_into(&mut char_iter, total_data_quartets, &mut output)?;
    }

    output.truncate(len);
    Ok(output)
}

#[pyfunction]
#[pyo3(name = "decode_u32")]
pub fn decode_u32_py(quartet: Vec<char>) -> PyResult<u32> {
    if quartet.len() != 4 {
        return Err(PyValueError::new_err(format!(
            "Quartet must have 4 characters, got {}",
            quartet.len()
        )));
    }
    let mut q = [' '; 4];
    q.copy_from_slice(&quartet);
    decode_u32(&q).map_err(PyValueError::new_err)
}

#[pyfunction]
#[pyo3(name = "encode_u32")]
pub fn encode_u32_py(val: u32) -> String {
    let q = encode_u32(val);
    q.into_iter().collect()
}

/// Native page-at-a-time encoder.
///
/// Mirrors the former pure-Python generator exactly: page 1 carries the global payload
/// length in Quartet 0 and holds 1,020 payload bytes, later pages hold 1,024 bytes each,
/// and every page is padded to 256 quartets. Iterating in Rust removes the per-quartet
/// PyO3 round trip that capped the Python loop at roughly 11 MB/s.
///
/// Holds an owned `Py<PyBytes>` (never a borrowed slice) so the payload stays alive for the
/// whole iteration; each page borrows only for the duration of a single `__next__`.
#[pyclass]
pub struct PageEncoder {
    data: Py<PyBytes>,
    total_len: usize,
    offset: usize,
    page_index: usize,
    total_pages: usize,
}

#[pymethods]
impl PageEncoder {
    #[new]
    fn new(py: Python<'_>, payload: Py<PyBytes>) -> PyResult<Self> {
        let total_len = payload.bind(py).as_bytes().len();
        u32::try_from(total_len)
            .map_err(|_| PyValueError::new_err("Payload length exceeds u32::MAX"))?;
        let total_pages = if total_len <= BYTES_PAGE_1 {
            1
        } else {
            1 + (total_len - BYTES_PAGE_1).div_ceil(BYTES_SUBSEQUENT)
        };
        Ok(Self {
            data: payload,
            total_len,
            offset: 0,
            page_index: 0,
            total_pages,
        })
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> Option<String> {
        if self.page_index >= self.total_pages {
            return None;
        }

        // Borrow the payload only for this page, while the GIL is held.
        let bytes = self.data.bind(py).as_bytes();

        let mut page = String::with_capacity(CHARS_PER_PAGE * 3);
        let mut quartets = 0usize;

        let (start, end) = if self.page_index == 0 {
            // Quartet 0 is the global length header.
            for &ch in &encode_u32(self.total_len as u32) {
                page.push(ch);
            }
            quartets = 1;
            (0usize, self.total_len.min(BYTES_PAGE_1))
        } else {
            (
                self.offset,
                (self.offset + BYTES_SUBSEQUENT).min(self.total_len),
            )
        };

        for chunk in bytes[start..end].chunks(4) {
            let mut buf = [0u8; 4];
            buf[..chunk.len()].copy_from_slice(chunk);
            for &ch in &encode_u32(u32::from_le_bytes(buf)) {
                page.push(ch);
            }
            quartets += 1;
        }

        // Every page is padded out to 256 quartets with the Bucket 0 null quartet.
        let null = CHARS_A1[0];
        while quartets < QUARTETS_PER_PAGE {
            page.push(null);
            page.push(null);
            page.push(null);
            page.push(null);
            quartets += 1;
        }

        self.offset = end;
        self.page_index += 1;
        Some(page)
    }
}

/// Native page-at-a-time decoder. Consumes an arbitrary iterable of 1,024-character pages
/// and yields one byte chunk per page, matching the former Python generator's framing rules
/// and error text exactly.
#[pyclass]
pub struct PageDecoder {
    iter: Py<PyAny>,
    remaining: usize,
    page_index: usize,
    done: bool,
}

#[pymethods]
impl PageDecoder {
    #[new]
    fn new(py: Python<'_>, pages: Py<PyAny>) -> PyResult<Self> {
        let iter: Py<PyAny> = pages.bind(py).try_iter()?.unbind().into();
        Ok(Self {
            iter,
            remaining: 0,
            page_index: 0,
            done: false,
        })
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyBytes>>> {
        if self.done {
            return Ok(None);
        }

        let page_obj = match self.iter.bind(py).call_method0("__next__") {
            Ok(v) => v,
            Err(e) if e.is_instance_of::<PyStopIteration>(py) => {
                if self.remaining > 0 {
                    return Err(PyValueError::new_err(format!(
                        "Truncated input: expected {} more bytes but no more pages provided",
                        self.remaining
                    )));
                }
                self.done = true;
                return Ok(None);
            }
            Err(e) => return Err(e),
        };

        let page_bound = page_obj.downcast::<PyString>()?;
        let page_str = page_bound.to_str()?;
        let char_count = page_str.chars().count();

        if char_count != CHARS_PER_PAGE {
            let which = if self.page_index == 0 {
                "Page 1"
            } else {
                "Page"
            };
            return Err(PyValueError::new_err(format!(
                "{which} has invalid length: {char_count} (must be {CHARS_PER_PAGE} characters)"
            )));
        }

        let mut char_iter = page_str.chars();

        let (bytes_needed, pad_quartets) = if self.page_index == 0 {
            let c0 = char_iter.next().unwrap();
            let c1 = char_iter.next().unwrap();
            let c2 = char_iter.next().unwrap();
            let c3 = char_iter.next().unwrap();
            let total_len = decode_u32(&[c0, c1, c2, c3])
                .map_err(|e| PyValueError::new_err(format!("Corrupt header: {e}")))?
                as usize;
            if total_len == 0 {
                self.done = true;
                return Ok(None);
            }
            self.remaining = total_len;
            let needed = total_len.min(BYTES_PAGE_1);
            let q_needed = needed.div_ceil(4);
            (needed, DATA_QUARTETS_PAGE_1 - q_needed)
        } else {
            let needed = self.remaining.min(BYTES_SUBSEQUENT);
            let q_needed = needed.div_ceil(4);
            (needed, DATA_QUARTETS_SUBSEQUENT - q_needed)
        };

        let q_needed = bytes_needed.div_ceil(4);
        let mut buf: Vec<u8> = Vec::with_capacity(q_needed * 4);
        decode_quartets_into(&mut char_iter, q_needed, &mut buf)?;
        skip_quartets(&mut char_iter, pad_quartets);
        buf.truncate(bytes_needed);

        self.remaining -= bytes_needed;
        self.page_index += 1;
        if self.remaining == 0 {
            self.done = true;
        }

        Ok(Some(PyBytes::new(py, &buf).unbind()))
    }
}

#[pymodule]
fn bookette(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decode_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decode_u32_py, m)?)?;
    m.add_function(wrap_pyfunction!(encode_u32_py, m)?)?;
    m.add_class::<PageEncoder>()?;
    m.add_class::<PageDecoder>()?;
    m.add("MAX_BYTES_PER_PAGE", MAX_BYTES_PER_PAGE)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vocab_sizes() {
        assert_eq!(CHARS_A1.len(), N1);
        assert_eq!(CHARS_A2.len(), N2);
        assert_eq!(CHARS_A3.len(), N3);
    }

    #[test]
    fn test_disjoint_alphabets() {
        use std::collections::HashSet;
        let s1: HashSet<char> = CHARS_A1.iter().copied().collect();
        let s2: HashSet<char> = CHARS_A2.iter().copied().collect();
        let s3: HashSet<char> = CHARS_A3.iter().copied().collect();
        assert!(
            s1.is_disjoint(&s2),
            "A1 and A2 overlap: {:?}",
            s1.intersection(&s2)
        );
        assert!(
            s1.is_disjoint(&s3),
            "A1 and A3 overlap: {:?}",
            s1.intersection(&s3)
        );
        assert!(
            s2.is_disjoint(&s3),
            "A2 and A3 overlap: {:?}",
            s2.intersection(&s3)
        );
    }

    #[test]
    fn test_u32_boundaries() {
        for &val in &[0u32, 1, 2, u32::MAX, u32::MAX - 1] {
            let q = encode_u32(val);
            let dec = decode_u32(&q).unwrap();
            assert_eq!(dec, val);
        }
    }

    #[test]
    fn test_page_boundaries_and_framing() {
        // Test 0 bytes
        let enc0 = encode_rust(b"");
        assert_eq!(enc0.chars().count(), 1024);
        assert_eq!(decode_rust(&enc0).unwrap(), b"");

        // Test 1020 bytes (exact Page 1)
        let p1020 = vec![42u8; 1020];
        let enc1020 = encode_rust(&p1020);
        assert_eq!(enc1020.chars().count(), 1024);
        assert_eq!(decode_rust(&enc1020).unwrap(), p1020);

        // Test 1021 bytes (spills to Page 2)
        let p1021 = vec![42u8; 1021];
        let enc1021 = encode_rust(&p1021);
        assert_eq!(enc1021.chars().count(), 2048);
        assert_eq!(decode_rust(&enc1021).unwrap(), p1021);

        // Test 2044 bytes (exact Page 1 + Page 2)
        let p2044 = vec![7u8; 2044];
        let enc2044 = encode_rust(&p2044);
        assert_eq!(enc2044.chars().count(), 2048);
        assert_eq!(decode_rust(&enc2044).unwrap(), p2044);

        // Test 2045 bytes (spills to Page 3)
        let p2045 = vec![99u8; 2045];
        let enc2045 = encode_rust(&p2045);
        assert_eq!(enc2045.chars().count(), 3072);
        assert_eq!(decode_rust(&enc2045).unwrap(), p2045);
    }

    #[test]
    fn test_untrusted_header_memory_bomb() {
        // Quartet 0 encoding u32::MAX (4,294,967,295 B)
        let max_header = encode_u32(u32::MAX);
        let input: String = max_header.iter().collect();
        // Passing only the 4-char header with an impossible 4GB length must return an error
        // cleanly and NOT crash with Out Of Memory.
        let result = decode_rust(&input);
        assert!(result.is_err());
    }

    #[test]
    fn test_malformed_glyphs_rejected() {
        // Unknown BMP, astral (beyond the 65536-entry table), and a control scalar.
        // Each must be rejected in every slot; a combined validity mask would let a single
        // unknown glyph through and underflow the width/index extraction.
        let bad_glyphs = ['\u{FFFF}', '\u{1F600}', '\u{0001}'];
        for &bad in &bad_glyphs {
            for slot in 0..4 {
                let mut q = encode_u32(12345);
                q[slot] = bad;
                assert!(
                    decode_u32(&q).is_err(),
                    "unknown glyph {bad:?} accepted at slot {slot}"
                );
            }
        }
    }

    #[test]
    fn test_truncated_streams_rejected() {
        let payload: Vec<u8> = (0..5000).map(|i| (i % 256) as u8).collect();
        let enc = encode_rust(&payload);
        let chars: Vec<char> = enc.chars().collect();
        assert!(decode_rust(&enc).is_ok(), "full stream must decode");

        // Header only: declares 5000 B but carries zero data quartets.
        let header_only: String = chars[..4].iter().collect();
        assert!(decode_rust(&header_only).is_err());

        // Half the declared data quartets.
        let half: String = chars[..4 + (chars.len() - 4) / 2].iter().collect();
        assert!(decode_rust(&half).is_err());

        // Shorter than a single quartet.
        let tiny: String = chars[..3].iter().collect();
        assert!(decode_rust(&tiny).is_err());
    }
    #[test]
    fn test_parallel_encode_path_matches_framing() {
        // Above PARALLEL_ENCODE_THRESHOLD, Pages 2..N are encoded with Rayon. The parallel path
        // must produce exactly the same text as the serial one.
        for &len in &[
            PARALLEL_ENCODE_THRESHOLD,
            PARALLEL_ENCODE_THRESHOLD + 1,
            200 * 1024,
        ] {
            let payload: Vec<u8> = (0..len).map(|i| (i % 256) as u8).collect();
            let enc = encode_rust(&payload);
            let chars = enc.chars().count();

            let data_quartets = len.div_ceil(4);
            let expected_pages = if data_quartets <= DATA_QUARTETS_PAGE_1 {
                1
            } else {
                1 + (data_quartets - DATA_QUARTETS_PAGE_1).div_ceil(DATA_QUARTETS_SUBSEQUENT)
            };
            assert_eq!(chars, expected_pages * CHARS_PER_PAGE, "framing at {len} B");
            assert_eq!(decode_rust(&enc).unwrap(), payload, "roundtrip at {len} B");
        }
    }

    /// Pins the invariant that makes `val >= 1 << 32` equivalent to the old explicit
    /// `BUCKET_14_CUTOFF` check in the table-driven decoder.
    #[test]
    fn test_bucket14_cutoff_is_the_32bit_boundary() {
        assert_eq!(BUCKET_TABLE[14].offset + BUCKET_14_CUTOFF, 1u64 << 32);
    }

    /// Exercises every bucket's first value and its predecessor, so a wrong stride, radix
    /// order, or swapped tuple in `COMBO_PARAMS` fails here instead of only on random input.
    #[test]
    fn test_every_bucket_boundary_roundtrips() {
        let mut values: Vec<u32> = Vec::new();
        for (id, bucket) in BUCKET_TABLE.iter().enumerate() {
            let start = bucket.offset;
            assert!(start < (1u64 << 32), "bucket {id} offset out of range");
            values.push(start as u32);
            if start > 0 {
                values.push((start - 1) as u32);
            }
        }
        // Bucket 14's truncated tail: the last accepted residue and the first rejected one.
        values.push(((1u64 << 32) - 1) as u32);

        for v in values {
            let q = encode_u32(v);
            assert_eq!(
                decode_u32(&q),
                Ok(v),
                "bucket boundary value {v} failed to round-trip"
            );
        }

        // Every `COMBO_PARAMS` slot is populated by exactly one bucket, and the 15 bucket ids
        // cover 15 distinct combos. A duplicate combo would silently shadow a bucket.
        let mut seen = [false; 81];
        for (id, bucket) in BUCKET_TABLE.iter().enumerate() {
            let w = bucket.widths;
            let combo = ((w[0] - 1) as usize) * 27
                + ((w[1] - 1) as usize) * 9
                + ((w[2] - 1) as usize) * 3
                + ((w[3] - 1) as usize);
            assert!(!seen[combo], "combo {combo} is claimed by two buckets");
            seen[combo] = true;
            assert_eq!(
                COMBO_PARAMS[combo],
                (
                    bucket.offset,
                    bucket.radices[0],
                    bucket.radices[1],
                    bucket.radices[2]
                ),
                "COMBO_PARAMS[{combo}] does not match bucket {id}"
            );
        }
        assert_eq!(seen.iter().filter(|&&s| s).count(), BUCKET_TABLE.len());
    }
}

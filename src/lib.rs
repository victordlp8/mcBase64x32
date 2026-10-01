use std::sync::LazyLock;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const WIDTH_1_CHARS: &str = include_str!("1_width.txt");
const WIDTH_2_CHARS: &str = include_str!("2_width.txt");
const WIDTH_3_CHARS: &str = include_str!("3_width.txt");

pub const N1: usize = 106;
pub const N2: usize = 211;
pub const N3: usize = 38;

const N1_U64: u64 = N1 as u64;
const N2_U64: u64 = N2 as u64;
const N3_U64: u64 = N3 as u64;

// Capacities of the 4 structural bucket shapes:
const CAP_1111: u64 = N1_U64 * N1_U64 * N1_U64 * N1_U64; // 126_247_696
const CAP_2111: u64 = N2_U64 * N1_U64 * N1_U64 * N1_U64; // 251_304_376
const CAP_3111: u64 = N3_U64 * N1_U64 * N1_U64 * N1_U64; // 45_258_608
const CAP_2211: u64 = N2_U64 * N2_U64 * N1_U64 * N1_U64; // 500_237_956

// Offsets derived continuously from bucket capacities:
const OFF_0: u64 = 0;
const OFF_1: u64 = OFF_0 + CAP_1111;
const OFF_2: u64 = OFF_1 + CAP_2111;
const OFF_3: u64 = OFF_2 + CAP_2111;
const OFF_4: u64 = OFF_3 + CAP_2111;
const OFF_5: u64 = OFF_4 + CAP_2111;
const OFF_6: u64 = OFF_5 + CAP_3111;
const OFF_7: u64 = OFF_6 + CAP_3111;
const OFF_8: u64 = OFF_7 + CAP_3111;
const OFF_9: u64 = OFF_8 + CAP_3111;
const OFF_10: u64 = OFF_9 + CAP_2211;
const OFF_11: u64 = OFF_10 + CAP_2211;
const OFF_12: u64 = OFF_11 + CAP_2211;
const OFF_13: u64 = OFF_12 + CAP_2211;
const OFF_14: u64 = OFF_13 + CAP_2211;

pub const BUCKET_14_CUTOFF: u64 = 481_277_884;

pub const MAX_BYTES_PER_PAGE: usize = 1024;
const QUARTETS_PER_PAGE: usize = 256;
const CHARS_PER_PAGE: usize = QUARTETS_PER_PAGE * 4; // 1024 characters per page
const DATA_QUARTETS_PAGE_1: usize = 255;            // 1020 bytes of payload on Page 1
const DATA_QUARTETS_SUBSEQUENT: usize = 256;        // 1024 bytes of payload on Pages 2..N

#[derive(Clone, Copy)]
pub struct BucketDef {
    pub id: u8,
    pub widths: [u8; 4],
    pub sizes: [u64; 4],
    pub capacity: u64,
    pub offset: u64,
}

pub const BUCKETS: [BucketDef; 15] = [
    BucketDef { id: 0,  widths: [1, 1, 1, 1], sizes: [N1_U64, N1_U64, N1_U64, N1_U64], capacity: CAP_1111, offset: OFF_0 },
    BucketDef { id: 1,  widths: [2, 1, 1, 1], sizes: [N2_U64, N1_U64, N1_U64, N1_U64], capacity: CAP_2111, offset: OFF_1 },
    BucketDef { id: 2,  widths: [1, 2, 1, 1], sizes: [N1_U64, N2_U64, N1_U64, N1_U64], capacity: CAP_2111, offset: OFF_2 },
    BucketDef { id: 3,  widths: [1, 1, 2, 1], sizes: [N1_U64, N1_U64, N2_U64, N1_U64], capacity: CAP_2111, offset: OFF_3 },
    BucketDef { id: 4,  widths: [1, 1, 1, 2], sizes: [N1_U64, N1_U64, N1_U64, N2_U64], capacity: CAP_2111, offset: OFF_4 },
    BucketDef { id: 5,  widths: [3, 1, 1, 1], sizes: [N3_U64, N1_U64, N1_U64, N1_U64], capacity: CAP_3111, offset: OFF_5 },
    BucketDef { id: 6,  widths: [1, 3, 1, 1], sizes: [N1_U64, N3_U64, N1_U64, N1_U64], capacity: CAP_3111, offset: OFF_6 },
    BucketDef { id: 7,  widths: [1, 1, 3, 1], sizes: [N1_U64, N1_U64, N3_U64, N1_U64], capacity: CAP_3111, offset: OFF_7 },
    BucketDef { id: 8,  widths: [1, 1, 1, 3], sizes: [N1_U64, N1_U64, N1_U64, N3_U64], capacity: CAP_3111, offset: OFF_8 },
    BucketDef { id: 9,  widths: [2, 2, 1, 1], sizes: [N2_U64, N2_U64, N1_U64, N1_U64], capacity: CAP_2211, offset: OFF_9 },
    BucketDef { id: 10, widths: [2, 1, 2, 1], sizes: [N2_U64, N1_U64, N2_U64, N1_U64], capacity: CAP_2211, offset: OFF_10 },
    BucketDef { id: 11, widths: [2, 1, 1, 2], sizes: [N2_U64, N1_U64, N1_U64, N2_U64], capacity: CAP_2211, offset: OFF_11 },
    BucketDef { id: 12, widths: [1, 2, 2, 1], sizes: [N1_U64, N2_U64, N2_U64, N1_U64], capacity: CAP_2211, offset: OFF_12 },
    BucketDef { id: 13, widths: [1, 2, 1, 2], sizes: [N1_U64, N2_U64, N1_U64, N2_U64], capacity: CAP_2211, offset: OFF_13 },
    BucketDef { id: 14, widths: [1, 1, 2, 2], sizes: [N1_U64, N1_U64, N2_U64, N2_U64], capacity: BUCKET_14_CUTOFF, offset: OFF_14 },
];

static CHARS_A1: LazyLock<Vec<char>> = LazyLock::new(|| WIDTH_1_CHARS.chars().collect());
static CHARS_A2: LazyLock<Vec<char>> = LazyLock::new(|| WIDTH_2_CHARS.chars().collect());
static CHARS_A3: LazyLock<Vec<char>> = LazyLock::new(|| WIDTH_3_CHARS.chars().collect());

static SORTED_CHARS: LazyLock<Vec<(char, u8, u16)>> = LazyLock::new(|| {
    let mut list = Vec::with_capacity(N1 + N2 + N3);
    for (i, &ch) in CHARS_A1.iter().enumerate() { list.push((ch, 1, i as u16)); }
    for (i, &ch) in CHARS_A2.iter().enumerate() { list.push((ch, 2, i as u16)); }
    for (i, &ch) in CHARS_A3.iter().enumerate() { list.push((ch, 3, i as u16)); }
    list.sort_unstable_by_key(|&(c, _, _)| c);
    list
});

#[inline(always)]
fn char_lookup(c: char) -> Option<(u8, usize)> {
    let table = &*SORTED_CHARS;
    match table.binary_search_by_key(&c, |&(ch, _, _)| ch) {
        Ok(idx) => {
            let (_, w, i) = table[idx];
            Some((w, i as usize))
        }
        Err(_) => None,
    }
}

/// Inlined mixed-radix decomposition using compile-time constants for reciprocal multiplication.
#[inline(always)]
fn decompose<const S2: u64, const S3: u64, const S4: u64>(mut rem: u64) -> (usize, usize, usize, usize) {
    let i4 = (rem % S4) as usize; rem /= S4;
    let i3 = (rem % S3) as usize; rem /= S3;
    let i2 = (rem % S2) as usize; rem /= S2;
    let i1 = rem as usize;
    (i1, i2, i3, i4)
}

/// Inlined mixed-radix recomposition using compile-time constants.
#[inline(always)]
fn recompose<const S2: u64, const S3: u64, const S4: u64>(i1: u64, i2: u64, i3: u64, i4: u64) -> u64 {
    ((i1 * S2 + i2) * S3 + i3) * S4 + i4
}

#[inline(always)]
pub fn encode_u32(val: u32) -> [char; 4] {
    let v = val as u64;
    let a1 = &*CHARS_A1;
    let a2 = &*CHARS_A2;
    let a3 = &*CHARS_A3;

    if v < OFF_5 {
        if v < OFF_1 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N1_U64, N1_U64>(v - OFF_0);
            [a1[i1], a1[i2], a1[i3], a1[i4]]
        } else if v < OFF_2 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N1_U64, N1_U64>(v - OFF_1);
            [a2[i1], a1[i2], a1[i3], a1[i4]]
        } else if v < OFF_3 {
            let (i1, i2, i3, i4) = decompose::<N2_U64, N1_U64, N1_U64>(v - OFF_2);
            [a1[i1], a2[i2], a1[i3], a1[i4]]
        } else if v < OFF_4 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N2_U64, N1_U64>(v - OFF_3);
            [a1[i1], a1[i2], a2[i3], a1[i4]]
        } else {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N1_U64, N2_U64>(v - OFF_4);
            [a1[i1], a1[i2], a1[i3], a2[i4]]
        }
    } else if v < OFF_9 {
        if v < OFF_6 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N1_U64, N1_U64>(v - OFF_5);
            [a3[i1], a1[i2], a1[i3], a1[i4]]
        } else if v < OFF_7 {
            let (i1, i2, i3, i4) = decompose::<N3_U64, N1_U64, N1_U64>(v - OFF_6);
            [a1[i1], a3[i2], a1[i3], a1[i4]]
        } else if v < OFF_8 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N3_U64, N1_U64>(v - OFF_7);
            [a1[i1], a1[i2], a3[i3], a1[i4]]
        } else {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N1_U64, N3_U64>(v - OFF_8);
            [a1[i1], a1[i2], a1[i3], a3[i4]]
        }
    } else {
        if v < OFF_10 {
            let (i1, i2, i3, i4) = decompose::<N2_U64, N1_U64, N1_U64>(v - OFF_9);
            [a2[i1], a2[i2], a1[i3], a1[i4]]
        } else if v < OFF_11 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N2_U64, N1_U64>(v - OFF_10);
            [a2[i1], a1[i2], a2[i3], a1[i4]]
        } else if v < OFF_12 {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N1_U64, N2_U64>(v - OFF_11);
            [a2[i1], a1[i2], a1[i3], a2[i4]]
        } else if v < OFF_13 {
            let (i1, i2, i3, i4) = decompose::<N2_U64, N2_U64, N1_U64>(v - OFF_12);
            [a1[i1], a2[i2], a2[i3], a1[i4]]
        } else if v < OFF_14 {
            let (i1, i2, i3, i4) = decompose::<N2_U64, N1_U64, N2_U64>(v - OFF_13);
            [a1[i1], a2[i2], a1[i3], a2[i4]]
        } else {
            let (i1, i2, i3, i4) = decompose::<N1_U64, N2_U64, N2_U64>(v - OFF_14);
            [a1[i1], a1[i2], a2[i3], a2[i4]]
        }
    }
}

#[inline(always)]
pub fn decode_u32(q: &[char; 4]) -> Result<u32, &'static str> {
    let (w1, i1) = char_lookup(q[0]).ok_or("Invalid character in quartet")?;
    let (w2, i2) = char_lookup(q[1]).ok_or("Invalid character in quartet")?;
    let (w3, i3) = char_lookup(q[2]).ok_or("Invalid character in quartet")?;
    let (w4, i4) = char_lookup(q[3]).ok_or("Invalid character in quartet")?;

    let i1 = i1 as u64;
    let i2 = i2 as u64;
    let i3 = i3 as u64;
    let i4 = i4 as u64;

    let (off, rem) = match (w1, w2, w3, w4) {
        (1, 1, 1, 1) => (OFF_0, recompose::<N1_U64, N1_U64, N1_U64>(i1, i2, i3, i4)),
        (2, 1, 1, 1) => (OFF_1, recompose::<N1_U64, N1_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 2, 1, 1) => (OFF_2, recompose::<N2_U64, N1_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 1, 2, 1) => (OFF_3, recompose::<N1_U64, N2_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 1, 1, 2) => (OFF_4, recompose::<N1_U64, N1_U64, N2_U64>(i1, i2, i3, i4)),
        (3, 1, 1, 1) => (OFF_5, recompose::<N1_U64, N1_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 3, 1, 1) => (OFF_6, recompose::<N3_U64, N1_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 1, 3, 1) => (OFF_7, recompose::<N1_U64, N3_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 1, 1, 3) => (OFF_8, recompose::<N1_U64, N1_U64, N3_U64>(i1, i2, i3, i4)),
        (2, 2, 1, 1) => (OFF_9, recompose::<N2_U64, N1_U64, N1_U64>(i1, i2, i3, i4)),
        (2, 1, 2, 1) => (OFF_10, recompose::<N1_U64, N2_U64, N1_U64>(i1, i2, i3, i4)),
        (2, 1, 1, 2) => (OFF_11, recompose::<N1_U64, N1_U64, N2_U64>(i1, i2, i3, i4)),
        (1, 2, 2, 1) => (OFF_12, recompose::<N2_U64, N2_U64, N1_U64>(i1, i2, i3, i4)),
        (1, 2, 1, 2) => (OFF_13, recompose::<N2_U64, N1_U64, N2_U64>(i1, i2, i3, i4)),
        (1, 1, 2, 2) => {
            let r = recompose::<N1_U64, N2_U64, N2_U64>(i1, i2, i3, i4);
            if r >= BUCKET_14_CUTOFF {
                return Err("Quartet value exceeds bucket 14 cutoff");
            }
            (OFF_14, r)
        }
        _ => return Err("Invalid quartet width pattern"),
    };

    Ok((off + rem) as u32)
}

#[pyfunction]
pub fn encode_rust(input: &[u8]) -> String {
    let len_u32 = u32::try_from(input.len()).expect("Payload length exceeds u32::MAX");
    let total_data_quartets = (input.len() + 3) / 4;

    let total_pages = if total_data_quartets <= DATA_QUARTETS_PAGE_1 {
        1
    } else {
        1 + (total_data_quartets - DATA_QUARTETS_PAGE_1 + DATA_QUARTETS_SUBSEQUENT - 1) / DATA_QUARTETS_SUBSEQUENT
    };

    let null_quartet = [CHARS_A1[0]; 4];
    let mut result = String::with_capacity(total_pages * CHARS_PER_PAGE * 3);

    let mut data_u32s = Vec::with_capacity(total_data_quartets);
    for chunk in input.chunks(4) {
        let mut buf = [0u8; 4];
        buf[..chunk.len()].copy_from_slice(chunk);
        data_u32s.push(u32::from_le_bytes(buf));
    }

    // --- Page 1 ---
    let header_q = encode_u32(len_u32);
    for &ch in &header_q {
        result.push(ch);
    }

    let p1_data_count = total_data_quartets.min(DATA_QUARTETS_PAGE_1);
    for i in 0..p1_data_count {
        let q = encode_u32(data_u32s[i]);
        for &ch in &q {
            result.push(ch);
        }
    }

    // Pad Page 1 to 256 quartets (1024 chars)
    for _ in (1 + p1_data_count)..QUARTETS_PER_PAGE {
        for &ch in &null_quartet {
            result.push(ch);
        }
    }

    // --- Subsequent Pages ---
    let mut offset = p1_data_count;
    for _ in 1..total_pages {
        let p_data_count = (total_data_quartets - offset).min(DATA_QUARTETS_SUBSEQUENT);
        for i in 0..p_data_count {
            let q = encode_u32(data_u32s[offset + i]);
            for &ch in &q {
                result.push(ch);
            }
        }
        for _ in p_data_count..QUARTETS_PER_PAGE {
            for &ch in &null_quartet {
                result.push(ch);
            }
        }
        offset += p_data_count;
    }

    result
}

#[pyfunction]
pub fn decode_rust(input: &str) -> PyResult<Vec<u8>> {
    let chars: Vec<char> = input.chars().collect();
    if chars.is_empty() {
        return Err(PyValueError::new_err("Input text is empty"));
    }
    if chars.len() < 4 || chars.len() % 4 != 0 {
        return Err(PyValueError::new_err(format!(
            "Input character count {} is not a multiple of 4",
            chars.len()
        )));
    }

    // Decode Quartet 0 (chars 0..4)
    let mut q0 = [' '; 4];
    q0.copy_from_slice(&chars[0..4]);
    let len = decode_u32(&q0)
        .map_err(|e| PyValueError::new_err(format!("Corrupt header: {e}")))? as usize;

    if len == 0 {
        return Ok(Vec::new());
    }

    // `len` comes from the untrusted header; `div_ceil` avoids the `len + 3` overflow
    // that `(len + 3) / 4` would hit on 32-bit targets for `u32::MAX`.
    let total_data_quartets = len.div_ceil(4);
    let max_possible_quartets = chars.len().saturating_sub(4) / 4;
    let safe_capacity_quartets = total_data_quartets.min(max_possible_quartets);
    let mut output = Vec::with_capacity(safe_capacity_quartets * 4);
    // If formatted as pages (multiples of 1024 chars):
    if chars.len() >= CHARS_PER_PAGE && chars.len() % CHARS_PER_PAGE == 0 {
        let total_pages = chars.len() / CHARS_PER_PAGE;
        let mut data_quartets_read = 0;

        // Page 1
        let p1_chars = &chars[0..CHARS_PER_PAGE];
        let p1_needed = total_data_quartets.min(DATA_QUARTETS_PAGE_1);
        for q_idx in 1..=p1_needed {
            let chunk = &p1_chars[q_idx * 4..(q_idx + 1) * 4];
            let mut q = [' '; 4];
            q.copy_from_slice(chunk);
            let val = decode_u32(&q)
                .map_err(|e| PyValueError::new_err(format!("Corrupt data quartet: {e}")))?;
            output.extend_from_slice(&val.to_le_bytes());
            data_quartets_read += 1;
        }

        // Subsequent pages
        for p in 1..total_pages {
            if data_quartets_read >= total_data_quartets {
                break;
            }
            let page_start = p * CHARS_PER_PAGE;
            let page_chars = &chars[page_start..page_start + CHARS_PER_PAGE];
            let p_needed = (total_data_quartets - data_quartets_read).min(DATA_QUARTETS_SUBSEQUENT);
            for q_idx in 0..p_needed {
                let chunk = &page_chars[q_idx * 4..(q_idx + 1) * 4];
                let mut q = [' '; 4];
                q.copy_from_slice(chunk);
                let val = decode_u32(&q)
                    .map_err(|e| PyValueError::new_err(format!("Corrupt data quartet: {e}")))?;
                output.extend_from_slice(&val.to_le_bytes());
                data_quartets_read += 1;
            }
        }

        if data_quartets_read < total_data_quartets {
            return Err(PyValueError::new_err(format!(
                "Payload requires {total_data_quartets} quartets, but only {data_quartets_read} read across pages"
            )));
        }
    } else {
        // Fallback for unpadded continuous streams
        let available_data_quartets = (chars.len() / 4) - 1;
        if available_data_quartets < total_data_quartets {
            return Err(PyValueError::new_err(format!(
                "Payload requires {total_data_quartets} quartets, but only {available_data_quartets} available"
            )));
        }
        for chunk in chars[4..4 + total_data_quartets * 4].chunks_exact(4) {
            let mut q = [' '; 4];
            q.copy_from_slice(chunk);
            let val = decode_u32(&q)
                .map_err(|e| PyValueError::new_err(format!("Corrupt data quartet: {e}")))?;
            output.extend_from_slice(&val.to_le_bytes());
        }
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
    decode_u32(&q).map_err(|e| PyValueError::new_err(e))
}

#[pyfunction]
#[pyo3(name = "encode_u32")]
pub fn encode_u32_py(val: u32) -> String {
    let q = encode_u32(val);
    q.into_iter().collect()
}

#[pymodule]
fn bookette(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decode_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decode_u32_py, m)?)?;
    m.add_function(wrap_pyfunction!(encode_u32_py, m)?)?;
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
        assert!(s1.is_disjoint(&s2), "A1 and A2 overlap: {:?}", s1.intersection(&s2));
        assert!(s1.is_disjoint(&s3), "A1 and A3 overlap: {:?}", s1.intersection(&s3));
        assert!(s2.is_disjoint(&s3), "A2 and A3 overlap: {:?}", s2.intersection(&s3));
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
}

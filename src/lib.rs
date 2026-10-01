use std::sync::LazyLock;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const WIDTH_1_CHARS: &str = include_str!("1_width.txt");
const WIDTH_2_CHARS: &str = include_str!("2_width.txt");
const WIDTH_3_CHARS: &str = include_str!("3_width.txt");

const N1: usize = 106;
const N2: usize = 211;
const N3: usize = 38;

const BUCKET_14_CUTOFF: u64 = 481_277_884;

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
    BucketDef { id: 0,  widths: [1, 1, 1, 1], sizes: [106, 106, 106, 106], capacity: 126_247_696, offset: 0 },
    BucketDef { id: 1,  widths: [2, 1, 1, 1], sizes: [211, 106, 106, 106], capacity: 251_304_376, offset: 126_247_696 },
    BucketDef { id: 2,  widths: [1, 2, 1, 1], sizes: [106, 211, 106, 106], capacity: 251_304_376, offset: 377_552_072 },
    BucketDef { id: 3,  widths: [1, 1, 2, 1], sizes: [106, 106, 211, 106], capacity: 251_304_376, offset: 628_856_448 },
    BucketDef { id: 4,  widths: [1, 1, 1, 2], sizes: [106, 106, 106, 211], capacity: 251_304_376, offset: 880_160_824 },
    BucketDef { id: 5,  widths: [3, 1, 1, 1], sizes: [38,  106, 106, 106], capacity: 45_258_608,  offset: 1_131_465_200 },
    BucketDef { id: 6,  widths: [1, 3, 1, 1], sizes: [106, 38,  106, 106], capacity: 45_258_608,  offset: 1_176_723_808 },
    BucketDef { id: 7,  widths: [1, 1, 3, 1], sizes: [106, 106, 38,  106], capacity: 45_258_608,  offset: 1_221_982_416 },
    BucketDef { id: 8,  widths: [1, 1, 1, 3], sizes: [106, 106, 106, 38 ], capacity: 45_258_608,  offset: 1_267_241_024 },
    BucketDef { id: 9,  widths: [2, 2, 1, 1], sizes: [211, 211, 106, 106], capacity: 500_237_956, offset: 1_312_499_632 },
    BucketDef { id: 10, widths: [2, 1, 2, 1], sizes: [211, 106, 211, 106], capacity: 500_237_956, offset: 1_812_737_588 },
    BucketDef { id: 11, widths: [2, 1, 1, 2], sizes: [211, 106, 106, 211], capacity: 500_237_956, offset: 2_312_975_544 },
    BucketDef { id: 12, widths: [1, 2, 2, 1], sizes: [106, 211, 211, 106], capacity: 500_237_956, offset: 2_813_213_500 },
    BucketDef { id: 13, widths: [1, 2, 1, 2], sizes: [106, 211, 106, 211], capacity: 500_237_956, offset: 3_313_451_456 },
    BucketDef { id: 14, widths: [1, 1, 2, 2], sizes: [106, 106, 211, 211], capacity: 481_277_884, offset: 3_813_689_412 },
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

const OFF_0: u64 = 0;
const OFF_1: u64 = 126_247_696;
const OFF_2: u64 = 377_552_072;
const OFF_3: u64 = 628_856_448;
const OFF_4: u64 = 880_160_824;
const OFF_5: u64 = 1_131_465_200;
const OFF_6: u64 = 1_176_723_808;
const OFF_7: u64 = 1_221_982_416;
const OFF_8: u64 = 1_267_241_024;
const OFF_9: u64 = 1_312_499_632;
const OFF_10: u64 = 1_812_737_588;
const OFF_11: u64 = 2_312_975_544;
const OFF_12: u64 = 2_813_213_500;
const OFF_13: u64 = 3_313_451_456;
const OFF_14: u64 = 3_813_689_412;

#[inline(always)]
pub fn encode_u32(val: u32) -> [char; 4] {
    let v = val as u64;
    let a1 = &*CHARS_A1;
    let a2 = &*CHARS_A2;
    let a3 = &*CHARS_A3;

    if v < OFF_5 {
        if v < OFF_1 {
            let mut rem = v - OFF_0;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a1[i1], a1[i2], a1[i3], a1[i4]]
        } else if v < OFF_2 {
            let mut rem = v - OFF_1;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a2[i1], a1[i2], a1[i3], a1[i4]]
        } else if v < OFF_3 {
            let mut rem = v - OFF_2;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 211) as usize; rem /= 211;
            let i1 = rem as usize;
            [a1[i1], a2[i2], a1[i3], a1[i4]]
        } else if v < OFF_4 {
            let mut rem = v - OFF_3;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 211) as usize; rem /= 211;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a1[i1], a1[i2], a2[i3], a1[i4]]
        } else {
            let mut rem = v - OFF_4;
            let i4 = (rem % 211) as usize; rem /= 211;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a1[i1], a1[i2], a1[i3], a2[i4]]
        }
    } else if v < OFF_9 {
        if v < OFF_6 {
            let mut rem = v - OFF_5;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a3[i1], a1[i2], a1[i3], a1[i4]]
        } else if v < OFF_7 {
            let mut rem = v - OFF_6;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 38) as usize; rem /= 38;
            let i1 = rem as usize;
            [a1[i1], a3[i2], a1[i3], a1[i4]]
        } else if v < OFF_8 {
            let mut rem = v - OFF_7;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 38) as usize; rem /= 38;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a1[i1], a1[i2], a3[i3], a1[i4]]
        } else {
            let mut rem = v - OFF_8;
            let i4 = (rem % 38) as usize; rem /= 38;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a1[i1], a1[i2], a1[i3], a3[i4]]
        }
    } else {
        if v < OFF_10 {
            let mut rem = v - OFF_9;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 211) as usize; rem /= 211;
            let i1 = rem as usize;
            [a2[i1], a2[i2], a1[i3], a1[i4]]
        } else if v < OFF_11 {
            let mut rem = v - OFF_10;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 211) as usize; rem /= 211;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a2[i1], a1[i2], a2[i3], a1[i4]]
        } else if v < OFF_12 {
            let mut rem = v - OFF_11;
            let i4 = (rem % 211) as usize; rem /= 211;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
            [a2[i1], a1[i2], a1[i3], a2[i4]]
        } else if v < OFF_13 {
            let mut rem = v - OFF_12;
            let i4 = (rem % 106) as usize; rem /= 106;
            let i3 = (rem % 211) as usize; rem /= 211;
            let i2 = (rem % 211) as usize; rem /= 211;
            let i1 = rem as usize;
            [a1[i1], a2[i2], a2[i3], a1[i4]]
        } else if v < OFF_14 {
            let mut rem = v - OFF_13;
            let i4 = (rem % 211) as usize; rem /= 211;
            let i3 = (rem % 106) as usize; rem /= 106;
            let i2 = (rem % 211) as usize; rem /= 211;
            let i1 = rem as usize;
            [a1[i1], a2[i2], a1[i3], a2[i4]]
        } else {
            let mut rem = v - OFF_14;
            let i4 = (rem % 211) as usize; rem /= 211;
            let i3 = (rem % 211) as usize; rem /= 211;
            let i2 = (rem % 106) as usize; rem /= 106;
            let i1 = rem as usize;
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
        (1, 1, 1, 1) => (OFF_0, ((i1 * 106 + i2) * 106 + i3) * 106 + i4),
        (2, 1, 1, 1) => (OFF_1, ((i1 * 106 + i2) * 106 + i3) * 106 + i4),
        (1, 2, 1, 1) => (OFF_2, ((i1 * 211 + i2) * 106 + i3) * 106 + i4),
        (1, 1, 2, 1) => (OFF_3, ((i1 * 106 + i2) * 211 + i3) * 106 + i4),
        (1, 1, 1, 2) => (OFF_4, ((i1 * 106 + i2) * 106 + i3) * 211 + i4),
        (3, 1, 1, 1) => (OFF_5, ((i1 * 106 + i2) * 106 + i3) * 106 + i4),
        (1, 3, 1, 1) => (OFF_6, ((i1 * 38  + i2) * 106 + i3) * 106 + i4),
        (1, 1, 3, 1) => (OFF_7, ((i1 * 106 + i2) * 38  + i3) * 106 + i4),
        (1, 1, 1, 3) => (OFF_8, ((i1 * 106 + i2) * 106 + i3) * 38  + i4),
        (2, 2, 1, 1) => (OFF_9, ((i1 * 211 + i2) * 106 + i3) * 106 + i4),
        (2, 1, 2, 1) => (OFF_10, ((i1 * 106 + i2) * 211 + i3) * 106 + i4),
        (2, 1, 1, 2) => (OFF_11, ((i1 * 106 + i2) * 106 + i3) * 211 + i4),
        (1, 2, 2, 1) => (OFF_12, ((i1 * 211 + i2) * 211 + i3) * 106 + i4),
        (1, 2, 1, 2) => (OFF_13, ((i1 * 211 + i2) * 106 + i3) * 211 + i4),
        (1, 1, 2, 2) => {
            let r = ((i1 * 106 + i2) * 211 + i3) * 211 + i4;
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

    let total_data_quartets = (len + 3) / 4;
    let mut output = Vec::with_capacity(total_data_quartets * 4);

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
}

//! mdsip **read-only** client — the device data plane (FYL-DESIGN-06).
//!
//! MDSplus servers speak `mdsip`: a 48-byte header followed by a flat
//! payload, one request/one answer per message.  That is the whole protocol
//! for reading, and this module implements it from scratch so that fetching a
//! shot no longer requires a site-installed MDSplus (the Python package is
//! not on PyPI; `python/fylite/mds.py` imports it lazily for exactly that
//! reason).  Nothing here links against MDSplus and nothing here parses TDI.
//!
//! ## Read-only by construction, not by convention
//!
//! An mdsip connection is, in general, a **remote TDI evaluation** face: the
//! payload of a request is an expression string, and the server evaluates it.
//! A spike against a live server confirmed the obvious consequence —
//! `getenv("HOME")` answers.  So this client never lets a caller supply an
//! expression: [`Client::request`] is private, the public surface is
//! [`Client::open_tree`] / [`Client::get`] / [`Client::get_dim_of`], and each
//! builds its own expression from arguments that must first pass
//! [`is_node_path`] / [`is_tree_name`].  A path carrying `(`, a comma, a
//! quote or whitespace is refused here, before a byte reaches the wire.
//!
//! This is deliberately stricter than what the protocol permits.  Widening it
//! is a design decision, not a convenience: see FYL-DESIGN-06 §5.
//!
//! ## Byte order and the dimension order trap
//!
//! The login message declares `client_type = 0x80|0x40|0x3` (the "JAVA"
//! client), which makes the server serialise **big-endian** in both
//! directions — so the codec is fixed-endian and identical on every host.
//!
//! ★The dims in an answer come back **fastest-varying first**: `SILOPT`, which
//! NumPy sees as shape `(106, 35)`, answers `dims = [35, 106]` — while the
//! payload bytes are in the very same order NumPy reads.  Treating `dims` as
//! a row-major shape therefore transposes the array *without any error*.
//! [`Answer::shape_row_major`] exists so that a consumer never has to
//! remember this.
//!
//! ## Layering
//!
//! The codec ([`build_request`], [`parse_answer`]) is transport-free and
//! `wasm32`-clean: a browser build could drive it over a WebSocket by
//! implementing [`Transport`] in JS glue.  Only the [`tcp`] submodule uses
//! `std::net`, and it is compiled out on `wasm32` where no socket exists.

use std::fmt;

/// Every mdsip message — request and answer alike — starts with 48 bytes.
pub const HEADER_LEN: usize = 48;

/// `client_type` advertised at login: big-endian, IEEE floats.  The server
/// converts to it, which is why this codec has no byte-order branches.
const CLIENT_TYPE_BIG_ENDIAN: u8 = 0x80 | 0x40 | 0x03;

/// mdsip dtype codes (a subset: the ones a measurement tree actually holds).
const DTYPE_U8: u8 = 2;
const DTYPE_U16: u8 = 3;
const DTYPE_U32: u8 = 4;
const DTYPE_I8: u8 = 6;
const DTYPE_I16: u8 = 7;
const DTYPE_I32: u8 = 8;
/// ★Unsigned 64-bit.  It arrives for exactly one thing on these trees: an
/// nci VMS timestamp (100 ns ticks since 1858-11-17, ~5.3e16).
const DTYPE_U64: u8 = 5;
const DTYPE_I64: u8 = 9;
const DTYPE_F32: u8 = 10;
const DTYPE_F64: u8 = 11;
const DTYPE_CSTRING: u8 = 14;

/// Refuse to allocate for an answer larger than this (a corrupt or hostile
/// length field must not turn into a multi-gigabyte allocation).  An entire
/// EAST shot's magnetics is ~100 KB, so this is four orders of magnitude of
/// headroom.
const MAX_ANSWER_BYTES: usize = 256 << 20;

/// Longest accepted node path / tree name — a guard on the same principle.
const MAX_ARG_LEN: usize = 256;

// --------------------------------------------------------------------------
// errors
// --------------------------------------------------------------------------

#[derive(Debug)]
pub enum MdsipError {
    /// The socket (or whatever transport is plugged in) failed.
    Transport(String),
    /// Bytes arrived, but they are not a message this codec can read.
    Protocol(String),
    /// An argument did not pass the read-only guard — nothing was sent.
    Refused(String),
    /// The server answered with a failure status (MDSplus/VMS convention:
    /// odd = success).
    Server { status: i32, text: String },
    /// A dtype outside the supported subset; the raw payload is not decoded
    /// rather than guessed at.
    Unsupported { dtype: u8 },
}

impl fmt::Display for MdsipError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            MdsipError::Transport(m) => write!(f, "mdsip transport: {m}"),
            MdsipError::Protocol(m) => write!(f, "mdsip protocol: {m}"),
            MdsipError::Refused(m) => write!(f, "mdsip refused (read-only client): {m}"),
            MdsipError::Server { status, text } => {
                if text.is_empty() {
                    write!(f, "mdsip server status {status}")
                } else {
                    write!(f, "mdsip server status {status}: {text}")
                }
            }
            MdsipError::Unsupported { dtype } => write!(f, "mdsip dtype {dtype} not supported"),
        }
    }
}

impl std::error::Error for MdsipError {}

// --------------------------------------------------------------------------
// answers
// --------------------------------------------------------------------------

/// A decoded payload.  One variant per supported dtype — the array keeps the
/// server's own type rather than being widened on arrival, so a caller that
/// wants exact integers still has them.
#[derive(Debug, Clone, PartialEq)]
pub enum Data {
    Text(String),
    U8(Vec<u8>),
    U16(Vec<u16>),
    U32(Vec<u32>),
    U64(Vec<u64>),
    I8(Vec<i8>),
    I16(Vec<i16>),
    I32(Vec<i32>),
    I64(Vec<i64>),
    F32(Vec<f32>),
    F64(Vec<f64>),
}

impl Data {
    /// Number of elements (characters, for text).
    pub fn len(&self) -> usize {
        match self {
            Data::Text(s) => s.len(),
            Data::U8(v) => v.len(),
            Data::U16(v) => v.len(),
            Data::U32(v) => v.len(),
            Data::U64(v) => v.len(),
            Data::I8(v) => v.len(),
            Data::I16(v) => v.len(),
            Data::I32(v) => v.len(),
            Data::I64(v) => v.len(),
            Data::F32(v) => v.len(),
            Data::F64(v) => v.len(),
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Numeric payload as `f64`, in the server's own element order.
    ///
    /// `None` for text.  `i64` beyond 2^53 and `u32`/`u64` extremes lose
    /// exactness here exactly as they would in any float conversion — a
    /// caller needing the integers should match on the variant instead.
    pub fn to_f64(&self) -> Option<Vec<f64>> {
        Some(match self {
            Data::Text(_) => return None,
            Data::U8(v) => v.iter().map(|&x| x as f64).collect(),
            Data::U16(v) => v.iter().map(|&x| x as f64).collect(),
            Data::U32(v) => v.iter().map(|&x| x as f64).collect(),
            //: ★an nci timestamp is above 2^53: `to_f64` is lossy for it by
            //: construction, and a caller that needs the exact tick count
            //: matches on the variant (`inserted_ms` does).
            Data::U64(v) => v.iter().map(|&x| x as f64).collect(),
            Data::I8(v) => v.iter().map(|&x| x as f64).collect(),
            Data::I16(v) => v.iter().map(|&x| x as f64).collect(),
            Data::I32(v) => v.iter().map(|&x| x as f64).collect(),
            Data::I64(v) => v.iter().map(|&x| x as f64).collect(),
            Data::F32(v) => v.iter().map(|&x| x as f64).collect(),
            Data::F64(v) => v.clone(),
        })
    }

    /// The single element of a scalar payload, as `f64`.
    pub fn scalar(&self) -> Option<f64> {
        match self.to_f64() {
            Some(v) if v.len() == 1 => Some(v[0]),
            _ => None,
        }
    }
}

/// One decoded answer message.
#[derive(Debug, Clone, PartialEq)]
pub struct Answer {
    /// MDSplus/VMS status word: **odd means success**.
    pub status: i32,
    pub dtype: u8,
    /// Dimensions **as the wire gives them: fastest-varying axis first**.
    /// See [`Answer::shape_row_major`] before indexing with these.
    pub dims: Vec<usize>,
    /// The header's element length.  ★It is the only thing that separates a
    /// text answer's ELEMENTS: `getnci(...,"NODE_NAME")` over nine nids comes
    /// back as one blob of nine right-padded records, and without this width
    /// the names cannot be told apart.
    pub elem_len: usize,
    pub data: Data,
}

impl Answer {
    /// `true` when the status word is odd (the MDSplus success convention).
    pub fn is_success(&self) -> bool {
        self.status & 1 == 1
    }

    /// [`Answer::dims`] reversed — i.e. the shape under which the payload is
    /// contiguous row-major, which is the shape NumPy reports for the same
    /// node.  Use this, not `dims`, whenever the result is going to be
    /// indexed as a matrix.
    pub fn shape_row_major(&self) -> Vec<usize> {
        self.dims.iter().rev().copied().collect()
    }

    /// Total element count implied by the dimensions (1 for a scalar).
    pub fn count(&self) -> usize {
        self.dims.iter().product::<usize>().max(1)
    }
}

// --------------------------------------------------------------------------
// codec
// --------------------------------------------------------------------------

fn put_u32(buf: &mut [u8], at: usize, v: u32) {
    buf[at..at + 4].copy_from_slice(&v.to_be_bytes());
}

fn get_i32(buf: &[u8], at: usize) -> i32 {
    i32::from_be_bytes([buf[at], buf[at + 1], buf[at + 2], buf[at + 3]])
}

fn get_u32(buf: &[u8], at: usize) -> u32 {
    u32::from_be_bytes([buf[at], buf[at + 1], buf[at + 2], buf[at + 3]])
}

/// Serialise one request: a header plus the expression text as its payload.
///
/// `msg_id` is echoed by the server; this client is strictly synchronous
/// (one request, one answer) so it uses it only as a sanity marker.
pub fn build_request(text: &str, msg_id: u8) -> Vec<u8> {
    let payload = text.as_bytes();
    let mut buf = vec![0u8; HEADER_LEN + payload.len()];
    put_u32(&mut buf, 0, (HEADER_LEN + payload.len()) as u32);
    put_u32(&mut buf, 4, 0); // status: zero on the way out
    buf[8..10].copy_from_slice(&(payload.len() as u16).to_be_bytes());
    buf[10] = 1; // nargs
    buf[11] = 0; // descriptor index
    buf[12] = msg_id;
    buf[13] = DTYPE_CSTRING;
    buf[14] = CLIENT_TYPE_BIG_ENDIAN;
    buf[15] = 0; // ndims — the expression is a scalar string
    // dims (8 x i32) stay zero
    buf[HEADER_LEN..].copy_from_slice(payload);
    buf
}

/// Length declared by a message header, for framing a stream.
///
/// Returns `None` until at least 4 bytes are available.
pub fn declared_len(bytes: &[u8]) -> Option<usize> {
    if bytes.len() < 4 {
        return None;
    }
    Some(get_u32(bytes, 0) as usize)
}

/// Decode one complete message.
pub fn parse_answer(msg: &[u8]) -> Result<Answer, MdsipError> {
    if msg.len() < HEADER_LEN {
        return Err(MdsipError::Protocol(format!(
            "short message: {} bytes, header is {HEADER_LEN}",
            msg.len()
        )));
    }
    let declared = get_u32(msg, 0) as usize;
    if declared != msg.len() {
        return Err(MdsipError::Protocol(format!(
            "length field {declared} != {} bytes received",
            msg.len()
        )));
    }
    let status = get_i32(msg, 4);
    let elem_len = u16::from_be_bytes([msg[8], msg[9]]) as usize;
    let dtype = msg[13];
    let ndims = msg[15] as usize;
    if ndims > 8 {
        return Err(MdsipError::Protocol(format!("ndims {ndims} > 8")));
    }
    let mut dims = Vec::with_capacity(ndims);
    for i in 0..ndims {
        dims.push(get_u32(msg, 16 + 4 * i) as usize);
    }
    let count = dims.iter().product::<usize>().max(1);
    let body = &msg[HEADER_LEN..];

    if dtype == DTYPE_CSTRING {
        // Text answers are the server's own words — an error string, a node
        // name — so they are kept verbatim rather than validated as UTF-8.
        //
        //: ★★AND NOT TRIMMED HERE.  A fixed-width record list is padded on
        //: purpose and the padding is what marks the element boundaries;
        //: trimming the blob before it is split loses them.  Trimming is the
        //: job of whatever reads one element — `text_of` / `split_elements`.
        let text = String::from_utf8_lossy(body).to_string();
        return Ok(Answer { status, dtype, dims, elem_len, data: Data::Text(text) });
    }

    //: ★★An answer with NO PAYLOAD is normal, not a decode failure: the login
    //: acknowledgement carries `dtype = 0` and zero bytes, and so does a node
    //: that exists and holds nothing.  Only a payload of an unknown dtype is
    //: an error — guessing at its width is how a silent misread would start.
    //:
    //: ★★★Measured, and it is why this rule is here at all: without it the
    //: FIRST message of every session — the login answer — fails to decode,
    //: so this client could not complete a handshake against a real server.
    //: The JS client beside it (`app/server/mdsip.mjs`) carries the same rule
    //: and has always talked to EAST; this one had never been pointed at a
    //: live server until `fylite-app` grew a request face (2026-08-31).
    if body.is_empty() {
        return Ok(Answer { status, dtype, dims, elem_len, data: Data::F64(Vec::new()) });
    }

    let width = match dtype {
        DTYPE_U8 | DTYPE_I8 => 1,
        DTYPE_U16 | DTYPE_I16 => 2,
        DTYPE_U32 | DTYPE_I32 | DTYPE_F32 => 4,
        DTYPE_U64 | DTYPE_I64 | DTYPE_F64 => 8,
        _ => return Err(MdsipError::Unsupported { dtype }),
    };
    let want = count * width;
    if body.len() < want {
        return Err(MdsipError::Protocol(format!(
            "dtype {dtype} needs {want} payload bytes for {count} elements \
             (dims {dims:?}, element length {elem_len}), got {}",
            body.len()
        )));
    }
    let at = |i: usize| &body[i * width..(i + 1) * width];
    let data = match dtype {
        DTYPE_U8 => Data::U8(body[..count].to_vec()),
        DTYPE_I8 => Data::I8(body[..count].iter().map(|&b| b as i8).collect()),
        DTYPE_U16 => Data::U16(
            (0..count).map(|i| u16::from_be_bytes([at(i)[0], at(i)[1]])).collect(),
        ),
        DTYPE_I16 => Data::I16(
            (0..count).map(|i| i16::from_be_bytes([at(i)[0], at(i)[1]])).collect(),
        ),
        DTYPE_U32 => Data::U32((0..count).map(|i| get_u32(body, i * 4)).collect()),
        DTYPE_I32 => Data::I32((0..count).map(|i| get_i32(body, i * 4)).collect()),
        DTYPE_F32 => Data::F32(
            (0..count).map(|i| f32::from_be_bytes(at(i).try_into().unwrap())).collect(),
        ),
        DTYPE_U64 => Data::U64(
            (0..count).map(|i| u64::from_be_bytes(at(i).try_into().unwrap())).collect(),
        ),
        DTYPE_I64 => Data::I64(
            (0..count).map(|i| i64::from_be_bytes(at(i).try_into().unwrap())).collect(),
        ),
        DTYPE_F64 => Data::F64(
            (0..count).map(|i| f64::from_be_bytes(at(i).try_into().unwrap())).collect(),
        ),
        _ => unreachable!("width table and decode table agree"),
    };
    Ok(Answer { status, dtype, dims, elem_len, data })
}

// --------------------------------------------------------------------------
// the read-only guard
// --------------------------------------------------------------------------

/// Accept only what can name a node, never what can compute.
///
/// What a binding asks of a node.  The three verbs the EAST A-Box uses, and
/// the only three: measured over its 485 bindings — 291 `DATA`, 145 `DIM_OF`,
/// 46 bare, 1 literal constant (`tools/abox-mds-bind.py`).
///
/// ★It is an ENUM and not a string for the reason the whole module exists:
/// a string reaching this layer would be a TDI fragment, and this client
/// deliberately takes none (see the module preamble, FYL-DESIGN-06 §5).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Verb {
    /// The node itself — `\FOO`.
    Raw,
    /// `data(\FOO)` — the signal's values, detached from its dimensions.
    Data,
    /// `dim_of(\FOO)` — its time base.
    DimOf,
}

/// The WIRE codes for [`Verb`], and the `*` sentinel — the contract between
/// the A-Box binding table (which spells a verb as a string) and
/// `fylite_rs_mds_read` (which takes an integer).
///
/// ★★Declared here and GENERATED into both hosts by `rust/build.sh`, for the
/// reason `fyo.rs` gives for every other table like it: a mapping two sides
/// keep in step by hand is not one contract.  `zerod`'s parameter order was
/// spelled in three places and reordering any one of them asked, silently, for
/// another discharge.  Three verbs is small enough to feel safe to transcribe,
/// which is exactly why it would be.
///
/// @mds-request
pub const REQUEST_VERBS: [(&str, i32); 3] =
    [("raw", 0), ("data", 1), ("dim_of", 2)];

/// `*` in a subscript, as `fylite_rs_mds_read` takes it.  @mds-request
pub const REQUEST_ALL: i64 = i64::MIN;

/// One subscript position: a fixed index, or the whole axis.
///
/// ★There is no third variant, and that is the boundary.  A bound that reads
/// ANOTHER node — the A-Box has two, `BDRY[0, 0:NBDRY[{t}]-1, {t}]` — cannot
/// become an `Index` until that node has been read, so it is two round trips
/// and the caller makes them.  Admitting an expression here to save the second
/// trip would hand this layer a parser, which is what it does not have.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Index {
    At(i64),
    All,
}

/// Assemble the TDI text for one binding — **from a validated node path and
/// integers, never from a caller's string**.
///
/// ★This is the whole of what the A-Box binding table decomposes to
/// (`{verb, node, subscript, inside}`), and it is a free function so that the
/// assembly can be judged without a server: the shapes below are the ones the
/// EAST bindings actually take, and a change to any of them is a change to
/// what every host asks for.
///
/// `inside` says which side of the verb the subscript sits on —
/// `data(\X)[0,*]` (111 bindings) versus `data(\X[0,*])` (16).  ★They are not
/// the same expression in TDI (the first subscripts the VALUE, the second the
/// signal before `data` takes it), so the placement travels in the table
/// rather than being normalised away.
pub fn tdi(verb: Verb, node: &str, sub: &[Index], inside: bool)
           -> Result<String, MdsipError> {
    if !is_node_path(node) {
        return Err(MdsipError::Refused(format!("node path {node:?}")));
    }
    let subs = if sub.is_empty() {
        String::new()
    } else {
        let items: Vec<String> = sub.iter().map(|i| match i {
            Index::At(n) => n.to_string(),
            Index::All => "*".to_string(),
        }).collect();
        format!("[{}]", items.join(","))
    };
    let name = match verb {
        Verb::Raw => return Ok(format!("{node}{subs}")),
        Verb::Data => "data",
        Verb::DimOf => "dim_of",
    };
    Ok(if inside && !subs.is_empty() {
        format!("{name}({node}{subs})")
    } else {
        format!("{name}({node}){subs}")
    })
}

/// Permitted: letters, digits, `_`, `$`, and the path punctuation `\ . : -`
/// (a leading `\` for a tag or fully-qualified path, `::TOP` for the tree
/// top, `.` for members, `:` for nodes).  Everything that makes TDI a
/// language — parentheses, commas, quotes, operators, whitespace, `;` — is
/// refused.
pub fn is_node_path(s: &str) -> bool {
    if s.is_empty() || s.len() > MAX_ARG_LEN {
        return false;
    }
    s.chars().all(|c| {
        c.is_ascii_alphanumeric() || matches!(c, '_' | '$' | '\\' | '.' | ':' | '-')
    })
}

/// Tree names are plainer still: letters, digits, `_`.
pub fn is_tree_name(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= MAX_ARG_LEN
        && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

// --------------------------------------------------------------------------
// transport + client
// --------------------------------------------------------------------------

/// A byte pipe to an mdsip server.
///
/// Kept abstract so the codec above stays usable where `std::net` does not
/// exist: on `wasm32` the same [`Client`] can be driven by a JS-supplied
/// WebSocket through an implementation of this trait.
pub trait Transport {
    fn send(&mut self, bytes: &[u8]) -> Result<(), MdsipError>;
    /// Read **at least one** byte into `buf`; return how many.  `Ok(0)` means
    /// the peer closed.
    fn recv(&mut self, buf: &mut [u8]) -> Result<usize, MdsipError>;
}

/// A synchronous, read-only mdsip session.
///
/// There is deliberately no method taking an expression: see the module
/// preamble.
pub struct Client<T: Transport> {
    io: T,
    msg_id: u8,
    /// Bytes received but not yet consumed by a message.
    spill: Vec<u8>,
}

impl<T: Transport> Client<T> {
    /// Perform the mdsip login handshake over an already-connected transport.
    ///
    /// The username is what the server matches against its `mdsip.hosts`
    /// map; mdsip carries no password (strong authentication exists only in
    /// the GSI/SSH transports), so a rejected login typically shows up as a
    /// closed connection rather than a status — both are reported here.
    pub fn login(io: T, user: &str) -> Result<Self, MdsipError> {
        if !is_tree_name(user) {
            return Err(MdsipError::Refused(format!("username {user:?}")));
        }
        let mut c = Client { io, msg_id: 1, spill: Vec::new() };
        c.io.send(&build_request(user, 1))?;
        let ans = c.read_message()?;
        if !ans.is_success() {
            return Err(MdsipError::Server {
                status: ans.status,
                text: match &ans.data {
                    Data::Text(_) => text_of(&ans),
                    _ => String::from("login rejected"),
                },
            });
        }
        Ok(c)
    }

    /// `TreeOpen(tree, shot)`.  Returns the server's status word.
    pub fn open_tree(&mut self, tree: &str, shot: i64) -> Result<i32, MdsipError> {
        if !is_tree_name(tree) {
            return Err(MdsipError::Refused(format!("tree name {tree:?}")));
        }
        // Built here, from a validated name and an integer — the caller never
        // supplies expression text.
        let ans = self.request(&format!("TreeOpen(\"{tree}\",{shot})"))?;
        let status = ans.data.scalar().map(|v| v as i32).unwrap_or(ans.status);
        if status & 1 == 0 {
            return Err(MdsipError::Server {
                status,
                text: format!("cannot open {tree} shot {shot}"),
            });
        }
        Ok(status)
    }

    /// Read one node by path.
    pub fn get(&mut self, node: &str) -> Result<Answer, MdsipError> {
        if !is_node_path(node) {
            return Err(MdsipError::Refused(format!("node path {node:?}")));
        }
        self.checked(node.to_string())
    }

    /// Read a node's dimension (time base) — `dim_of(node)`.
    ///
    /// The wrapper is applied here rather than accepted from the caller, so
    /// that "a function call is allowed" never becomes "any function call is
    /// allowed".
    pub fn get_dim_of(&mut self, node: &str) -> Result<Answer, MdsipError> {
        if !is_node_path(node) {
            return Err(MdsipError::Refused(format!("node path {node:?}")));
        }
        self.checked(format!("dim_of({node})"))
    }

    /// Read one A-Box binding: `[verb](node)[subscript]`.
    ///
    /// ★The single entry point the binding table drives, and the reason the
    /// table can exist at all — every piece it carries (`verb`, a node path,
    /// integers) is a piece THIS layer already assembles from, so admitting
    /// the table costs the client no new grammar.  See [`tdi`].
    pub fn read(&mut self, verb: Verb, node: &str, sub: &[Index], inside: bool)
                -> Result<Answer, MdsipError> {
        let expr = tdi(verb, node, sub, inside)?;
        self.checked(expr)
    }

    fn checked(&mut self, expr: String) -> Result<Answer, MdsipError> {
        let ans = self.request(&expr)?;
        if !ans.is_success() {
            return Err(MdsipError::Server {
                status: ans.status,
                text: match &ans.data {
                    Data::Text(_) => text_of(&ans),
                    _ => expr,
                },
            });
        }
        Ok(ans)
    }

    /// `current_shot(tree)` — the shot number the tree is writing now.
    pub fn current_shot(&mut self, tree: &str) -> Result<i64, MdsipError> {
        if !is_tree_name(tree) {
            return Err(MdsipError::Refused(format!("tree name {tree:?}")));
        }
        let ans = self.checked(format!("current_shot(\"{tree}\")"))?;
        ans.data
            .scalar()
            .map(|v| v as i64)
            .ok_or_else(|| MdsipError::Protocol(format!(
                "current_shot(\"{tree}\") did not answer a number"
            )))
    }

    /// `size(data(node))` — how many samples the node holds.
    pub fn size(&mut self, node: &str) -> Result<i64, MdsipError> {
        let p = self.path(node)?;
        let ans = self.checked(format!("size(data({p}))"))?;
        Ok(ans.data.scalar().unwrap_or(0.0) as i64)
    }

    /// `units_of(node)`.
    pub fn units_of(&mut self, node: &str) -> Result<String, MdsipError> {
        let p = self.path(node)?;
        Ok(text_of(&self.checked(format!("units_of({p})"))?))
    }

    /// `units_of(dim_of(node))` — composed here, never accepted from a caller.
    pub fn dim_units_of(&mut self, node: &str) -> Result<String, MdsipError> {
        let p = self.path(node)?;
        Ok(text_of(&self.checked(format!("units_of(dim_of({p}))"))?))
    }

    /// A strided slice of the samples, taken SERVER-SIDE.
    ///
    /// ★This is why decimation does not belong in whatever sits in front of
    /// this client: one EAST POINT chord is millions of samples, and a page
    /// drawing 1 500 pixels of it has no use for the rest.
    pub fn slice(&mut self, node: &str, start: i64, stop: i64, step: i64)
                 -> Result<Answer, MdsipError> {
        let p = self.path(node)?;
        check_slice(start, stop, step)?;
        self.checked(format!("data({p})[{start}:{stop}:{step}]"))
    }

    /// The same slice of the node's time base.
    pub fn dim_slice(&mut self, node: &str, start: i64, stop: i64, step: i64)
                     -> Result<Answer, MdsipError> {
        let p = self.path(node)?;
        check_slice(start, stop, step)?;
        self.checked(format!("dim_of({p})[{start}:{stop}:{step}]"))
    }

    /// `getnci(node,"TIME_INSERTED")` as milliseconds since the Unix epoch,
    /// or `None` when the node was never written.
    ///
    /// ★NOT "the shot time": it is when THAT node's record was stored, which
    /// for a raw channel is minutes after the plasma and for a re-analysed
    /// result can be days.  The VMS epoch is 1858-11-17 and the tick 100 ns.
    pub fn inserted_ms(&mut self, node: &str) -> Result<Option<i64>, MdsipError> {
        let p = self.path(node)?;
        let ans = self.checked(format!("getnci({p},\"TIME_INSERTED\")"))?;
        let ticks = match &ans.data {
            //: ★★`TIME_INSERTED` arrives as U64 and is ~5.3e16 — above 2^53,
            //: so it must be read from the integer variant, not through
            //: `to_f64`.  Reading it as a float silently rounds the
            //: millisecond away; reading it with no U64 branch at all
            //: (as this client did until 2026-08-31) reports "never written"
            //: for every node, which looks like an answer.
            Data::U64(v) if !v.is_empty() => v[0] as i64,
            Data::I64(v) if !v.is_empty() => v[0],
            Data::U32(v) if !v.is_empty() => v[0] as i64,
            Data::I32(v) if !v.is_empty() => v[0] as i64,
            _ => return Ok(None),
        };
        if ticks == 0 {
            return Ok(None);
        }
        Ok(Some(ticks / 10_000 - 3_506_716_800_000))
    }

    /// One level below `path`: the names (or another nci field) of its
    /// children or its members.
    ///
    /// ★`getnci` is composed HERE from a validated path and a field drawn
    /// from a fixed table — the caller passes `"children"`/`"members"` and a
    /// field key, never text.  A level with nothing in it answers
    /// `%TREE-W-NNF`, which is an empty list and not an error.
    pub fn list_nodes(&mut self, path: &str, kind: &str, field: &str)
                      -> Result<Vec<String>, MdsipError> {
        let p = self.path(path)?;
        let nids = match kind {
            "children" => "CHILDREN_NIDS",
            "members" => "MEMBER_NIDS",
            _ => return Err(MdsipError::Refused(format!("node kind {kind:?}"))),
        };
        let attr = match field {
            "name" => "NODE_NAME",
            "path" => "FULLPATH",
            "usage" => "USAGE_STR",
            "length" => "LENGTH",
            _ => return Err(MdsipError::Refused(format!("nci field {field:?}"))),
        };
        match self.checked(format!("getnci(getnci({p},\"{nids}\"),\"{attr}\")")) {
            Ok(ans) => Ok(split_elements(&ans)),
            Err(MdsipError::Server { text, .. })
                if text.contains("NNF")
                    || text.contains("NO_MORE")
                    || text.to_ascii_uppercase().contains("NODE NOT FOUND") =>
            {
                Ok(Vec::new())
            }
            Err(e) => Err(e),
        }
    }

    fn path(&self, node: &str) -> Result<String, MdsipError> {
        if !is_node_path(node) {
            return Err(MdsipError::Refused(format!("node path {node:?}")));
        }
        Ok(node.to_string())
    }

    /// The only place an expression reaches the wire — **private on purpose**.
    fn request(&mut self, text: &str) -> Result<Answer, MdsipError> {
        self.msg_id = self.msg_id.wrapping_add(1);
        self.io.send(&build_request(text, self.msg_id))?;
        self.read_message()
    }

    /// Pull exactly one framed message off the transport.
    fn read_message(&mut self) -> Result<Answer, MdsipError> {
        let mut chunk = [0u8; 64 * 1024];
        loop {
            if let Some(total) = declared_len(&self.spill) {
                if total < HEADER_LEN || total > MAX_ANSWER_BYTES {
                    return Err(MdsipError::Protocol(format!(
                        "implausible message length {total}"
                    )));
                }
                if self.spill.len() >= total {
                    let rest = self.spill.split_off(total);
                    let msg = std::mem::replace(&mut self.spill, rest);
                    return parse_answer(&msg);
                }
            }
            let n = self.io.recv(&mut chunk)?;
            if n == 0 {
                return Err(MdsipError::Transport(String::from(
                    "connection closed by peer (rejected login, or the \
                     server dropped the session)",
                )));
            }
            self.spill.extend_from_slice(&chunk[..n]);
        }
    }
}

fn check_slice(start: i64, stop: i64, step: i64) -> Result<(), MdsipError> {
    if start < 0 || stop < start || step < 1 {
        return Err(MdsipError::Refused(format!("slice [{start}:{stop}:{step}]")));
    }
    Ok(())
}

/// The text of an answer, trimmed of the padding a fixed-width record carries.
pub fn text_of(ans: &Answer) -> String {
    match &ans.data {
        Data::Text(t) => t.trim_end_matches(|c: char| c == '\0' || c.is_whitespace()).to_string(),
        _ => String::new(),
    }
}

/// Split a fixed-width text answer into its elements.
///
/// ★An nci name list comes back as ONE blob of `n` records each `len/n` bytes
/// wide, right-padded.  Splitting it by the declared element count is the only
/// way to get the names apart — reading it as one string yields
/// `"AL_TRIG   B_PORT ..."`, which looks like data and is not.
fn split_elements(ans: &Answer) -> Vec<String> {
    match &ans.data {
        Data::Text(t) => {
            //: ★the width is the HEADER's, falling back to an even division
            //: by the element count — the same rule the JS client uses.
            let w = if ans.elem_len > 0 && t.len() > ans.elem_len {
                ans.elem_len
            } else {
                let n = ans.count();
                if n <= 1 || t.len() % n != 0 {
                    return vec![text_of(ans)];
                }
                t.len() / n
            };
            let n = t.len() / w;
            (0..n)
                .map(|i| {
                    t[i * w..(i + 1) * w]
                        .trim_end_matches(|c: char| c == '\0' || c.is_whitespace())
                        .to_string()
                })
                .collect()
        }
        other => other
            .to_f64()
            .unwrap_or_default()
            .iter()
            .map(|v| {
                if v.fract() == 0.0 {
                    format!("{}", *v as i64)
                } else {
                    format!("{v}")
                }
            })
            .collect(),
    }
}

/// TCP transport — the native half.  Absent on `wasm32`, which has no socket
/// to open; there the codec is driven by a host-supplied [`Transport`].
#[cfg(not(target_arch = "wasm32"))]
pub mod tcp {
    use super::{Client, MdsipError, Transport};
    use std::io::{Read, Write};
    use std::net::{TcpStream, ToSocketAddrs};
    use std::time::Duration;

    /// The IANA-registered mdsip port, and what every MDSplus site uses
    /// unless it says otherwise.
    pub const DEFAULT_PORT: u16 = 8000;

    pub struct TcpTransport(TcpStream);

    impl TcpTransport {
        pub fn connect(host: &str, port: u16, timeout: Option<Duration>) -> Result<Self, MdsipError> {
            let addr = (host, port)
                .to_socket_addrs()
                .map_err(|e| MdsipError::Transport(format!("resolve {host}:{port}: {e}")))?
                .next()
                .ok_or_else(|| MdsipError::Transport(format!("no address for {host}:{port}")))?;
            let sock = match timeout {
                Some(t) => TcpStream::connect_timeout(&addr, t),
                None => TcpStream::connect(addr),
            }
            .map_err(|e| MdsipError::Transport(format!("connect {host}:{port}: {e}")))?;
            // A data server that stops answering must not hang a run
            // forever; the default is generous next to a ~2 ms fetch.
            let rw = timeout.unwrap_or_else(|| Duration::from_secs(30));
            let _ = sock.set_read_timeout(Some(rw));
            let _ = sock.set_write_timeout(Some(rw));
            let _ = sock.set_nodelay(true);
            Ok(TcpTransport(sock))
        }
    }

    impl Transport for TcpTransport {
        fn send(&mut self, bytes: &[u8]) -> Result<(), MdsipError> {
            self.0
                .write_all(bytes)
                .map_err(|e| MdsipError::Transport(format!("write: {e}")))
        }

        fn recv(&mut self, buf: &mut [u8]) -> Result<usize, MdsipError> {
            self.0
                .read(buf)
                .map_err(|e| MdsipError::Transport(format!("read: {e}")))
        }
    }

    /// Connect and log in: `host` may carry `:port`, matching the
    /// `KEFIT_MDS_SERVER` convention the Python layer already uses.
    pub fn connect(host: &str, user: &str) -> Result<Client<TcpTransport>, MdsipError> {
        let (h, p) = match host.rsplit_once(':') {
            Some((h, p)) => (
                h,
                p.parse::<u16>()
                    .map_err(|_| MdsipError::Transport(format!("bad port in {host:?}")))?,
            ),
            None => (host, DEFAULT_PORT),
        };
        Client::login(TcpTransport::connect(h, p, Some(Duration::from_secs(30)))?, user)
    }
}

// --------------------------------------------------------------------------
// tests
// --------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_answer_with_no_payload_decodes_instead_of_failing() {
        //: ★★★THE LOGIN ACKNOWLEDGEMENT IS THIS MESSAGE.  It carries
        //: `dtype = 0` and zero bytes, so a decoder that consults its width
        //: table first rejects the FIRST message of every session — which is
        //: exactly what this client did until `fylite-app` was pointed at
        //: EAST's server through a tunnel (2026-08-31) and could not log in.
        //: A node that exists and holds nothing answers the same shape.
        let ans = parse_answer(&answer_bytes(1, 0, &[], &[]))
            .expect("an empty payload is not a decode failure");
        assert!(ans.is_success());
        assert_eq!(ans.dtype, 0);
        assert!(ans.data.is_empty());
    }

    #[test]
    fn a_fixed_width_text_answer_splits_into_its_elements() {
        //: `getnci(...,"NODE_NAME")` over three nids answers ONE blob of
        //: three right-padded records.  Read as one string it looks like data
        //: and is not — and the padding is what marks the boundaries, so the
        //: blob must not be trimmed before it is split.
        let ans = parse_answer(&answer_bytes(1, DTYPE_CSTRING, &[3], b"AAA BB  C   ")).unwrap();
        assert_eq!(split_elements(&ans), vec!["AAA", "BB", "C"]);
        //: one element still reads as one trimmed string
        let one = parse_answer(&answer_bytes(1, DTYPE_CSTRING, &[], b"Wb/rad  ")).unwrap();
        assert_eq!(text_of(&one), "Wb/rad");
    }

    #[test]
    fn request_header_is_the_documented_48_bytes() {
        let m = build_request("hello", 7);
        assert_eq!(m.len(), HEADER_LEN + 5);
        assert_eq!(get_u32(&m, 0) as usize, m.len());
        assert_eq!(get_i32(&m, 4), 0);
        assert_eq!(u16::from_be_bytes([m[8], m[9]]), 5);
        assert_eq!(m[10], 1); // nargs
        assert_eq!(m[12], 7); // message id
        assert_eq!(m[13], DTYPE_CSTRING);
        assert_eq!(m[14], CLIENT_TYPE_BIG_ENDIAN);
        assert_eq!(m[15], 0); // ndims
        assert_eq!(&m[HEADER_LEN..], b"hello");
    }

    /// Build an answer the way a server would, to exercise the decoder.
    fn answer_bytes(status: i32, dtype: u8, dims: &[u32], payload: &[u8]) -> Vec<u8> {
        let mut m = vec![0u8; HEADER_LEN + payload.len()];
        put_u32(&mut m, 0, (HEADER_LEN + payload.len()) as u32);
        m[4..8].copy_from_slice(&status.to_be_bytes());
        m[13] = dtype;
        m[15] = dims.len() as u8;
        for (i, d) in dims.iter().enumerate() {
            put_u32(&mut m, 16 + 4 * i, *d);
        }
        m[HEADER_LEN..].copy_from_slice(payload);
        m
    }

    #[test]
    fn decodes_f64_and_keeps_the_wire_dimension_order() {
        // Two "channels" x three "samples" as the wire presents it.
        let vals = [1.0f64, 2.0, 3.0, 4.0, 5.0, 6.0];
        let mut payload = Vec::new();
        for v in vals {
            payload.extend_from_slice(&v.to_be_bytes());
        }
        let a = parse_answer(&answer_bytes(1, DTYPE_F64, &[2, 3], &payload)).unwrap();
        assert!(a.is_success());
        assert_eq!(a.dims, vec![2, 3]);
        // ★the trap: the row-major shape is the REVERSE of the wire dims.
        assert_eq!(a.shape_row_major(), vec![3, 2]);
        assert_eq!(a.count(), 6);
        assert_eq!(a.data, Data::F64(vals.to_vec()));
    }

    #[test]
    fn decodes_scalar_int_and_text() {
        let a = parse_answer(&answer_bytes(1, DTYPE_I32, &[], &265389633i32.to_be_bytes())).unwrap();
        assert_eq!(a.data.scalar(), Some(265389633.0));
        //: ★text arrives VERBATIM, padding included.  〔This assertion read
        //: `"%TREE-E-NOT_OPEN"` until 2026-08-31, when the padding turned out
        //: to be load-bearing: a fixed-width record list is separated by it,
        //: and trimming the blob at decode time loses the boundaries.
        //: Trimming is `text_of`'s job, and the messages a caller sees are
        //: trimmed there.〕
        let t = parse_answer(&answer_bytes(1, DTYPE_CSTRING, &[], b"%TREE-E-NOT_OPEN  ")).unwrap();
        assert_eq!(t.data, Data::Text(String::from("%TREE-E-NOT_OPEN  ")));
        assert_eq!(text_of(&t), "%TREE-E-NOT_OPEN");
    }

    #[test]
    fn rejects_malformed_frames() {
        assert!(matches!(parse_answer(&[0u8; 10]), Err(MdsipError::Protocol(_))));
        let m = answer_bytes(1, DTYPE_F64, &[4], &[0u8; 8]); // claims 4, carries 1
        assert!(matches!(parse_answer(&m), Err(MdsipError::Protocol(_))));
        //: ★★An unknown dtype refuses — but the example has to carry BYTES.
        //: 〔This assertion used an EMPTY payload until 2026-08-31, and that
        //: made it assert the opposite of what mdsip does: the login
        //: acknowledgement is `dtype = 0` with no payload, so "unknown dtype
        //: always refuses" rejected the first message of every session and
        //: this client could not log in to a real server.  What refuses is an
        //: unknown dtype whose width would have to be GUESSED — see
        //: `an_answer_with_no_payload_decodes_instead_of_failing`.〕
        assert!(matches!(
            parse_answer(&answer_bytes(1, 99, &[1], &[0u8; 8])),
            Err(MdsipError::Unsupported { dtype: 99 })
        ));
    }

    #[test]
    fn status_word_follows_the_odd_is_success_convention() {
        assert!(parse_answer(&answer_bytes(265389633, DTYPE_I32, &[], &[0; 4]))
            .unwrap()
            .is_success());
        assert!(!parse_answer(&answer_bytes(265389632, DTYPE_I32, &[], &[0; 4]))
            .unwrap()
            .is_success());
    }

    #[test]
    fn the_read_only_guard_refuses_everything_that_can_compute() {
        for ok in [
            r"\EFIT_EAST::TOP.MEASUREMENTS:SILOPT",
            r"\TE_CORETS",
            "MEASUREMENTS:PLASMA",
            r"\IP_MEAS-1",
        ] {
            assert!(is_node_path(ok), "should accept {ok}");
        }
        for bad in [
            "getenv(\"HOME\")",
            "spawn('rm -rf /')",
            r"\A , \B",
            "TreeOpen(\"x\",1)",
            "2+3",
            r"\A;\B",
            "",
        ] {
            assert!(!is_node_path(bad), "should refuse {bad}");
        }
        assert!(!is_node_path(&"x".repeat(MAX_ARG_LEN + 1)));
        assert!(is_tree_name("efit_east"));
        assert!(!is_tree_name("efit east"));
        assert!(!is_tree_name(r"efit\east"));
    }

    /// A transport that replays canned answers, so the client's framing and
    /// its guards are testable without a server.
    struct Replay {
        sent: Vec<Vec<u8>>,
        answers: Vec<Vec<u8>>,
        /// Deliver this many bytes per `recv`, to exercise reassembly.
        chunk: usize,
        cursor: Vec<u8>,
    }

    impl Transport for Replay {
        fn send(&mut self, bytes: &[u8]) -> Result<(), MdsipError> {
            self.sent.push(bytes.to_vec());
            self.cursor = self.answers.remove(0);
            Ok(())
        }
        fn recv(&mut self, buf: &mut [u8]) -> Result<usize, MdsipError> {
            let n = self.chunk.min(self.cursor.len()).min(buf.len());
            buf[..n].copy_from_slice(&self.cursor[..n]);
            self.cursor.drain(..n);
            Ok(n)
        }
    }

    fn replay(answers: Vec<Vec<u8>>, chunk: usize) -> Replay {
        Replay { sent: Vec::new(), answers, chunk, cursor: Vec::new() }
    }

    #[test]
    fn reassembles_a_message_split_across_reads() {
        let payload: Vec<u8> = (0..106u32)
            .flat_map(|i| (i as f64).to_be_bytes())
            .collect();
        let ok = answer_bytes(1, DTYPE_I32, &[], &1i32.to_be_bytes());
        let big = answer_bytes(1, DTYPE_F64, &[106], &payload);
        // 7 bytes per read: the header itself arrives in pieces.
        let mut c = Client::login(replay(vec![ok.clone(), ok, big], 7), "salmon").unwrap();
        c.open_tree("efit_east", 70754).unwrap();
        let a = c.get(r"\EFIT_EAST::TOP.RESULTS.GEQDSK:GTIME").unwrap();
        assert_eq!(a.dims, vec![106]);
        assert_eq!(a.data.to_f64().unwrap()[105], 105.0);
        // and the expression that went out is the path, nothing more
        assert_eq!(
            String::from_utf8_lossy(&c.io.sent[2][HEADER_LEN..]),
            r"\EFIT_EAST::TOP.RESULTS.GEQDSK:GTIME"
        );
        assert_eq!(
            String::from_utf8_lossy(&c.io.sent[1][HEADER_LEN..]),
            "TreeOpen(\"efit_east\",70754)"
        );
    }

    #[test]
    fn a_refused_argument_never_reaches_the_wire() {
        let ok = answer_bytes(1, DTYPE_I32, &[], &1i32.to_be_bytes());
        let mut c = Client::login(replay(vec![ok], 4096), "salmon").unwrap();
        let before = c.io.sent.len();
        assert!(matches!(c.get("getenv(\"HOME\")"), Err(MdsipError::Refused(_))));
        assert!(matches!(c.get_dim_of("spawn('id')"), Err(MdsipError::Refused(_))));
        assert!(matches!(c.open_tree("efit east", 1), Err(MdsipError::Refused(_))));
        assert_eq!(c.io.sent.len(), before, "nothing was sent");
    }

    #[test]
    fn dim_of_is_built_here_not_accepted_from_the_caller() {
        let ok = answer_bytes(1, DTYPE_I32, &[], &1i32.to_be_bytes());
        let ans = answer_bytes(1, DTYPE_F64, &[1], &1.5f64.to_be_bytes());
        let mut c = Client::login(replay(vec![ok, ans], 4096), "salmon").unwrap();
        c.get_dim_of(r"\TI0_TXCS").unwrap();
        assert_eq!(
            String::from_utf8_lossy(&c.io.sent[1][HEADER_LEN..]),
            r"dim_of(\TI0_TXCS)"
        );
    }

    /// Live oracle against a real MDSplus server.  Skipped unless
    /// `FYLITE_MDSIP_SERVER` is set (`host[:port]`), because a unit-test run
    /// must not depend on a data system being up:
    ///
    /// ```text
    /// efit_east_path=$HOME/workspace/machine_desc/east_mdsplus/efit_east \
    ///   mdsip -m -p 18000 -h mdsip.hosts -c 0 &
    /// FYLITE_MDSIP_SERVER=127.0.0.1:18000 FYLITE_MDSIP_USER=$USER cargo test mdsip
    /// ```
    ///
    /// The reference numbers are what the official MDSplus Python client
    /// reads from the same tree — this is the bit-for-bit gate on the codec.
    #[test]
    fn live_read_matches_the_official_client() {
        let Ok(server) = std::env::var("FYLITE_MDSIP_SERVER") else {
            eprintln!("skipped: set FYLITE_MDSIP_SERVER=host[:port] to run");
            return;
        };
        let user = std::env::var("FYLITE_MDSIP_USER").unwrap_or_else(|_| String::from("nobody"));
        let mut c = tcp::connect(&server, &user).expect("login");
        c.open_tree("efit_east", 70754).expect("TreeOpen");

        let a = c.get(r"\EFIT_EAST::TOP.MEASUREMENTS:SILOPT").expect("SILOPT");
        assert_eq!(a.dtype, DTYPE_F64);
        assert_eq!(a.dims, vec![35, 106], "wire order: fastest axis first");
        assert_eq!(a.shape_row_major(), vec![106, 35], "what NumPy reports");
        let v = a.data.to_f64().unwrap();
        assert_eq!(v.len(), 35 * 106);
        // MDSplus python: tree.getNode(...).getData().data()[50][:3]
        for (i, want) in [0.262_136_417_340_736_8_f64, 0.270_743_245_986_599_93, 0.267_546_179_982_815_77]
            .iter()
            .enumerate()
        {
            assert_eq!(v[50 * 35 + i], *want, "SILOPT[50][{i}] must be bit-identical");
        }

        let gt = c.get(r"\EFIT_EAST::TOP.RESULTS.GEQDSK:GTIME").expect("GTIME");
        assert_eq!(gt.dims, vec![106]);
        assert_eq!(gt.data.to_f64().unwrap()[50], 4.86);

        // a node that is not there must surface as an error, not as zeros
        match c.get(r"\EFIT_EAST::TOP.MEASUREMENTS:NO_SUCH_NODE") {
            Err(MdsipError::Server { status, text }) => {
                assert_eq!(status & 1, 0, "failure status is even");
                eprintln!("missing node -> status {status}: {text}");
            }
            other => panic!("missing node should error, got {other:?}"),
        }

        // and the guard still holds on a live session
        assert!(matches!(c.get("getenv(\"HOME\")"), Err(MdsipError::Refused(_))));
    }

    #[test]
    fn a_closed_connection_is_reported_not_hung() {
        struct Dead;
        impl Transport for Dead {
            fn send(&mut self, _: &[u8]) -> Result<(), MdsipError> {
                Ok(())
            }
            fn recv(&mut self, _: &mut [u8]) -> Result<usize, MdsipError> {
                Ok(0)
            }
        }
        assert!(matches!(
            Client::login(Dead, "nobody"),
            Err(MdsipError::Transport(_))
        ));
    }
    // ---------------------------------------------------------------- //
    // TDI assembly for the A-Box binding table
    // ---------------------------------------------------------------- //

    /// ★The shapes are not invented here: they are the ones
    /// `tools/abox-mds-bind.py` decomposes the 485 EAST bindings into, one
    /// case per shape it emits.  A change that breaks one of these changes
    /// what every host asks the server for.
    #[test]
    fn the_binding_table_assembles_into_the_expressions_it_came_from() {
        use Index::{All, At};
        let c = |v, n, s: &[Index], i| tdi(v, n, s, i).unwrap();

        //: 46 bindings — the node itself
        assert_eq!(c(Verb::Raw, "\\TIME", &[], false), "\\TIME");
        //: 34 — a raw node with the slice index substituted for `{time_slice}`
        assert_eq!(c(Verb::Raw, "\\BCENTR", &[At(7)], false), "\\BCENTR[7]");
        //: 291 — `DATA(...)`, the commonest by far
        assert_eq!(c(Verb::Data, "\\PLASMA", &[], false), "data(\\PLASMA)");
        //: 145 — the time base
        assert_eq!(c(Verb::DimOf, "\\ECRH_EAST::PECRH1I", &[], false),
                   "dim_of(\\ECRH_EAST::PECRH1I)");
        //: 111 — subscript OUTSIDE the verb
        assert_eq!(c(Verb::Data, "\\EFIT_MFILE:CMPR2", &[At(0), All], false),
                   "data(\\EFIT_MFILE:CMPR2)[0,*]");
        //: 16 — subscript INSIDE it.  ★Not the same expression as the line
        //: above, which is why the placement travels in the table.
        assert_eq!(c(Verb::Data, "\\EFIT_MFILE:CCBRSP", &[At(1), All], true),
                   "data(\\EFIT_MFILE:CCBRSP[1,*])");
        //: 3-D, `[*,*,{t}]`
        assert_eq!(c(Verb::Raw, "\\PSIRZ", &[All, All, At(12)], false),
                   "\\PSIRZ[*,*,12]");
    }

    /// ★`inside` with no subscript is not a third form — there is nothing to
    /// put inside, so it must not produce `data(\\X)` twice over.
    #[test]
    fn inside_with_no_subscript_is_the_plain_form() {
        assert_eq!(tdi(Verb::Data, "\\X", &[], true).unwrap(),
                   tdi(Verb::Data, "\\X", &[], false).unwrap());
    }

    /// ★★The guard that makes the table safe to admit: the node path is
    /// checked HERE, so a binding that smuggled a TDI fragment through the
    /// generator is refused at assembly, not sent.
    #[test]
    fn a_node_that_is_an_expression_is_refused_not_assembled() {
        for bad in ["data(\\X)", "\\X, \\Y", "\\X)+1", "\\X ", ""] {
            assert!(tdi(Verb::Data, bad, &[], false).is_err(),
                    "assembled {bad:?} instead of refusing it");
        }
    }

}

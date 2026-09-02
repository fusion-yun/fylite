//! 张量化 —— 把一棵 DD 树里的结构数组「压」成带索引轴的盒子，以及反过来。
//!
//! ★★两种 IMAS 布局做的是**同一件事**：`time_slice[i].profiles_1d.psi[j]` 这样一族
//! 叶子存成一个 `(n_time, n_psi_max)` 的盒子，各时间片的真实长度另存一份形状表
//! （HDF5 叫 `_SHAPE`，netCDF 叫 `:shape`），元素个数另存一份（`AOS_SHAPE` /
//! 维度长度）。两者只在轴序（HDF5 存反序的数据轴）、填充值与稀疏判据上不同。
//! 所以「压」与「解压」各写一次在这里，两种格式各自只管字节怎么落盘。
//!
//! 术语：**AoS 轴** = 结构数组祖先各一根轴（`time_slice`、`profiles_2d`）；
//! **数据轴** = 叶子自己的维（`psi[j]` 一根，`psi[i, j]` 两根）；**盒子** = AoS 轴
//! 取各层的最大个数、数据轴取各元素的最大长度、其余填充值。

use crate::document::{Array, ArrayData, Node};
use crate::ids_meta::{IdsMeta, Kind};
use std::collections::BTreeMap;

/// 一族叶子（同一条 DD 路径、不同 AoS 索引）。
#[derive(Debug, Clone)]
pub struct LeafTensor {
    pub path: String,
    pub kind: Kind,
    pub ndim: usize,
    /// 结构数组祖先，由外到内。
    pub aos_paths: Vec<String>,
    /// AoS 轴的盒子长度（各层元素个数的最大值）。
    pub aos_max: Vec<usize>,
    /// 数据轴的盒子长度（各元素形状的最大值，numpy 序）。
    pub field_max: Vec<usize>,
    /// `(AoS 索引, 值)`，按遍历序。
    pub elems: Vec<(Vec<usize>, Node)>,
}

/// 一个结构数组的元素个数表。
#[derive(Debug, Clone)]
pub struct AosTensor {
    pub path: String,
    pub parent_aos_paths: Vec<String>,
    pub parent_max: Vec<usize>,
    /// `(父 AoS 索引, 个数)`。
    pub counts: Vec<(Vec<usize>, usize)>,
}

impl AosTensor {
    pub fn max_count(&self) -> usize {
        self.counts.iter().map(|(_, n)| *n).max().unwrap_or(0)
    }

    /// 个数的盒子（父 AoS 轴 + 1），缺席为 0。
    pub fn count_box(&self) -> (Vec<usize>, Vec<i64>) {
        let mut shape = self.parent_max.clone();
        shape.push(1);
        let n: usize = shape.iter().product();
        let mut data = vec![0i64; n];
        for (idx, c) in &self.counts {
            data[flat_index(idx, &self.parent_max)] = *c as i64;
        }
        (shape, data)
    }
}

/// 一棵 DD 树压出来的全部盒子。
#[derive(Debug, Clone, Default)]
pub struct Tensorized {
    pub leaves: Vec<LeafTensor>,
    pub aos: Vec<AosTensor>,
    /// 结构（含 AoS）路径，遍历序 —— netCDF 要为每个写一个占位变量。
    pub structures: Vec<String>,
}

fn flat_index(idx: &[usize], dims: &[usize]) -> usize {
    let mut f = 0usize;
    for (i, d) in idx.iter().zip(dims) {
        f = f * d + i;
    }
    f
}

/// 压。`tree` 是 [`crate::fyodoc::dd_normalize`] 之后的 DD 树。
pub fn tensorize(meta: &IdsMeta, tree: &Node) -> Tensorized {
    let mut t = Tensorized::default();
    let mut leaves: BTreeMap<String, LeafTensor> = BTreeMap::new();
    let mut aos: BTreeMap<String, AosTensor> = BTreeMap::new();
    let mut order_leaves: Vec<String> = Vec::new();
    let mut order_aos: Vec<String> = Vec::new();
    walk(meta, tree, "", &Vec::new(), &Vec::new(), &mut leaves, &mut aos, &mut order_leaves, &mut order_aos, &mut t.structures);
    //: AoS 轴的盒子长度：各层的最大个数
    let max_counts: std::collections::HashMap<String, usize> =
        aos.iter().map(|(p, a)| (p.clone(), a.max_count())).collect();
    let aos_max_of = |p: &str| -> usize { max_counts.get(p).copied().unwrap_or(0) };
    for p in &order_aos {
        let mut a = aos.remove(p).unwrap();
        a.parent_max = a.parent_aos_paths.iter().map(|q| aos_max_of(q)).collect();
        t.aos.push(a);
    }
    for p in &order_leaves {
        let mut l = leaves.remove(p).unwrap();
        l.aos_max = l.aos_paths.iter().map(|q| aos_max_of(q)).collect();
        let mut fm = vec![0usize; l.ndim];
        for (_, v) in &l.elems {
            for (d, s) in v.shape().iter().enumerate().take(l.ndim) {
                fm[d] = fm[d].max(*s);
            }
        }
        l.field_max = fm;
        t.leaves.push(l);
    }
    t
}

#[allow(clippy::too_many_arguments)]
fn walk(meta: &IdsMeta, n: &Node, path: &str, aos_paths: &Vec<String>, idx: &Vec<usize>,
        leaves: &mut BTreeMap<String, LeafTensor>, aos: &mut BTreeMap<String, AosTensor>,
        order_leaves: &mut Vec<String>, order_aos: &mut Vec<String>, structures: &mut Vec<String>) {
    let m = match n.as_map() {
        Some(m) => m,
        None => return,
    };
    for (k, v) in m.iter() {
        let p = if path.is_empty() { k.to_string() } else { format!("{path}/{k}") };
        let e = match meta.entry(&p) {
            Some(e) => e,
            None => continue,
        };
        match e.kind {
            Kind::Structure => {
                if !structures.contains(&p) {
                    structures.push(p.clone());
                }
                walk(meta, v, &p, aos_paths, idx, leaves, aos, order_leaves, order_aos, structures);
            }
            Kind::StructArray => {
                let l = match v.as_list() {
                    Some(l) => l,
                    None => continue,
                };
                if !structures.contains(&p) {
                    structures.push(p.clone());
                }
                if !aos.contains_key(&p) {
                    aos.insert(p.clone(), AosTensor {
                        path: p.clone(), parent_aos_paths: aos_paths.clone(), parent_max: vec![], counts: vec![] });
                    order_aos.push(p.clone());
                }
                aos.get_mut(&p).unwrap().counts.push((idx.clone(), l.len()));
                let mut inner = aos_paths.clone();
                inner.push(p.clone());
                for (i, item) in l.iter().enumerate() {
                    let mut ii = idx.clone();
                    ii.push(i);
                    walk(meta, item, &p, &inner, &ii, leaves, aos, order_leaves, order_aos, structures);
                }
            }
            _ => {
                if !leaves.contains_key(&p) {
                    leaves.insert(p.clone(), LeafTensor {
                        path: p.clone(), kind: e.kind, ndim: e.ndim, aos_paths: aos_paths.clone(),
                        aos_max: vec![], field_max: vec![], elems: vec![] });
                    order_leaves.push(p.clone());
                }
                leaves.get_mut(&p).unwrap().elems.push((idx.clone(), v.clone()));
            }
        }
    }
}

impl LeafTensor {
    pub fn is_string(&self) -> bool {
        self.kind == Kind::Str
    }

    /// 盒子的形状：AoS 轴 + 数据轴（`reverse` 反转数据轴，HDF5 的存法）。
    pub fn box_shape(&self, reverse: bool) -> Vec<usize> {
        let mut s = self.aos_max.clone();
        if reverse {
            s.extend(self.field_max.iter().rev());
        } else {
            s.extend(self.field_max.iter());
        }
        s
    }

    fn box_shape_with(&self, reverse: bool, field_dims: Option<&[usize]>) -> Vec<usize> {
        match field_dims {
            None => self.box_shape(reverse),
            Some(fd) => {
                let mut s = self.aos_max.clone();
                if reverse { s.extend(fd.iter().rev()); } else { s.extend(fd.iter()); }
                s
            }
        }
    }

    /// 每个元素的形状表：AoS 轴 + `[ndim]`，缺席为 0。
    pub fn shape_box(&self, reverse: bool) -> (Vec<usize>, Vec<i64>) {
        let mut shape = self.aos_max.clone();
        shape.push(self.ndim.max(1));
        let n: usize = shape.iter().product();
        let mut data = vec![0i64; n];
        for (idx, v) in &self.elems {
            let mut s: Vec<usize> = v.shape();
            s.resize(self.ndim, 0);
            if reverse {
                s.reverse();
            }
            let base = flat_index(idx, &self.aos_max) * self.ndim.max(1);
            for (d, x) in s.iter().enumerate() {
                data[base + d] = *x as i64;
            }
        }
        (shape, data)
    }

    /// 所有元素都是满盒子（形状 = 数据轴最大）且每个 AoS 位置都有元素？
    ///
    /// imas-python 的 `sparse` 判据：张量化的叶子，形状表全等于满形状才不稀疏；
    /// 0 维叶子则看每个位置是否都填了。
    pub fn is_full(&self) -> bool {
        let n_slots: usize = self.aos_max.iter().product();
        if self.elems.len() != n_slots {
            return false;
        }
        self.elems.iter().all(|(_, v)| {
            let mut s = v.shape();
            s.resize(self.ndim, 0);
            s == self.field_max
        })
    }

    /// 数值盒子（行主序，`reverse` 反转数据轴并转置各元素）。
    ///
    /// `field_dims`：数据轴按这个长度开盒（netCDF 的维度可能比本叶子的最大形状大，
    /// 因为维度是共用的）；`None` 取各元素的最大值。
    pub fn box_f64(&self, fill: f64, reverse: bool, field_dims: Option<&[usize]>) -> (Vec<usize>, Vec<f64>) {
        let shape = self.box_shape_with(reverse, field_dims);
        let n: usize = shape.iter().product();
        let mut data = vec![fill; n];
        for (idx, v) in &self.elems {
            let arr = match v {
                Node::Array(a) => if reverse { a.transposed() } else { a.clone() },
                other => match other.as_f64() {
                    Some(x) => Array::vec_f64(vec![x]),
                    None => continue,
                },
            };
            let vals = match arr.to_f64() { Some(v) => v, None => continue };
            let elem_shape: Vec<usize> = if self.ndim == 0 { vec![] } else { arr.shape.clone() };
            place(&shape, &mut data, idx, &elem_shape, &vals, self.ndim);
        }
        (shape, data)
    }

    pub fn box_i64(&self, fill: i64, reverse: bool, field_dims: Option<&[usize]>) -> (Vec<usize>, Vec<i64>) {
        let (shape, f) = self.box_f64(fill as f64, reverse, field_dims);
        (shape, f.into_iter().map(|x| x as i64).collect())
    }

    /// 字符串盒子：0 维给 AoS 轴的盒子，1 维加一根「第几个字符串」轴。
    pub fn box_str(&self, field_dims: Option<&[usize]>) -> (Vec<usize>, Vec<String>) {
        let shape = self.box_shape_with(false, field_dims);
        let n: usize = shape.iter().product();
        let mut data = vec![String::new(); n];
        for (idx, v) in &self.elems {
            let vals: Vec<String> = match v {
                Node::Str(s) => vec![s.clone()],
                Node::Array(a) => a.as_str().map(|s| s.to_vec()).unwrap_or_default(),
                _ => continue,
            };
            let elem_shape: Vec<usize> = if self.ndim == 0 { vec![] } else { vec![vals.len()] };
            place(&shape, &mut data, idx, &elem_shape, &vals, self.ndim);
        }
        (shape, data)
    }
}

/// 把一个元素放进盒子的 `idx` 位置（数据轴从 0 起、不足处保留填充）。
fn place<T: Clone>(shape: &[usize], data: &mut [T], idx: &[usize], elem_shape: &[usize], vals: &[T], ndim: usize) {
    let n_aos = idx.len();
    let box_field = &shape[n_aos..];
    if vals.is_empty() {
        return;
    }
    if ndim == 0 {
        let f = flat_index(idx, &shape[..n_aos]);
        data[f] = vals[0].clone();
        return;
    }
    if elem_shape.len() != ndim {
        return;
    }
    //: strides of the box
    let mut strides = vec![1usize; shape.len()];
    for i in (0..shape.len().saturating_sub(1)).rev() {
        strides[i] = strides[i + 1] * shape[i + 1];
    }
    let base: usize = idx.iter().zip(&strides).map(|(i, s)| i * s).sum();
    let n_elem: usize = elem_shape.iter().product();
    for (k, v) in vals.iter().enumerate().take(n_elem) {
        //: unravel k in elem_shape (row-major) -> offset in the box
        let mut rem = k;
        let mut off = 0usize;
        let mut ok = true;
        for d in (0..ndim).rev() {
            let i = rem % elem_shape[d];
            rem /= elem_shape[d];
            if i >= box_field[d] {
                ok = false;
                break;
            }
            off += i * strides[n_aos + d];
        }
        if ok {
            data[base + off] = v.clone();
        }
    }
}

// --------------------------------------------------------------------------
// the inverse
// --------------------------------------------------------------------------

/// 把一个 HDF5 序（数据轴反着存）的盒子换成 numpy 序：形状 `[aos..., fk..f1]` →
/// `[aos..., f1..fk]`，元素随之搬家。
pub fn unreverse_field_axes<T: Clone>(shape: &[usize], data: &[T], n_aos: usize) -> (Vec<usize>, Vec<T>) {
    let nf = shape.len().saturating_sub(n_aos);
    if nf < 2 {
        return (shape.to_vec(), data.to_vec());
    }
    let mut new_shape = shape[..n_aos].to_vec();
    new_shape.extend(shape[n_aos..].iter().rev());
    let mut old_strides = vec![1usize; shape.len()];
    for i in (0..shape.len() - 1).rev() {
        old_strides[i] = old_strides[i + 1] * shape[i + 1];
    }
    let n: usize = shape.iter().product();
    let mut out = Vec::with_capacity(n);
    let mut idx = vec![0usize; shape.len()];
    for _ in 0..n {
        //: idx is in new_shape order; old axis for new field axis d is the mirrored one
        let mut off = 0usize;
        for (k, &i) in idx.iter().enumerate() {
            let old_axis = if k < n_aos { k } else { n_aos + (nf - 1 - (k - n_aos)) };
            off += i * old_strides[old_axis];
        }
        out.push(data[off].clone());
        //: increment idx row-major over new_shape
        for k in (0..idx.len()).rev() {
            idx[k] += 1;
            if idx[k] < new_shape[k] {
                break;
            }
            idx[k] = 0;
        }
    }
    (new_shape, out)
}

/// 一个从盘上读回的盒子。
#[derive(Debug, Clone)]
pub struct LeafBox {
    pub path: String,
    /// AoS 轴数。
    pub n_aos: usize,
    /// 盒子的形状（AoS 轴 + 数据轴，**已是 numpy 序**）。
    pub shape: Vec<usize>,
    pub data: ArrayData,
    /// 每个元素的形状表（AoS 轴 + `[ndim]`，numpy 序）；`None` = 都是满的。
    pub shapes: Option<Vec<i64>>,
    /// 0 维数值叶子的「未设」值。
    pub fill: Option<f64>,
}

/// 解压：把盒子放回一棵树。`counts` 是各结构数组的个数表（缺席时按盒子推）。
pub fn detensorize(meta: Option<&IdsMeta>, boxes: &[LeafBox], counts: &[(String, Vec<usize>, Vec<i64>)]) -> Node {
    let mut tree = Node::map();
    let count_at = |aos_path: &str, parent_idx: &[usize]| -> Option<usize> {
        let (_, shape, data) = counts.iter().find(|(p, _, _)| p == aos_path)?;
        let dims = &shape[..shape.len() - 1];
        if parent_idx.len() != dims.len() || parent_idx.iter().zip(dims).any(|(i, d)| i >= d) {
            return None;
        }
        Some(data[flat_index(parent_idx, dims)].max(0) as usize)
    };
    //: AoS lists exist even when empty of leaves
    for (aos_path, shape, data) in counts {
        let dims = &shape[..shape.len() - 1];
        let n: usize = dims.iter().product::<usize>().max(1);
        for f in 0..n {
            let mut rem = f;
            let mut idx = vec![0usize; dims.len()];
            for d in (0..dims.len()).rev() {
                idx[d] = rem % dims[d];
                rem /= dims[d];
            }
            let c = data.get(f).copied().unwrap_or(0).max(0) as usize;
            let ancestors: Vec<String> = aos_paths_of(meta, aos_path, counts);
            if !prefix_exists(&ancestors, &idx, &count_at) {
                continue;
            }
            let p = explicit_path(aos_path, &ancestors, &idx);
            if tree.get(&p).is_none() {
                tree.set(&p, Node::List((0..c).map(|_| Node::map()).collect())).ok();
            }
        }
    }
    for b in boxes {
        let ancestors = aos_paths_of(meta, &b.path, counts);
        let n_aos = b.n_aos;
        let aos_dims = &b.shape[..n_aos];
        let field_dims = &b.shape[n_aos..];
        let ndim = field_dims.len();
        let n_slots: usize = aos_dims.iter().product::<usize>().max(1);
        for f in 0..n_slots {
            let mut rem = f;
            let mut idx = vec![0usize; n_aos];
            for d in (0..n_aos).rev() {
                idx[d] = rem % aos_dims[d];
                rem /= aos_dims[d];
            }
            if !prefix_exists(&ancestors, &idx, &count_at) {
                continue;
            }
            let elem_shape: Vec<usize> = match &b.shapes {
                Some(s) => (0..ndim).map(|d| s[f * ndim.max(1) + d].max(0) as usize).collect(),
                None => field_dims.to_vec(),
            };
            if ndim > 0 && elem_shape.contains(&0) {
                continue;
            }
            let value = extract(&b.shape, &b.data, &idx, &elem_shape);
            let value = match value {
                Some(v) => v,
                None => continue,
            };
            //: unset 0-D numbers carry the fill value
            if ndim == 0 {
                if let (Some(fill), Some(x)) = (b.fill, value.as_f64()) {
                    if x == fill || (fill.abs() > 1e30 && (x / fill - 1.0).abs() < 1e-6) {
                        continue;
                    }
                }
                if matches!(&value, Node::Str(s) if s.is_empty()) && n_aos > 0 {
                    continue;
                }
            }
            let p = explicit_path(&b.path, &ancestors, &idx);
            tree.set(&p, value).ok();
        }
    }
    tree
}

fn aos_paths_of(meta: Option<&IdsMeta>, path: &str, counts: &[(String, Vec<usize>, Vec<i64>)]) -> Vec<String> {
    if let Some(m) = meta {
        return m.aos_ancestors(path);
    }
    //: without a table: whatever count tables are prefixes of the path
    let segs: Vec<&str> = path.split('/').collect();
    let mut out = Vec::new();
    for n in 1..segs.len() {
        let p = segs[..n].join("/");
        if counts.iter().any(|(c, _, _)| *c == p) {
            out.push(p);
        }
    }
    out
}

fn prefix_exists(ancestors: &[String], idx: &[usize], count_at: &dyn Fn(&str, &[usize]) -> Option<usize>) -> bool {
    for (k, a) in ancestors.iter().enumerate() {
        if k >= idx.len() {
            break;
        }
        match count_at(a, &idx[..k]) {
            Some(c) if idx[k] < c => {}
            Some(_) => return false,
            None => {}
        }
    }
    true
}

/// `time_slice/profiles_2d/psi` + 祖先 + 索引 → `time_slice/0/profiles_2d/1/psi`。
fn explicit_path(path: &str, ancestors: &[String], idx: &[usize]) -> String {
    let mut out = String::new();
    let segs: Vec<&str> = path.split('/').collect();
    let mut k = 0usize;
    for n in 1..=segs.len() {
        if !out.is_empty() {
            out.push('/');
        }
        out.push_str(segs[n - 1]);
        let prefix = segs[..n].join("/");
        if k < ancestors.len() && ancestors[k] == prefix && k < idx.len() {
            out.push('/');
            out.push_str(&idx[k].to_string());
            k += 1;
        }
    }
    out
}

fn extract(shape: &[usize], data: &ArrayData, idx: &[usize], elem_shape: &[usize]) -> Option<Node> {
    let n_aos = idx.len();
    let ndim = elem_shape.len();
    let mut strides = vec![1usize; shape.len()];
    for i in (0..shape.len().saturating_sub(1)).rev() {
        strides[i] = strides[i + 1] * shape[i + 1];
    }
    let base: usize = idx.iter().zip(&strides).map(|(i, s)| i * s).sum();
    let n_elem: usize = elem_shape.iter().product();
    let mut offsets = Vec::with_capacity(n_elem);
    for k in 0..n_elem {
        let mut rem = k;
        let mut off = 0usize;
        for d in (0..ndim).rev() {
            let i = rem % elem_shape[d];
            rem /= elem_shape[d];
            off += i * strides[n_aos + d];
        }
        offsets.push(base + off);
    }
    Some(match data {
        ArrayData::F64(v) => {
            if ndim == 0 { Node::Float(*v.get(base)?) } else {
                Node::Array(Array { shape: elem_shape.to_vec(), data: ArrayData::F64(offsets.iter().map(|&o| v[o]).collect()) })
            }
        }
        ArrayData::I64(v) => {
            if ndim == 0 { Node::Int(*v.get(base)?) } else {
                Node::Array(Array { shape: elem_shape.to_vec(), data: ArrayData::I64(offsets.iter().map(|&o| v[o]).collect()) })
            }
        }
        ArrayData::Str(v) => {
            if ndim == 0 { Node::Str(v.get(base)?.clone()) } else {
                Node::Array(Array { shape: elem_shape.to_vec(), data: ArrayData::Str(offsets.iter().map(|&o| v[o].clone()).collect()) })
            }
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fyodoc;

    fn sample() -> Node {
        let mut d = Node::map();
        d.set("time", vec![1.0, 2.0].into()).unwrap();
        d.set("time_slice/0/time", 1.0.into()).unwrap();
        d.set("time_slice/0/profiles_1d/psi", vec![0.0, 0.5, 1.0].into()).unwrap();
        d.set("time_slice/0/profiles_2d/0/psi", Node::Array(Array::f64(vec![2, 3], vec![1., 2., 3., 4., 5., 6.]).unwrap())).unwrap();
        d.set("time_slice/0/profiles_2d/0/grid_type/name", "rectangular".into()).unwrap();
        d.set("time_slice/1/time", 2.0.into()).unwrap();
        d.set("time_slice/1/profiles_1d/psi", vec![0.0, 1.0].into()).unwrap();
        d.set("time_slice/1/global_quantities/ip", 5.0.into()).unwrap();
        d
    }

    #[test]
    fn boxes_take_the_maximum_and_pad_with_the_fill() {
        let meta = IdsMeta::get("equilibrium").unwrap();
        let (dd, _) = fyodoc::dd_normalize("equilibrium", &sample(), &meta);
        let t = tensorize(&meta, &dd);
        let psi = t.leaves.iter().find(|l| l.path == "time_slice/profiles_1d/psi").unwrap();
        assert_eq!(psi.aos_max, vec![2]);
        assert_eq!(psi.field_max, vec![3]);
        let (shape, data) = psi.box_f64(-9e40, false, None);
        assert_eq!(shape, vec![2, 3]);
        assert_eq!(data, vec![0.0, 0.5, 1.0, 0.0, 1.0, -9e40]);
        assert!(!psi.is_full());
        let (ss, sd) = psi.shape_box(false);
        assert_eq!((ss, sd), (vec![2, 1], vec![3, 2]));
        let p2 = t.leaves.iter().find(|l| l.path == "time_slice/profiles_2d/psi").unwrap();
        assert_eq!(p2.aos_max, vec![2, 1]);
        let (shape, data) = p2.box_f64(-9e40, true, None);
        let (ns, nd) = unreverse_field_axes(&shape, &data, 2);
        assert_eq!(ns, vec![2, 1, 2, 3]);
        assert_eq!(&nd[..6], &[1., 2., 3., 4., 5., 6.]);
        assert_eq!(shape, vec![2, 1, 3, 2]);
        assert_eq!(&data[..6], &[1., 4., 2., 5., 3., 6.]);
        assert!(data[6..].iter().all(|&x| x == -9e40));
        let (ss, sd) = p2.shape_box(true);
        assert_eq!(ss, vec![2, 1, 2]);
        assert_eq!(sd, vec![3, 2, 0, 0]);
        let a = t.aos.iter().find(|a| a.path == "time_slice/profiles_2d").unwrap();
        assert_eq!(a.count_box(), (vec![2, 1], vec![1, 0]));
        let ts = t.aos.iter().find(|a| a.path == "time_slice").unwrap();
        assert_eq!(ts.count_box(), (vec![1], vec![2]));
        let name = t.leaves.iter().find(|l| l.path == "time_slice/profiles_2d/grid_type/name").unwrap();
        assert_eq!(name.box_str(None), (vec![2, 1], vec!["rectangular".into(), String::new()]));
        let ip = t.leaves.iter().find(|l| l.path == "time_slice/global_quantities/ip").unwrap();
        assert!(!ip.is_full());
        assert_eq!(ip.box_f64(-9e40, false, None), (vec![2], vec![-9e40, 5.0]));
        let (s4, d4) = psi.box_f64(-9e40, false, Some(&[4]));
        assert_eq!((s4, d4), (vec![2, 4], vec![0.0, 0.5, 1.0, -9e40, 0.0, 1.0, -9e40, -9e40]));
        assert!(t.structures.contains(&"time_slice/profiles_2d/grid_type".to_string()));
    }

    #[test]
    fn detensorize_undoes_tensorize() {
        let meta = IdsMeta::get("equilibrium").unwrap();
        let (dd, _) = fyodoc::dd_normalize("equilibrium", &sample(), &meta);
        let t = tensorize(&meta, &dd);
        let counts: Vec<(String, Vec<usize>, Vec<i64>)> = t.aos.iter().map(|a| {
            let (s, d) = a.count_box();
            (a.path.clone(), s, d)
        }).collect();
        let boxes: Vec<LeafBox> = t.leaves.iter().map(|l| {
            if l.is_string() {
                let (shape, data) = l.box_str(None);
                LeafBox { path: l.path.clone(), n_aos: l.aos_paths.len(), shape, data: ArrayData::Str(data), shapes: None, fill: None }
            } else {
                let (shape, data) = l.box_f64(-9e40, false, None);
                let shapes = if l.ndim > 0 { Some(l.shape_box(false).1) } else { None };
                LeafBox { path: l.path.clone(), n_aos: l.aos_paths.len(), shape, data: ArrayData::F64(data), shapes, fill: Some(-9e40) }
            }
        }).collect();
        let back = detensorize(Some(&meta), &boxes, &counts);
        assert_eq!(back.get("time_slice/1/profiles_1d/psi"), dd.get("time_slice/1/profiles_1d/psi"));
        assert_eq!(back.get("time_slice/0/profiles_2d/0/psi"), dd.get("time_slice/0/profiles_2d/0/psi"));
        assert_eq!(back.get("time_slice/0/profiles_2d/0/grid_type/name").and_then(Node::as_str), Some("rectangular"));
        assert!(back.get("time_slice/0/global_quantities/ip").is_none());
        assert_eq!(back.get("time_slice/1/global_quantities/ip").and_then(Node::as_f64), Some(5.0));
        assert_eq!(back.get("time_slice").unwrap().as_list().unwrap().len(), 2);
        assert_eq!(back.get("time_slice/1/profiles_2d").unwrap().as_list().unwrap().len(), 0);
        assert_eq!(back.get("time"), dd.get("time"));
    }
}

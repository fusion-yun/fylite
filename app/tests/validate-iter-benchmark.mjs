// ITER 15 MA 感应燃烧：含时演化栏对 ASTRA 参考剖面的对拍（T-C2）。
//
// ★★这道闸子把算例说明里的一句话变成数。`docs/examples/evolve/evolve-iter-15ma.jsonld`
// 一直写着「跑到 8 s 时 W_th ≈ 342 MJ、τ_E ≈ 3.6 s、β_N ≈ 1.8、Q ≈ 11 ——
// 与 ITER 15 MA 的设计点同量级」。「同量级」没有参考数、没有容差，也没有
// 任何东西在跑它：改一个缺省、换一版内核，它照样是那句话。
//
// ★参考答案**本来就在仓里**：`tests/data/reference/iter15ma_astra_burn.csv`
// ——ITER Organization 参考算例（CORSICA / ASTRA 15.0 MA，2010-04-07 批次），
// 153 点逐字收录，出处与「不能拿它做什么」写在同目录的 README.md 里。这道
// 闸子是它的第二个读者（第一个是 `rust/fylite/src/heating.rs` 的 α 判据）。
//
// ★★**容差是量出来的，不是定出来的**（`FEATURE.md` §3.2 末那条规矩）。下面
// 每一个数都来自 2026-08-24 的实测，逐条记在 changelog 与
// `docs/note/iter-15ma-benchmark.md` 里；把一个已知缺陷写进容差
// 等于让判据同意这个缺陷，所以缺陷是**单独一条判据**，不是放宽的带宽。
//
// 四段：
//   〔甲〕**原样跑**：算例从菜单套用、按计算键，终态读数钉住。这一段是回归
//        钉——它不判物理对不对，判的是「今天这一档还是昨天那一档」。
//   〔乙〕**边界密度的口径**：`edgene` 落在梯子末端（ψ_N = edgepsin ≈ 0.95），
//        也就是**台基顶**，不是分界面。2026-08-24 起这一档取 **7.0e19**，与
//        内核自己的 ITER 常量和 FUSE 那一档**逐位一致**；与 ASTRA 在
//        x = 0.948 上的 9.654e19 仍差着，那是**口径不同**（EPED 的台基顶密度
//        是格林沃尔德分数定义的），差值钉住而不是当成错。
//   〔丙〕**对拍本身**：密度剖面与边界温度按 ASTRA 钉死，唯一自由参数 χ₀ 由
//        对拍定出来。判的是两件事——χ₀ 落在哪个区间才对得上 ASTRA 的轴上
//        温度；对上之后**归一化形状**还差多远。形状比不需要 V′，正是 README
//        说这张表判得了的那一类（「判据比的是比值」）。★2026-08-24 算例改对
//        之后这个差**变了号**：常数 χ 的剖面从「比 ASTRA 宽」变成「比它窄」。
//   〔丁〕**台基那一路**：`pedestal` 开着时 EPED1-NN 的 `neped` 就是 `edgene`，
//        且 T_ped ≡ p_ped/(2 n k) 是恒等式。这一段判口径，不判 EPED 本身
//        （那是 `validate-pedestal.mjs` 的活）。
//
//   node app/tests/validate-iter-benchmark.mjs [--playwright DIR] [--url BASE]

import { existsSync, readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'iterbm-'));

let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};
/** `got` 落在 [lo, hi] 内 —— 区间两端都是实测出来的。 */
const band = (got, lo, hi, what, unit = '') =>
  say(got >= lo && got <= hi, what,
      `${got.toFixed(3)}${unit} ∈ [${lo}, ${hi}]`);

// --- ASTRA 参考表 ----------------------------------------------------------

const REF = ROOT + '/tests/data/reference/iter15ma_astra_burn.csv';
//: ★★2026-09-04：参考表是**私有**语料（`tests/data` → fydoc 的算例书，一条符号
//: 链接），公开检出里没有它。缺输入的结局只能是**跳过并点名**——此前这里直接
//: `readFileSync`，于是缺一份可选输入时整道闸子以 ENOENT 崩掉，读日志的人看到的
//: 是一段 Node 栈，而不是「这条要私有语料」。
if (!existsSync(REF)) {
  console.log(`跳过：没有 ASTRA 参考表 ${REF}\n  它随 fydoc（私有）走：ln -s <fydoc>/cases tests/data`);
  process.exit(0);
}
const lines = readFileSync(REF, 'utf8').split('\n').filter((l) => l && !l.startsWith('#'));
const head = lines[0].split(',');
const ref = lines.slice(1).map((l) => {
  const v = l.split(','); const o = {};
  head.forEach((h, i) => { o[h] = parseFloat(v[i]); });
  return o;
});
const refX = ref.map((r) => r.x);
const refCol = (c) => ref.map((r) => r[c]);
/** 线性内插；两端取端值。 */
function at(xs, ys, x) {
  for (let i = 1; i < xs.length; i += 1)
    if (x <= xs[i]) {
      const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
      return ys[i - 1] + t * (ys[i] - ys[i - 1]);
    }
  return ys[ys.length - 1];
}

//: ★梯子末端锚在 ASTRA 的哪个面上，是**量出来的、不是假设的**：本栏的
//: Dirichlet 点就是台基顶，而 ASTRA 的剖面恰在 x = 0.948 处过 3.008 keV
//: ——ITER 那一档手填的边界温度正是 3.000 keV。锚点由数据自己给出。
const EDGE_X = 0.948;

// --- 页面 ------------------------------------------------------------------

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error' && !/favicon/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 200));
});
await page.goto(BASE + 'pages/model.html?device=iter', { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {}).textContent || ''),
  null, { timeout: 180000 });

const RUN = '#model-evolve-run';
/** 从菜单套用 ITER 那一档，覆盖 `over` 里的控件，跑一遍，取读数与会话文件。 */
async function march(tag, over) {
  await page.evaluate(() => {
    const s = document.getElementById('model-evolve-case');
    s.value = 'evolve-iter-15ma';
    s.dispatchEvent(new Event('change'));
  });
  await page.waitForTimeout(400);
  await page.evaluate((v) => {
    Object.keys(v).forEach((id) => {
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      if (!el) throw new Error('no control ' + id);
      if (el.type === 'checkbox') { el.checked = !!v[id]; el.dispatchEvent(new Event('change')); }
      else { el.value = v[id];
             el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input')); }
    });
  }, over);
  await page.waitForFunction((k) => !document.querySelector(k).classList.contains('stop'),
                             RUN, { timeout: 300000 });
  await page.click(RUN);
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {}).textContent || ''),
    null, { timeout: 1800000 });
  const rows = await page.evaluate(
    () => [...document.querySelectorAll('#model-evolve-scalars tr')]
            .map((tr) => [...tr.children].map((td) => td.textContent.trim())));
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt')]);
  const f = join(OUT, tag + '.json');
  await dl.saveAs(f);
  return { rows, doc: JSON.parse(readFileSync(f, 'utf8')) };
}
/** 终态读数里那一行的第一个数。 */
const num = (rows, key) => {
  const r = rows.find((x) => x[0].includes(key));
  return r ? parseFloat(r[1]) : NaN;
};
/** 会话文件里的剖面，按梯子末端锚到 ASTRA 的 x。 */
function profiles(doc) {
  const res = doc['fylite:result'];
  const cp = res.core_profiles.profiles_1d;
  const rt = res.equilibrium.time_slice[0].profiles_1d.rho_tor;
  const x = rt.map((r) => EDGE_X * r / rt[rt.length - 1]);
  return { x,
           te: cp.electrons.temperature.map((v) => v / 1e3),
           ti: cp.t_i_average.map((v) => v / 1e3),
           ne: cp.electrons.density.map((v) => v / 1e19) };
}

// === 〔甲〕原样跑：终态读数的回归钉 =========================================

console.log('〔甲〕ITER 15 MA 自足档，原样跑');
const shipped = await march('shipped', { pedestal: false });
{
  const t = num(shipped.rows, '时间');
  band(t, 7.99, 8.01, '跑满 400 步到 t = 8 s', ' s');
  band(num(shipped.rows, 'T_e(0)'), 22.8, 23.9, 'T_e(0)', ' keV');
  band(num(shipped.rows, '热储能'), 349, 363, 'W_th', ' MJ');
  band(num(shipped.rows, 'τE'), 4.79, 4.99, 'τ_E', ' s');
  band(num(shipped.rows, 'beta_N'), 1.73, 1.81, 'β_N');
  band(num(shipped.rows, 'Q'), 11.0, 11.6, 'Q');
  //: ★成分自洽：氖 1.10 % 隐含的 Z_eff 必须与控件上的 2.00 对得上——这一栏
  //: 报出两个数正是为了让它可判，而不是让读者相信
  say(/1\.9\d? \/ 2\.00/.test((shipped.rows.find((r) => r[0].includes('隐含 Zeff'))
      || ['', ''])[1] || ''), '隐含 Z_eff 与控件对得上',
      (shipped.rows.find((r) => r[0].includes('隐含 Zeff')) || ['', '—'])[1]);
  //: ★算例说明里那四个数就是这四条。它们**不是**对 ASTRA 的判据，判的是
  //: 「这一档没有悄悄变成另一档」。
  //: ★★带宽在 2026-08-24 重定过：形状、台基顶密度与成分按三处一致的来源改了
  //: （κ 1.70→1.86 · δ 0.34→0.48 · n_ped 3.0→7.0e19 · Z_eff 1.20→2.00 经氖
  //: 1.10 %），χ₀ 随之从 0.6 重定为 0.40。★τ_E 从 3.64 升到 4.89 **不是变差**：
  //: 氖辐射 34.7 MW（非韧致 10.4），而 τ_E = W/(P_in − P_rad)。
}

// === 〔乙〕边界密度的口径：edgene 落在台基顶，不是分界面 =====================

console.log('〔乙〕边界密度落在哪个面上');
{
  const p = profiles(shipped.doc);
  const cfg = shipped.doc['fylite:config'];
  const edgeNe = p.ne[p.ne.length - 1];
  say(Math.abs(edgeNe - cfg.edgene) < 1e-9,
      'n_e 的末点就是 edgene（梯子末端 = Dirichlet 点）',
      `${edgeNe.toFixed(3)} vs ${cfg.edgene}`);
  say(Math.abs(cfg.edgepsin - 0.95) < 1e-9,
      '梯子末端是 ψ_N = 0.95，也就是台基顶', `edgepsin = ${cfg.edgepsin}`);
  const aNe = at(refX, refCol('ne_1e19'), EDGE_X);
  const dev = 100 * (edgeNe / aNe - 1);
  //: ★★2026-08-24 起这一条判的是**对上了**，不再是一个已知的口径错。
  //: 台基顶密度取 **7.0e19**，与**两处独立来源逐位一致**：内核自己的 ITER
  //: 验证常量（`rust/fylite/src/pedestal.rs` 的 `const ITER`，`neped: 7.0`）与
  //: FUSE 的 `case_parameters(:ITER; init_from=:scalars)`
  //: （`0.9 × 0.75 × n_G` = 7.008e19）。
  say(Math.abs(edgeNe - 7.0) < 1e-9,
      '★台基顶密度 = 内核 ITER 常量与 FUSE 那一档的 7.0e19',
      `${edgeNe.toFixed(3)}e19`);
  //: ★仍与 ASTRA 在 x = 0.948 上的 9.654e19 差着，那**不是错**：ASTRA 那一点
  //: 是它自己剖面上的一个面，而 7.0e19 是 EPED 口径的台基顶密度（格林沃尔德
  //: 分数定义的）。差值钉住，是为了它哪天变了有人知道。
  band(dev, -30, -25, 'ASTRA 在 x = 0.948 上的密度与它的差（口径不同，非错）', ' %');
  say(aNe > 9 && aNe < 10, 'ASTRA 在同一个面上的密度', `${aNe.toFixed(3)}e19`);
}

// === 〔丙〕对拍：密度与边界按 ASTRA 钉死，χ₀ 由对拍定出来 =====================

console.log('〔丙〕对拍——ASTRA 的密度剖面与台基顶，χ₀ 是唯一的自由参数');
//: ne0 / edgene / peakn 取 ASTRA 自己的剖面（轴 11.29e19、x=0.948 处 9.65e19，
//: 幂次由这两点加 x=0.6 的 11.06e19 反解得 0.34）；边界温度取 ASTRA 在同一个
//: 面上的 T_e / T_i。★`edgene` 的格点是 0.1，所以写 9.7 而不是 9.65——写
//: 9.65 会被格点悄悄改成 9.7。
const MATCH = { ne0: 11.29, edgene: 9.7, peakn: 0.34, edgete: 3.0, edgeti: 3.22,
                pedestal: false };
const aTe0 = refCol('te_kev')[0];
//: ★χ₀ 的格点是 0.05；2026-08-24 算例改对之后夹住 ASTRA 的那两档是 0.25 / 0.30
//: （此前是 0.42 / 0.45——旧的形状小、无氖辐射）
//: ★★而 `edgeti` 这一格，在滑杆上限还是 3 keV 的时候，被**悄悄夹到了 3.0**：
//: 这张表写着 3.22（ASTRA 在 x = 0.948 上的 T_i），跑的却是 3.00——从这张表
//: 落地那一刻起（`2dc9872`，同日）两条带子就都是在夹住的边界上标定的。
//: 上限放开到 8 keV（连带 δ / B₀ / n_e /
//: peakn 那几根，见 `tools/fuse-case-to-fylite.py` —— FUSE 的 SPARC、ARC、
//: MANTA 放不进原来的量程）之后，这张表才真的跑的是它写的那个边界，
//: T_e(0) 也就从 30.33 / 23.99 变成 32.18 / 25.31，夹出的 χ₀ 从 0.277 移到
//: **0.288**（+4 %）。★这一条是「格点会悄悄改值」的另一面：夹住比落格更狠，
//: 而且没有任何一处会喊。
const lo = await march('chi025', { ...MATCH, chi0: 0.25 });
const hi = await march('chi030', { ...MATCH, chi0: 0.30 });
{
  const teLo = num(lo.rows, 'T_e(0)'), teHi = num(hi.rows, 'T_e(0)');
  say(teHi < aTe0 && aTe0 < teLo,
      `★χ₀ ∈ [0.30, 0.25] 夹住 ASTRA 的轴上温度 ${aTe0.toFixed(2)} keV`,
      `${teHi.toFixed(2)} < ${aTe0.toFixed(2)} < ${teLo.toFixed(2)}`);
  band(teLo, 31.6, 32.7, 'χ₀ = 0.25 的 T_e(0)', ' keV');
  band(teHi, 24.8, 25.8, 'χ₀ = 0.30 的 T_e(0)', ' keV');

  //: ★形状比：T(x)/T(0)，两边各自归一。不需要 V′、不需要绝对功率，正是
  //: README 说这张表判得了的那一类。轴上对齐之后剩下的就是「这套输运模型
  //: 让剖面漂了多远」——常数 χ 给出的剖面比 ASTRA **宽**。
  const p = profiles(lo.doc);
  const aTe = refCol('te_kev');
  const shape = (x) => 100 * ((at(p.x, p.te, x) / p.te[0])
                              / (at(refX, aTe, x) / aTe[0]) - 1);
  const s2 = shape(0.2), s6 = shape(0.6), s9 = shape(0.9);
  console.log(`        形状差 T/T(0)：x=0.2 ${s2.toFixed(1)}% · `
              + `x=0.6 ${s6.toFixed(1)}% · x=0.9 ${s9.toFixed(1)}%`);
  //: ★★2026-08-24 这个结论**变了号**，而且是算例改对带来的：此前（κ 1.70 ·
  //: δ 0.34 · 无氖）常数 χ 的剖面比 ASTRA **宽**，中径最大 +20.6 %；换成
  //: 三处一致的形状与成分之后，它比 ASTRA **窄**，且差值**向外增大**
  //: （x = 0.2 −0.6 % → 0.6 −12.2 % → 0.9 −17.4 %），不再是中径最大。
  //: （这三个数在 `edgeti` 的夹持解除之后由 −1.3 / −15.3 / −16.4 微动到此，
  //:  结论——窄、且向外增大——没有变。）
  //: ★旧结论是在**错的输入**上量的——留着它比没有它更坏。
  band(s2, -6, 6, '芯部形状差（x = 0.2）', ' %');
  band(s6, -20, -10, '★中径形状差（x = 0.6）——常数 χ 比 ASTRA 窄', ' %');
  band(s9, -22, -11, '近边形状差（x = 0.9）', ' %');
  say(Math.abs(s2) < Math.abs(s6) && Math.abs(s6) <= Math.abs(s9) + 2,
      '形状差向外增大（不是整体平移，也不再是中径最大）',
      `|${s2.toFixed(1)}| < |${s6.toFixed(1)}| ≲ |${s9.toFixed(1)}|`);
}

// === 〔丁〕台基那一路的口径 =================================================

console.log('〔丁〕台基开着时 EPED 拿到的是哪一个密度');
{
  const on = await march('ped', { ...MATCH, chi0: 0.42, pedestal: true });
  const ped = on.doc['fylite:pedestal'];
  say(!!ped, '会话文件带台基块');
  const inp = ped['fylite:inputs'], ap = ped['fylite:applied'];
  say(Math.abs(inp['fylite:neped_1e19'] - MATCH.edgene) < 1e-9,
      '★EPED 的 neped 就是 edgene（台基顶密度，不是分界面密度）',
      `${inp['fylite:neped_1e19']} vs ${MATCH.edgene}`);
  //: T_ped = p_ped/(2 n k) —— EPED 自己的 T_e = T_i 约定，是恒等式不是拟合
  const QE = 1.602176634e-19;
  const tid = ap['fylite:p_ped'] / (2 * MATCH.edgene * 1e19 * QE);
  say(Math.abs(tid / ap['fylite:t_ped'] - 1) < 1e-9,
      'T_ped ≡ p_ped/(2 n_ped k) 逐位成立',
      `${(tid).toFixed(3)} vs ${ap['fylite:t_ped'].toFixed(3)} eV`);
  //: ★口径对上之后，EPED 在这一档上给出的台基顶**低于** ASTRA 的台基顶：
  //: ASTRA 在 x = 0.948 上是 3.008 / 3.224 keV，EPED 给 ~1.9 keV。这是
  //: **两个模型的差**，不是口径错——记在这里，容差由实测定（T-C7）。
  const aT = at(refX, refCol('te_kev'), EDGE_X);
  console.log(`        EPED 的台基顶 ${(ap['fylite:t_ped'] / 1e3).toFixed(3)} keV`
              + ` vs ASTRA 在同一面上的 ${aT.toFixed(3)} keV`
              + ` （${(100 * (ap['fylite:t_ped'] / 1e3 / aT - 1)).toFixed(1)} %）`);
  //: ★★2026-08-24：算例改对之后这一条从「低 36.7 %」变成「差 ~1 %」。
  //: 台基那一路现在**对上了 ASTRA**，剩下的是模型差本身。
  band(ap['fylite:t_ped'] / 1e3, 2.9, 3.2, '★EPED 台基顶（对上 ASTRA 的 3.004）', ' keV');
}

// === 〔戊〕喂给 EPED 的形状与成分，是哪一套口径 ==============================
//
// ★★内核自己的 ITER 常量（`rust/fylite/src/pedestal.rs` 的 `const ITER`）是
// **δ = 0.485 · κ = 1.85 · Z_eff,ped = 1.8**——**分界面形状**与**台基处**的
// Z_eff，`the_iter_baseline_lands_on_the_published_eped1_prediction` 那条测试
// 就跑在它上面（79.03 kPa / Δψ 0.0330 / T_ped 3.523 keV，正中已发表区间）。
// 而 `worker.js` 喂的是 `sp.delta` / `sp.kappa` / `sp.zeff`——算例里的
// **95 % 形状**（ITER 那一档 δ 0.34 · κ 1.70）与**体平均** Z_eff（1.2）。
//
// **内核验在一套口径上，页面喂的是另一套。** 这一段把它判出来：同一个
// n_ped，两套口径各跑一遍，比的是内核自己那条测试要求的三个区间。
//
// ★用页面而不是原生内核跑，是为了不给这道闸子添一个 numpy 依赖；代价是
// β_N 由推进给出、两遍不同（2.55 / 3.26）。这不影响判决——β_N 在这里只值
// 几个百分点（原生扫描：1.8 → 1.39 只动 −2.6 %，逐项数在笔记 §7）。

console.log('〔戊〕喂给 EPED 的形状与成分，现在是哪一套');
{
  //: 内核测试自己的三个区间（同一份 pedestal.rs）
  const P_BAND = [60, 110], W_BAND = [0.025, 0.045], T_BAND = [3.0, 4.6];
  const on = await march('conv-now', { ...MATCH, edgene: 7.0, chi0: 0.42,
                                       pedestal: true });
  const ped = on.doc['fylite:pedestal'];
  const i = ped['fylite:inputs'], ap = ped['fylite:applied'];
  const p = ap['fylite:p_ped'] / 1e3, t = ap['fylite:t_ped'] / 1e3;
  const w = ped['fylite:width'][0];
  console.log(`        喂进去的 δ ${i['fylite:delta']} · κ ${i['fylite:kappa']}`
              + ` · Z_eff,ped ${i['fylite:zeff_ped']} · n_ped ${i['fylite:neped_1e19']}`);
  console.log(`        p_ped ${p.toFixed(2)} kPa · T_ped ${t.toFixed(3)} keV · Δψ ${w.toFixed(4)}`);
  //: ★★2026-08-24：这一段此前判的是**页面喂错了口径**（δ₉₅/κ₉₅ 与体 Z_eff，
  //: 把 T_ped 压到内核那条测试要求的区间之下）。算例改对之后它判的是**对上了**。
  say(i['fylite:delta'] >= 0.47 && i['fylite:kappa'] >= 1.84
      && i['fylite:zeff_ped'] >= 1.9,
      '★喂给 EPED 的是分界面形状与台基 Z_eff（不再是 δ₉₅/κ₉₅ 与体 Z_eff）',
      `δ ${i['fylite:delta']} · κ ${i['fylite:kappa']} · Z_eff ${i['fylite:zeff_ped']}`);
  say(p >= P_BAND[0] && p <= P_BAND[1] && w >= W_BAND[0] && w <= W_BAND[1]
      && t >= T_BAND[0] && t <= T_BAND[1],
      '★★落在内核自己那条 ITER 测试的三个区间里',
      `p ${p.toFixed(1)} ∈ [${P_BAND}] · Δψ ${w.toFixed(4)} ∈ [${W_BAND}]`
      + ` · T ${t.toFixed(2)} ∈ [${T_BAND}]`);
  //: ★并且落在**已发表的** EPED1 ITER 基线附近（~79 kPa / 0.033 / 3.5 keV），
  //: 那正是内核 `const ITER` 逐位钉住的那一组
  band(p, 74, 88, '★p_ped 在已发表的 EPED1 ITER 基线附近', ' kPa');
  band(t, 3.3, 3.9, '★T_ped 在已发表的 EPED1 ITER 基线附近', ' keV');
}

// === 收尾 ==================================================================

say(errs.length === 0, '页面零报错', errs.join(' | ').slice(0, 200));
await br.close();
console.log(bad ? `\n✗ ${bad} 条不过` : '\n全部通过');
process.exit(bad ? 1 : 0);

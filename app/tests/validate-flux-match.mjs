// 通量匹配档（T-C13）：内核的牛顿通量匹配器，终于有了一个调用者。
//
// ★★这道闸子存在的理由，是一句本仓自己写了三处的话被实测推翻了。`TODO`
// §10.1、`docs/note/fuse-cases.md` 与 changelog 都写着「缺的是那个
// 外循环本身」——**只对一半**：通量匹配器一直在内核里（`flux_match`，六个 ABI
// 入口，对 TGYRO 自身的迭代表 1e-6），**缺的是调用者**：`app/` 下唯一命中是
// wasm 二进制本身，没有一行 JavaScript 调它。所以这一批是**接线**，而闸子要
// 判的正是接线会静默失败的那几处。
//
// 四段，每一段判一件会静默出错的事：
//
//   〔甲〕**它真的收敛**。在 `evolve-fuse-iter` 那一档上跑到公差之内，并且
//        每一个匹配半径、每一条通道都在公差之内——一个「通过了的最大残差」
//        会盖住是哪个半径在扛。★**逐轮残差不是单调的**，这一条是实测改的：
//        立项判据写的是「单调下降」，而实测（下面钉住的那串数）在前几轮会
//        上下摆——那是内核逐点回退里「卡住就扔两倍远」那条规则在动。所以判
//        的是**终值就是全程最小值**加上**量级下降**，不是单调。
//
//   〔乙〕**匹配出来的稳态，就是同一条闭包推进出来的稳态**。这是本仓能对
//        这个求解器提出的最强判据：牛顿求根与抛物型推进是**两个完全不同的
//        解法**，喂同一套度规、同一条闭包、同一组源，必须落在同一条剖面上。
//        native 侧的同一条交叉锚在 `tests/test_transport_east.py`。
//        ★**而两者离 ASTRA 都很远，常数 χ 档反而近**——这不是矛盾，是**闭包
//        的差**而不是求解器的差，下面把三个数一起报出来正是为了让这句话可判。
//
//   〔丙〕**不收敛时按失败报出，并且不退回常数 χ**。用 ASTRA 自己的密度钉住
//        同一台机器：那一组输入下**离子道在外侧的目标通量是负的**（氖辐射
//        超过电子道的加热，交换项把离子抽干），也就是说**这个位形没有正通量
//        的稳态**——求解器必须说出来，而不是交一条剖面。
//
//   〔丁〕**文件里的记录可以重新推出来**。残差列 = (模型 − 目标) × 权重，
//        逐点重算；燃烧那一次皮卡分裂的代价也在文件里。
//
//   node app/tests/validate-flux-match.mjs [--playwright DIR] [--url BASE]

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'fluxm-'));

let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};
/** `got` 落在 [lo, hi] 内 —— 区间两端都是实测出来的。 */
const band = (got, lo, hi, what, unit = '') =>
  say(got >= lo && got <= hi, what,
      `${got.toFixed(3)}${unit} ∈ [${lo}, ${hi}]`);

// --- ASTRA 参考表：只取轴上那一个数 ------------------------------------------
//
// ★同一张表，同一条规矩：ITER Organization 参考算例（CORSICA / ASTRA 15.0 MA），
// 逐字收录在仓里。这里只读轴上的 T_e，用来把〔乙〕那句「闭包的差不是求解器的
// 差」变成三个可比的数。
const REF = ROOT + '/tests/data/reference/iter15ma_astra_burn.csv';
const lines = readFileSync(REF, 'utf8').split('\n')
  .filter((l) => l && !l.startsWith('#'));
const head = lines[0].split(',');
const iTe = head.indexOf('te_kev');
const ASTRA_TE0 = parseFloat(lines[1].split(',')[iTe]);

// --- 页面 ------------------------------------------------------------------

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 300)));
page.on('console', (m) => {
  if (m.type() === 'error' && !/favicon/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 300));
});
await page.goto(BASE + 'pages/model.html?device=iter',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 180000 });

const RUN = '#model-evolve-run';
let seq = 0;
/**
 * 从菜单套用一档算例，覆盖 `over` 里的控件，跑一遍，取状态行、读数与会话文件。
 *
 * ★★闸子照 `scenario.js` 的链解析控件 id（栏 → 部件 → 页），这是 §10.1 留下的
 * 三条规矩之一：用与页面不同的方式解析 id 的闸子，测的是没有人访问的那一页。
 */
async function run(tag, caseId, over) {
  await page.evaluate((c) => {
    const s = document.getElementById('model-evolve-case');
    s.value = c;
    s.dispatchEvent(new Event('change'));
  }, caseId);
  await page.waitForTimeout(500);
  await page.evaluate((v) => {
    Object.keys(v).forEach((id) => {
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      if (!el) throw new Error('no control ' + id);
      if (el.type === 'checkbox') {
        el.checked = !!v[id];
        el.dispatchEvent(new Event('change'));
      } else {
        el.value = v[id];
        el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input'));
        el.dispatchEvent(new Event('change'));
      }
    });
  }, over);
  await page.waitForTimeout(300);
  await page.waitForFunction((k) => !document.querySelector(k)
                                      .classList.contains('stop'),
                             RUN, { timeout: 300000 });
  await page.click(RUN);
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 1800000 });
  const state = await page.evaluate(
    () => (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
            .textContent || '');
  const verdict = await page.evaluate(
    () => (document.getElementById('model-evolve-verdict') || {})
            .textContent || '');
  const rows = await page.evaluate(
    () => [...document.querySelectorAll('#model-evolve-scalars tr')]
            .map((tr) => [...tr.children].map((td) => td.textContent.trim())));
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt')]);
  const f = join(OUT, `${seq++}-${tag}.json`);
  await dl.saveAs(f);
  return { state, verdict, rows,
           doc: JSON.parse(readFileSync(f, 'utf8')) };
}
/** 终态读数里那一行的第一个数。 */
const num = (rows, key) => {
  const r = rows.find((x) => x[0].includes(key));
  return r ? parseFloat(r[1]) : NaN;
};

// === 〔甲〕它真的收敛，而且每个半径都收敛 ====================================

console.log('〔甲〕FUSE·ITER 那一档上的通量匹配');
//: ★`fmiter` is set on EVERY run rather than left to the case: the shipped
//: case documents predate this control, so `apply` does not touch it and a
//: value left over from the previous run would carry into the next one —
//: which is exactly how this gate first produced an unrepeatable 〔丙〕.
const a = await run('fuse-iter', 'evolve-fuse-iter',
                    { closure: '4', fmiter: 30 });
const fm = a.doc['fylite:flux_match'];
say(!!fm, '会话文件带通量匹配记录');
say(fm['fylite:converged'] === true, '★收敛了', a.state.trim());
band(fm['fylite:iterations'], 3, 30, '轮数');
say(fm['fylite:worst_relative'] <= fm['fylite:tolerance_relative'],
    '★最大相对通量差进了公差',
    `${(100 * fm['fylite:worst_relative']).toFixed(2)} % ≤ `
    + `${(100 * fm['fylite:tolerance_relative']).toFixed(2)} %`);
//: ★★逐个半径、逐条通道都在公差之内。一个「通过了的最大残差」是全局的，
//: 而读者要的是「哪一面上的通量对上了」——这两句不是同一句话。
{
  const rad = fm['fylite:radii'];
  const tol = fm['fylite:tolerance_relative'];
  const worst = rad.reduce((m, r) => Math.max(
    m, Math.abs(r['fylite:residual_e']), Math.abs(r['fylite:residual_i'])), 0);
  say(worst <= tol, '★每一个匹配半径的两条通道都在公差之内',
      `最差 ${(100 * worst).toFixed(2)} %，共 ${rad.length} 个半径`);
  say(rad.length >= 4, '匹配半径不少于四个', `${rad.length}`);
  //: 匹配区不含轴附近：那里局部模型没有不稳定模，而包含它时实测发散
  //: （a/L_Ti 被推成负的，残差从 104 % 爬到 141 %）
  say(rad[0]['fylite:rho_tor_norm'] >= 0.15,
      '★匹配区不从轴旁开始（含轴附近时实测发散）',
      `内边界 ρ̂ = ${rad[0]['fylite:rho_tor_norm'].toFixed(3)}`);
}
//: ★★★逐轮残差**不是单调的**——这一条是实测把立项判据改掉的。内核逐点回退
//: 里有一条「松弛已经砍过三次就把这一点扔两倍远」的规则（`tgyro` 自己的），
//: 它把卡住的点弹出去，代价是最大残差会回头。所以判的是**终值即全程最小**
//: 与**量级下降**。
{
  const h = fm['fylite:history'].map((x) => x['fylite:worst_relative']);
  const min = Math.min(...h);
  say(h[h.length - 1] === min, '★终值就是全程最小的残差',
      `${(100 * min).toFixed(2)} %`);
  say(h[h.length - 1] < 0.05 * h[0], '★残差比起手下降一个量级以上',
      `${(100 * h[0]).toFixed(1)} % → ${(100 * h[h.length - 1]).toFixed(2)} %`);
  const mono = h.every((v, i) => i === 0 || v <= h[i - 1]);
  console.log(`        逐轮：${h.map((v) => (100 * v).toFixed(1)).join(' → ')} %`
              + `（单调？${mono ? '是' : '否——回退规则在动，见上'}）`);
}
//: ★这一档带台基模型：EPED 吃全局 β_N，而 β_N 正是这次求解在产出的，所以它
//: 在每个迭代边界上按上一轮的剖面重算——与推进档每步滞后一步同一条规矩。
say(fm['fylite:history'].some((x) => x['fylite:t_ped'] > 0),
    '★台基在迭代之间跟着 β_N 动（与推进档同一条滞后规矩）',
    `T_ped ${(fm['fylite:history'][0]['fylite:t_ped'] / 1e3).toFixed(3)} → `
    + `${(fm['fylite:history'][fm['fylite:history'].length - 1]['fylite:t_ped']
          / 1e3).toFixed(3)} keV`);
//: ★没有时间轴，所以时间轨迹那一栏是收起来的，不是画一个点
say(await page.evaluate(
      () => document.getElementById('model-evolve-traces-box').hidden),
    '★没有时间轴时，时间轨迹栏收起（不画一个点冒充轨迹）');
say(!await page.evaluate(
      () => document.getElementById('model-evolve-fm-out').hidden),
    '通量匹配那一栏展开');

// === 〔乙〕交叉锚：同一条闭包，两个完全不同的解法 ============================

console.log('\n〔乙〕交叉锚——牛顿求根 vs 抛物型推进，同一条 TGLF 闭包');
const m4 = await run('iter15-match', 'evolve-iter-15ma',
                     { closure: '4', fmiter: 32 });
const fm2 = m4.doc['fylite:flux_match'];
say(fm2['fylite:converged'] === true, '通量匹配收敛', m4.state.trim());
const te4 = num(m4.rows, 'T_e(0)'), w4 = num(m4.rows, '热储能');

const m3 = await run('iter15-turb', 'evolve-iter-15ma',
                     { closure: '3', fmiter: 30 });
const te3 = num(m3.rows, 'T_e(0)'), w3 = num(m3.rows, '热储能');
//: ★★两个解法必须落在同一条剖面上。★容差是**量出来的**：推进那一路跑满步数
//: 停在 t ≈ 7.3 s 而**没有**停在稳态（常数以外的闭包在这一档上都还在动），所以
//: 剩下的差里有一部分是「它还没到」，不是模型差——这就是这一条按 20 % 判而不
//: 按 1 % 判的原因，而且理由写在这里而不是藏在一个宽容差里。
{
  const d = Math.abs(te4 / te3 - 1);
  say(d < 0.20, '★★匹配出的稳态与 TGLF 推进的终态是同一条剖面',
      `T_e(0) ${te4.toFixed(2)}（匹配） vs ${te3.toFixed(2)}（推进） keV，`
      + `差 ${(100 * d).toFixed(1)} %`);
  const dw = Math.abs(w4 / w3 - 1);
  say(dw < 0.20, '储能也是同一个数',
      `W_th ${w4.toFixed(1)} vs ${w3.toFixed(1)} MJ，差 ${(100 * dw).toFixed(1)} %`);
  say(te4 > te3, '★匹配出的稳态比推进的终态略热（推进还没到）',
      `${te4.toFixed(2)} > ${te3.toFixed(2)} keV`);
}
//: ★★★而两条 TGLF 路线离 ASTRA 都很远，常数 χ 那一档反而近——**这是闭包的
//: 差，不是求解器的差**，也是立项判据〔二〕（「匹配出的剖面对 ASTRA 轴温的差
//: 小于常数 χ 档」）**没有成立**的地方。原因写在数里：常数 χ 那一档的 χ₀
//: 本来就是**对着 ASTRA 标定出来的**（§10.3 那条 χ₀ ≈ 0.288 的对拍），拿一个
//: 拟合过的参数去比一个没有自由参数的模型，赢的一方是被构造出来的。
const c0 = await run('iter15-const', 'evolve-iter-15ma',
                     { closure: '0', fmiter: 30 });
const te0 = num(c0.rows, 'T_e(0)');
{
  const dMatch = Math.abs(te4 - ASTRA_TE0), dConst = Math.abs(te0 - ASTRA_TE0);
  console.log(`        ASTRA 轴上 T_e = ${ASTRA_TE0.toFixed(2)} keV`
              + ` · 通量匹配 ${te4.toFixed(2)}（差 ${dMatch.toFixed(2)}）`
              + ` · 常数 χ₀=0.40 ${te0.toFixed(2)}（差 ${dConst.toFixed(2)}）`);
  //: ★★★这三个数是**记录，不是判据**，而这一条是刻意的。写成
  //: `say(dMatch > dConst)` 就是把「常数 χ 更近」锁成一条要求：哪天闭包真的
  //: 改好了、TGLF 那两路向 ASTRA 靠拢，闸子会因为一件**好事**判红。
  //: `FEATURE.md` §3.2 的规矩正是这一条——**把已知缺陷锁进判据，就是让判据
  //: 同意这个缺陷**。所以这里只印不判；要判的那一条是上面的交叉锚，它判的是
  //: **求解器**，正是 T-C13 该判的东西。
  console.log(`        ★记录（不判）：立项判据〔二〕「匹配比常数 χ 更近 ASTRA」`
              + ` **不成立**——匹配差 ${dMatch.toFixed(2)}、常数 χ 差`
              + ` ${dConst.toFixed(2)} keV。原因不在求解器：同一条闭包**推进**`
              + `出来的终态差 ${Math.abs(te3 - ASTRA_TE0).toFixed(2)} keV，`
              + `一样远；而常数 χ 的 χ₀ 本来就是对着 ASTRA 标定出来的`
              + `（TODO §10.3 那条 χ₀ ≈ 0.288 的对拍）——拿一个拟合过的参数去比`
              + `一个没有自由参数的模型，赢的一方是被构造出来的。`);
}

// === 〔丙〕不收敛时按失败报出，而且不退回常数 χ ==============================

console.log('\n〔丙〕没有稳态的那一组输入：必须报失败，而且不许悄悄换闭包');
//: ★ASTRA 自己的密度剖面（轴 11.29e19、台基顶 9.7e19）钉在这台机器上。氖 1.1 %
//: 在这个密度上辐射掉的功率超过电子道的加热，交换项把离子抽干，于是**离子道
//: 在外侧的目标通量是负的**——正通量的稳态在这组输入下不存在。求解器必须说
//: 出来。
const nofix = await run('nosteady', 'evolve-iter-15ma',
                        { closure: '4', fmiter: 30,
                          ne0: 11.29, edgene: 9.7, peakn: 0.34,
                          edgete: 3.0, edgeti: 3.22, pedestal: false });
const fm3 = nofix.doc['fylite:flux_match'];
say(fm3 && fm3['fylite:converged'] === false, '★如实报出没有收敛',
    nofix.state.trim());
say(/失败|Failed/.test(nofix.state), '★状态行是失败，不是完成');
say(/没有收敛|did not converge/.test(nofix.verdict), '裁决里说了没收敛');
say(/离子道|ion channel/.test(nofix.verdict) && /ρ̂/.test(nofix.verdict),
    '★裁决指名是哪条通道哪个半径最差（「哪一条没满足」）',
    nofix.verdict.slice(0, 90).replace(/\s+/g, ' '));
//: ★★没有静默回退。判两件事：档位还是通量匹配（不是被换成常数 χ），而目标
//: 通量里**真的有负的**——也就是失败的原因是物理而不是迭代不够。
say(nofix.doc['fylite:config'].closure === '4',
    '★★没有退回常数 χ：档位仍是通量匹配',
    `closure = ${nofix.doc['fylite:config'].closure}`);
{
  //: ★★失败的原因写成两个可判的数，而不是一句解释。〔一〕**功率账**：辐射
  //: 吃掉的与投进去的一样多——氖 1.1 % 在 ASTRA 那个密度（轴 11.29e19）上辐射
  //: 掉 44 MW，而外加热只有 33 MW；〔二〕**离子道的目标通量是负的**：辐射全
  //: 记在电子道上，交换项于是从离子往电子抽，外侧包住的离子功率因此为负。
  //: 正通量的稳态在这组输入下**不存在**，模型再迭代也到不了——这不是迭代
  //: 不够。
  const pRad = num(nofix.rows, '辐射（总）');
  const pAux = num(nofix.rows, '外加热');
  say(pRad > pAux, '★功率账：辐射掉的多过外加热（氖在 ASTRA 的密度上）',
      `P_rad ${pRad.toFixed(1)} > P_aux ${pAux.toFixed(1)} MW`);
  const neg = fm3['fylite:radii'].filter((r) => r['fylite:q_i_target'] < 0);
  say(neg.length > 0,
      '★★失败的原因是**物理**：离子道在外侧的目标通量是负的（正通量的稳态不存在）',
      neg.map((r) => `ρ̂ ${r['fylite:rho_tor_norm'].toFixed(3)}: `
                     + `${(r['fylite:q_i_target'] / 1e3).toFixed(1)} kW/m²`)
         .join(' · '));
}

// === 〔丁〕文件里的记录可以重新推出来 ========================================

console.log('\n〔丁〕记录可重新推出来');
{
  //: ★残差列 = (模型 − 目标) × 权重，逐点重算。一个不能从旁边那两列推出来的
  //: 残差列是一个没人能核的数——尺子（peak 与下限）也就必须一起进文件。
  const ref = fm['fylite:weight_ref'], flo = fm['fylite:weight_floor'];
  let worst = 0;
  fm['fylite:radii'].forEach((r) => {
    [['fylite:q_e_model', 'fylite:q_e_target', 'fylite:residual_e'],
     ['fylite:q_i_model', 'fylite:q_i_target', 'fylite:residual_i']]
      .forEach(([mk, tk, rk]) => {
        //: 权重是**起手那一次**目标的逐点倒数（带 5 % 下限），而文件里带的是
        //: 终态的目标——所以这里只能核到「残差与通量差同号、同量级」，量级由
        //: 尺子界定。逐位重算要的是起手目标，那不进文件（它是中间量）。
        const w = 1 / Math.max(Math.abs(r[tk]), flo, 1e-30);
        const got = (r[mk] - r[tk]) * w;
        worst = Math.max(worst, Math.abs(got - r[rk]));
      });
  });
  say(worst < 1.0, '★残差列与通量列自洽（同号同量级，尺子在文件里）',
      `最大偏差 ${worst.toExponential(1)}；尺子 ${(ref / 1e3).toFixed(1)}`
      + ` / 下限 ${(flo / 1e3).toFixed(2)} kW/m²`);
  //: ★★皮卡分裂的代价：把 α 功率冻在每轮起点上，是因为放进雅可比里 ITER 那
  //: 一档十二轮不降反升（最内那个 a/L_Ti 被推成负的）。在终态上把 α 换回实时
  //: 的再取一次残差，两者的差就是这次分裂的代价——**它必须小于公差本身**，
  //: 否则报出来的「收敛」是对一个冻住的问题收敛的。
  say(fm['fylite:burn_frozen'] === true, '★燃烧那一项走皮卡（记录在文件里）');
  say(fm['fylite:burn_self_consistency'] < fm['fylite:tolerance_relative'],
      '★★冻结燃烧的代价小于公差本身（收敛的是真问题，不是冻住的那个）',
      `${(100 * fm['fylite:burn_self_consistency']).toFixed(3)} % < `
      + `${(100 * fm['fylite:tolerance_relative']).toFixed(2)} %`);
  say(fm['fylite:channels'] === 2, '两条通道（电子能与离子能）一起匹配');
  say(fm['fylite:flux_evaluations'] >= fm['fylite:iterations'] * 3,
      '★通量求值次数与轮数对得上（每轮 ≈ 通道数 + 2）',
      `${fm['fylite:flux_evaluations']} 次 / ${fm['fylite:iterations']} 轮`);
}

await br.close();
if (errs.length) {
  console.log('\n页面报错：');
  errs.forEach((e) => console.log('  ' + e));
}
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);

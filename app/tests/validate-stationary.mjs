// 自洽稳态外环（T-C14）：源 → 台基 → 输运 → 电流 → 锯齿，轮流到自洽。
//
// ★★这道闸子判的是接线活最容易**静默失败**的那一件：**一个什么都没改变的
// 外环等于没有这一层**。多跑四轮而结果与一轮逐位相同，状态行照样写「收敛」，
// 而没有任何一处会喊——所以〔乙〕判的是「开与不开必须看得见差别」，不是
// 「开着能跑完」。
//
// 四段：
//   〔甲〕一轮 = 从前的行为。`fmouter = 1` 不写外环记录，跑法一字未变。
//   〔乙〕多轮**改变了结果**，并且在轮数上限内收敛；逐轮的两个变化量在文件里。
//   〔丙〕电流那一步是**稳态解**，`I_p` 是它的**结果**：解出来的电流与请求的
//        并排报出，对不上时照直说——闭上它要环电压回路（T-C16），不是这一层。
//
// ★★★这道闸子留着一个**说明白的缺口**：崩塌那一段代码本身没有被任何浏览器闸子
// 跑过。EAST 那一档在通量匹配解得动的电流范围内不锯齿（400 kA 上 q(0) ≈ 1.43，
// 推到 600 与 700 kA 则第一轮的匹配就不收敛），而判据〔三〕自己允许「没落下去就
// 如实说」。缺的是一个 **q(0) < 1 而通量匹配又解得动**的算例。★写在这里而不是让
// 它无声地消失。
//   〔丁〕解析 Miller 上多轮**拒绝**，不悄悄按一轮跑。
//   〔己〕**跨宿主**：稳态电流那一步的入参进会话文件，装配层
//        `fylite.scenario.model.stationary.steady_current` 原样重做，两边
//        必须落在同一条 ψ 与同一个 I_p 上（判据〔五〕）。
//   〔庚〕**g-file 几何**：步 6 跳过，而且**记录里写明跳了与为什么**
//        （判据〔一〕的另一半）。
//
//   node app/tests/validate-stationary.mjs [--playwright DIR] [--url BASE]

import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const ROOT = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'fylite-stat-'));
let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 300)));
await page.goto(BASE + 'pages/model.html?device=east',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 180000 });

let seq = 0;
async function run(tag, caseId, over, opts) {
  await page.evaluate((c) => {
    const s = document.getElementById('model-evolve-case');
    s.value = c; s.dispatchEvent(new Event('change'));
  }, caseId);
  await page.waitForTimeout(500);
  await page.evaluate((v) => {
    Object.keys(v).forEach((id) => {
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      if (!el) throw new Error('no control ' + id);
      if (el.type === 'checkbox') {
        el.checked = !!v[id]; el.dispatchEvent(new Event('change'));
      } else {
        el.value = v[id];
        el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input'));
        el.dispatchEvent(new Event('change'));
      }
    });
  }, over);
  await page.waitForTimeout(300);
  await page.click('#model-evolve-run');
  //: ★超时可调，理由是量出来的：g-file 那一档若**一次都没跑起来**（页面在
  //: 没有导入 g 文件时直接以一句提示收场，那句话既不是「完成」也不是「失败」），
  //: 缺省的 40 分钟会白等 40 分钟才说话。短一点的上限让「没跑起来」当场露出来。
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null,
    { timeout: (opts && opts.timeout) || 2400000 });
  const state = await page.evaluate(
    () => (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
            .textContent || '');
  const rows = await page.evaluate(
    () => [...document.querySelectorAll('#model-evolve-scalars tr')]
            .map((tr) => [...tr.children].map((td) => td.textContent.trim())));
  if (opts && opts.noExport) return { state, rows, doc: null };
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt')]);
  const f = join(OUT, `${seq++}-${tag}.json`);
  await dl.saveAs(f);
  return { state, rows, doc: JSON.parse(readFileSync(f, 'utf8')) };
}
const num = (rows, key) => {
  const r = rows.find((x) => x[0].includes(key));
  return r ? parseFloat(r[1]) : NaN;
};

//: ★牛顿迭代上限用控件的缺省 30，理由是量出来的：第一轮这一炮要 16 轮，
//: 而**接上步 6 之后靠后的轮次要到 30**（实测第二轮正好 30 轮落到 1.97 %）。
//: 定在 20 会把「外环本身收没收敛」判成「里层解不动」——两句完全不同的话。
const BASECFG = { closure: '4', fmiter: 30 };

console.log('〔甲〕一轮 = 从前的行为');
const one = await run('outer-1', 'evolve-east-hmode',
                      { ...BASECFG, fmouter: 1 });
say(/完成|Done/.test(one.state), '跑完了', one.state.trim().slice(0, 70));
say(one.doc['fylite:stationary'] === undefined,
    '★一轮时**不写**外环记录（跑法与这一档从前逐字相同）');
say(!one.rows.some((r) => /自洽外环/.test(r[0])), '读数里也没有外环那一行');
const te1 = num(one.rows, 'T_e(0)');
const ip1 = one.doc['fylite:ip_from_psi']
  ? one.doc['fylite:ip_from_psi']['fylite:i_p'] : NaN;

console.log('\n〔乙〕多轮：收敛，而且**改变了结果**');
//: ★上限 8 轮而不是 4，理由是量出来的：步 6 接上之后几何也进了这个回路，
//: `evolve-east-hmode` 实测**第 6 轮**才收敛（Δp 41.6 → 10.6 → 9.0 → 19.6 →
//: 8.8 → 2.9 %）。★上游的缺省是 5——但上游的步 4 是另一个 actor
//: （`ActorSteadyStateCurrent`），所以那个 5 不是这一档的数，实测的 6 才是。
const many = await run('outer-8', 'evolve-east-hmode',
                       { ...BASECFG, fmouter: 8 });
say(/完成|Done/.test(many.state), '跑完了', many.state.trim().slice(0, 70));
const so = many.doc['fylite:stationary'];
say(!!so, '多轮时写出外环记录');
if (so) {
  const rounds = so['fylite:rounds'] || [];
  say(so['fylite:converged'] === true, '★外环收敛',
      `${rounds.length} / ${so['fylite:max_rounds']} 轮`);
  say(rounds.length <= so['fylite:max_rounds'], '轮数不超过上限');
  say(rounds.length >= 2, '★至少两轮——第一轮没有可比的上一轮，不算收敛',
      `${rounds.length}`);
  const last = rounds[rounds.length - 1];
  say(last['fylite:d_pressure'] <= so['fylite:tolerance'],
      '★末轮的压强变化进了判据',
      `Δp ${(100 * last['fylite:d_pressure']).toFixed(2)} % ≤ `
      + `${(100 * so['fylite:tolerance']).toFixed(0)} %`);
  say(last['fylite:d_q'] === null
      || last['fylite:d_q'] <= so['fylite:tolerance'],
      '★末轮的 q 变化也进了判据',
      last['fylite:d_q'] === null ? '—'
        : `Δq ${(100 * last['fylite:d_q']).toFixed(2)} %`);
  //: ★★这一条是这道闸子存在的理由
  const ip4 = many.doc['fylite:ip_from_psi']
    ? many.doc['fylite:ip_from_psi']['fylite:i_p'] : NaN;
  const te4 = num(many.rows, 'T_e(0)');
  const dIp = Math.abs(ip4 / ip1 - 1), dTe = Math.abs(te4 / te1 - 1);
  console.log(`        一轮 T_e(0) ${te1.toFixed(2)} keV · I_p `
              + `${(ip1 / 1e3).toFixed(1)} kA  ／  多轮 ${te4.toFixed(2)} keV · `
              + `${(ip4 / 1e3).toFixed(1)} kA`);
  //: ★★这一条是这道闸子存在的理由，但**观测量换了一个**，理由是量出来的：
  //: 步 4 现在**解出**平顶要的环电压，所以开与不开的 I_p 都落在请求值上
  //: （0.1–1.1 %）——拿 I_p 判就会把「电流终于对上了」判成「外环什么都没做」。
  //: 看得见差别的是**芯温与几何**：外环走完剖面与小半径都动了。
  const eqRounds = rounds.filter((r) => r['fylite:equilibrium']);
  const dA = eqRounds.length
    ? Math.abs(eqRounds[eqRounds.length - 1]['fylite:equilibrium']['fylite:a_after']
               / eqRounds[0]['fylite:equilibrium']['fylite:a_before'] - 1) : 0;
  say(dTe > 0.02 || dA > 0.01,
      '★★开与不开**看得见差别**（一个什么都没改变的外环等于没有这一层）',
      `T_e(0) 差 ${(100 * dTe).toFixed(1)} % · 小半径差 ${(100 * dA).toFixed(2)} %`
      + ` · I_p 差 ${(100 * dIp).toFixed(1)} %（被平衡重解拉回去了）`);
  //: ★★锯齿：这一段第一版写的是 `say(true, …)` 加一句「这一炮没有 q(0) < 1」
  //: ——**两处都错**。永真的断言判不出任何东西；而记录里 q(0) = 0.788 明明
  //: 就在 1 以下，没触发的真正原因是**这一档把锯齿开关关着**。所以这里改成
  //: 把开关打开、让锯齿真的被判一次，并按开关的状态分别断言。
  const sawOn = many.doc['fylite:config'].sawtooth === true;
  const saws = rounds.map((r) => r['fylite:sawtooth']).filter(Boolean);
  say(!sawOn && saws.length === 0,
      '★锯齿开关关着时，外环里一次都不该触发',
      `开关 ${sawOn ? '开' : '关'} · 触发 ${saws.length} 轮`);
  //: ★★步 6：装置几何上必须真的重解，而且逐轮的账要在文件里
  say(so['fylite:equilibrium_rounds'] > 0,
      '★★平衡那一步真的转了（不是跳过之后照样说收敛）',
      `${so['fylite:equilibrium_rounds']} / ${rounds.length} 轮`);
  const e0 = eqRounds.length ? eqRounds[0]['fylite:equilibrium'] : null;
  say(!!e0 && isFinite(e0['fylite:beta_p_target'])
      && isFinite(e0['fylite:beta_p_equilibrium']),
      '★两个 β_p 都记下来（这一轮的交替是在闭还是在飘，读者自己看得见）',
      e0 ? `β_p 目标 ${e0['fylite:beta_p_target'].toFixed(3)} · `
           + `平衡 ${e0['fylite:beta_p_equilibrium'].toFixed(3)}` : '');
  say(!!e0 && isFinite(e0['fylite:a_before']) && isFinite(e0['fylite:a_after']),
      '★小半径改了没有，也记下来（几何真的动了才算它进了这个回路）',
      e0 ? `${e0['fylite:a_before'].toFixed(4)} → `
           + `${e0['fylite:a_after'].toFixed(4)} m` : '');
  //: ★Δq 必须算得出来——它一度恒为 NaN（步 6 把 q 置空了），那等于半条收敛
  //: 判据悄悄不存在了
  say(rounds.slice(1).every((r) => r['fylite:d_q'] !== null),
      '★★第二轮起 Δq 都算得出来（半条判据不许悄悄消失）',
      rounds.map((r) => r['fylite:d_q'] === null ? '—'
        : (100 * r['fylite:d_q']).toFixed(1) + '%').join(' · '));
}

console.log('\n〔丙〕锯齿：q(0) 落到 1 以下就必须触发，没落下去就如实说');
//: ★★★这一段的第一版建立在一个**已经不成立的**观测上：当时 q(0) = 0.788，
//: 因为步 4 只解出非感应电流（264 kA / 请求 400），电流剖面是空心的。步 4 改成
//: 解出平顶要的环电压之后，同一炮的 q(0) 升到 1.36–1.45——**这是修好了，不是
//: 回归**，但它把这一段判空了。
//: ★所以这里把电流提上去（700 kA），让 q(0) 真的落到 1 以下；并且**两个方向
//: 都判**：落下去就必须触发，没落下去就必须一次都不触发，而且把哪一种如实印
//: 出来。★这样它既不会因为「这一炮不锯齿」而变成永真，也不会因为电流道没接
//: 上而**永远不判**。
//: ★★★这一炮**在它自己的电流上跑**，而不是被推到 q(0) < 1 去，理由是量出来的：
//: 400 kA 上 q(0) ≈ 1.43；推到 **600 kA 与 700 kA 都跑不出一轮**——那两个工作点上
//: 第一轮的通量匹配就不收敛（600 kA 停在 45.15 %，判据 2 %）。★所以**这一档
//: 等离子体在通量匹配解得动的电流范围内不锯齿**，判据〔三〕自己写的就是这种情形：
//: 「没落下去就如实说『这一炮不锯齿』」。
//: ★★★而这条闸子因此**留着一个说明白的缺口**：崩塌那一段代码本身没有被任何浏览器
//: 闸子跑过。★写在这里而不是让它无声地消失——`fy.sawtoothCrash` 有内核侧的判据，
//: 缺的是「外环里真的崩了一次」的那一炮，它要一个 q(0) < 1 **而通量匹配又解得动**
//: 的算例。★注意这不是回归：修好步 4 之前记录里那个 q(0) = 0.788 正是**空心的
//: 非感应电流剖面**的产物，那是缺陷不是特征。
const sawRun = await run('outer-saw', 'evolve-east-hmode',
                         { ...BASECFG, fmouter: 4, sawtooth: true });
const soS = sawRun.doc['fylite:stationary'];
say(!!soS, '锯齿那一次也写出外环记录');
if (soS) {
  const rr = soS['fylite:rounds'] || [];
  const fired = rr.map((r) => r['fylite:sawtooth']).filter(Boolean);
  const q0s = rr.map((r) => r['fylite:q_axis']);
  const below = q0s.some((x) => x < 1);
  console.log(`        轴上 q 逐轮：${q0s.map((x) => x.toFixed(3)).join(' → ')}`
              + ` · 触发 ${fired.length} / ${rr.length} 轮`);
  //: ★★一轮都没走完时**说出来**，而不是让下面那条在空数组上变成永真。
  //: 「没跑起来」与「跑了但没触发」是两句话。
  say(q0s.length > 0 && q0s.every(isFinite),
      '★每一轮都判过一次（轴上 q 逐轮都在记录里——「永远不判」会在这里露出来）',
      q0s.length ? `${q0s.length} 轮`
                 : `一轮都没走完：${sawRun.state.trim().slice(0, 70)}`);
  say(q0s.length > 0 && (below ? fired.length > 0 : fired.length === 0),
      below ? '★★q(0) 落到 1 以下，锯齿在外环里真的触发了'
            : '★★这一炮 q(0) 一次都没落到 1 以下，所以一次都不该触发（如实说）',
      below
        ? (fired.length ? `r₁ = ${fired[0]['fylite:r_1'].toFixed(3)} m · `
            + `r_mix = ${fired[0]['fylite:r_mix'].toFixed(3)} m` : '一次都没有')
        : `min q(0) = ${Math.min(...q0s).toFixed(3)}`);
  say(fired.every((x) => !x['fylite:refused']),
      '★没有一次是「拒绝的混合半径」（那会是另一回事，也要报出来）');
}

console.log('\n〔丁〕电流那一步是**稳态**解——它解出平顶要的环电压');
//: ★★这一段判的是 T-C14 判据〔六〕，而〔六〕的判词在实测之后变强了：
//: 立项时写的是「解出的 I_p 与请求的并排报出，对不上时照直说」，因为当时
//: 步 4 跑 `dt = ∞`，那一档的欧姆项恒为零、只剩非感应电流（实测差 35 %）。
//: **`dt = ∞` 不是平顶上的托卡马克**：平顶是 ∂ψ/∂t = V_loop 均匀的**稳态**，
//: 长而有限的步长加边界速率就到那里，而 I_p 对速率仿射——所以步 4 可以
//: **解出**那个电压。判据因此从「照直说差多少」升级成「真的对上」。
if (so) {
  const rounds = so['fylite:rounds'] || [];
  const r0 = rounds[0];
  say(r0 && isFinite(r0['fylite:i_p']) && isFinite(r0['fylite:i_p_requested']),
      '★逐轮都把解出的 I_p 与请求的并排记下来',
      r0 ? `${(r0['fylite:i_p'] / 1e3).toFixed(1)} kA / `
           + `${(r0['fylite:i_p_requested'] / 1e3).toFixed(1)} kA` : '');
  say(isFinite(r0['fylite:q_axis']), '★轴上 q 也记下来（锯齿判据的那一个）',
      r0 ? r0['fylite:q_axis'].toFixed(3) : '');
  const worst = Math.max(...rounds.map(
    (r) => Math.abs(r['fylite:i_p'] / r['fylite:i_p_requested'] - 1)));
  say(worst < 0.02,
      '★★每一轮的稳态电流都落在请求值上（判据〔六〕，实测之后变强的那一条）',
      `最差 ${(100 * worst).toFixed(2)} %`);
  const vs = rounds.map((r) => r['fylite:v_loop']).filter((v) => v != null);
  say(vs.length === rounds.length && vs.every(isFinite),
      '★逐轮把解出的环电压记下来（平顶的磁通消耗是这一步的**产出**）',
      vs.map((v) => v.toFixed(3)).join(' / ') + ' V');
  //: ★★不判「电压等于某个数」——那会把一次实测钉成判据。判的是它在
  //: **物理量程里**且**没有被读者的量程截断**：一次被夹住的解是在报告一个
  //: 页面问不出来的边界条件。
  say(rounds.every((r) => r['fylite:v_loop_clamped'] === false),
      '★没有一轮的电压被量程夹住（夹住了要报出来，不是悄悄用）');
}

console.log('\n〔己〕跨宿主：稳态电流那一步，两个宿主同一个解');
//: ★★T-C14〔五〕。会话文件里 `fylite:steady_current` 带着
//: `solve_core(dt = inf, channels = {current})` 的**全部入参**（12 位有效），
//: 这里把它们原样喂给 `fylite.scenario.model.stationary.steady_current`，
//: 两边必须落在同一条 ψ 上。★沿用 `validate-ip-reading`〔乙〕那条既有规矩：
//: 容差 1e-6，因为文件是**有意**按 12 位截断写的。
//: ★这道判据判的是「同一个解」，不是「同一条闭包」——σ 与 j_ni 是浏览器那一
//: 轮闭包的原值，交给 Python 的是**解**这一件事。两句话分开，是因为它们会
//: 分别出错。
const sc = so ? so['fylite:steady_current'] : null;
say(!!sc, '★多轮时写出稳态电流那一步的入参与出参（只有答案的文件判不了〔五〕）');
if (sc) {
  const scFile = join(OUT, 'steady.json');
  writeFileSync(scFile, JSON.stringify(sc));
  const PY = `
import json, sys
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
import numpy as np
from fylite.scenario.model import stationary
d = json.load(open(${JSON.stringify(scFile)}))
out = stationary.steady_current(
    d['fylite:rho_tor'], vprime=d['fylite:vprime'], gm3=d['fylite:gm3'],
    gm2=d['fylite:gm2'], fpol=d['fylite:f_pol'], b0=d['fylite:b0'],
    te=d['fylite:t_e'], ti=d['fylite:t_i'],
    # ★与浏览器那一侧同一件事：这一支马其实用不到密度（热道与密度道都关着），
    # 所以喂什么都一样 —— 喂第一种离子那一块，免得读者以为它进了方程。
    ne=np.asarray(d['fylite:n_i'], float)[:len(d['fylite:rho_tor'])],
    psi=d['fylite:psi_in'], sigma_par=d['fylite:sigma_par'],
    j_ni=d['fylite:j_ni'], edge_psi=d['fylite:edge_psi'],
    # ★★步长与边界速率一起喂——这一支马不是 dt = inf：inf 会把欧姆项整个
    # 去掉，只剩非感应电流。平顶是 dpsi/dt = V_loop 均匀的稳态。
    dt=d['fylite:dt'], edge_psi_rate=d['fylite:edge_psi_rate'],
    tol_steady=d['fylite:tol_steady'], n_coupling=d['fylite:n_coupling'])
ref = np.asarray(d['fylite:psi_out'], float)
psi = np.asarray(out['psi'], float)
den = float(np.max(np.abs(ref))) or 1.0
# ★浏览器那一侧的 I_p：从**文件里的那条 ψ** 上读，用同一支式子（fyo 那份按
# Wb/rad 写，而这条 ψ 是总磁通，所以除 2π——换算写在这里，不在任一侧的脑子里）
from fylite import fyo
ip_ref = fyo.enclosed_plasma_current(d['fylite:rho_tor'], d['fylite:vprime'],
                                     d['fylite:gm2'], ref / (2.0 * np.pi))
print(json.dumps({'worst': float(np.max(np.abs(psi - ref))) / den,
                  'i_p': out['i_p'], 'ip_ref': float(ip_ref[-1]),
                  'psi0': float(psi[0]), 'ref0': float(ref[0])}))
`;
  let py = null;
  try {
    py = JSON.parse(execFileSync('python3', ['-c', PY],
                                 { encoding: 'utf8' }).trim());
  } catch (e) {
    say(false, 'Python 侧跑得起来', String(e.message || e).slice(0, 300));
  }
  if (py) {
    say(py.worst < 1e-6,
        '★★两个宿主把稳态 ψ 解到同一条曲线上（装配层同口径）',
        `最大相对差 ${py.worst.toExponential(2)}（浏览器 ψ(0) `
        + `${py.ref0.toExponential(6)} · Python ${py.psi0.toExponential(6)}）`);
    //: ★★★闸子第一次跑时这里是 1.28e-2，而那**不是缺陷**：推进档每一趟耦合都
    //: 重跑闭包，文件里记的 σ/j_ni 是它最后一趟的值，另一宿主拿它们去解会落在
    //: 一个皮卡步之外。★把容差放宽到能咽下 1.3 % 就等于让这道判据不再抓得住
    //: 它存在的那类错（一个 2π 是 6 倍，一处度规是几十 %——但一处符号或一个
    //: 因子 1.02 就正好躲在那条宽带子里）。所以改的是**记的东西**：文件给的是
    //: 另一宿主真正被问到的那个问题的答案（冻结系数的伴随解），运行自己用的
    //: 那一条并排放着。这一条判那个距离**被记下来了**，而不是判它多小。
    say(sc['fylite:psi_out_frozen'] === true,
        '★文件里给的是冻结系数的伴随解（另一宿主被问到的正是这个问题）');
    const gap = sc['fylite:psi_out_frozen_gap'];
    say(gap != null && isFinite(gap),
        '★★而运行自己那一条与它差多远，也写在文件里——那个距离就是'
        + '「内层的耦合收敛了没有」，是读数不是判据',
        gap == null ? '（没写）' : `${(100 * gap).toFixed(2)} %`);
    //: ★★而且**同一个 I_p**：〔六〕报的那个数，另一个宿主从同一条 ψ 上读得
    //: 出来——两处都用 `fyo.enclosed_plasma_current`，单位换算写在两侧各自
    //: 的代码里而不是任一侧的脑子里。
    //: ★I_p 也从**同一条**（伴随的）ψ 上读，两侧各自用自己那份
    //: `enclosed_plasma_current`——单位换算写在两侧各自的代码里，不在任一侧
    //: 的脑子里。
    const rel = Math.abs(py.i_p / py.ip_ref - 1);
    say(isFinite(rel) && rel < 1e-6,
        '★★从那条 ψ 上读出的 I_p 也是同一个数',
        `浏览器 ${(py.ip_ref / 1e3).toFixed(6)} kA · Python `
        + `${(py.i_p / 1e3).toFixed(6)} kA · 相对差 ${rel.toExponential(2)}`);
  }
}

console.log('\n〔庚〕g-file 几何：步 6 跳过，而且写明理由');
//: ★★判据〔一〕的另一半。g-file 的度规来自一份文件，没有可重解的自由边界
//: ——所以步 6 **跳过**，但记录里必须写明跳了以及为什么，不让读者从缺的键里
//: 推。★`equilibrium_rounds: 0` 是写出来的 0，不是省略。
//: ★★★这一段第一次写时**一次都没跑起来，而且白等了 40 分钟才发现**：页面在
//: 没有导入 g 文件时直接以一句提示收场（`e.err.nogfile`），那句话既不是「完成」
//: 也不是「失败」，于是 `waitForFunction` 一直等到上限。**闸子必须先把 g 文件
//: 喂进去。** 喂的是仓里那份合成 g 文件——它比 ITER 那一档小得多，而这一段判的
//: 不是 ITER 的物理，是「g-file 几何上步 6 跳过并写明理由」这条**代码路径**。
const G = ROOT + '/rust/fylite_engine/testdata/g_synthetic.geqdsk';
const [chooser] = await Promise.all([
  page.waitForEvent('filechooser'),
  page.click('#model-ioimport'),
]);
await chooser.setFiles(G);
//: ★导入本身会触发一次运行（`apply` 末尾就是 `run()`），先让它落定
await page.waitForTimeout(1500);
await page.waitForFunction(
  () => !/运行中|Running/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 600000 }).catch(() => {});
const gf = await run('outer-gfile', 'evolve-east-hmode',
                     { ...BASECFG, fmouter: 3, geometry: 'gfile' },
                     { timeout: 900000 });
const soG = gf.doc['fylite:stationary'];
say(!!soG, 'g-file 那一档也写出外环记录', gf.state.trim().slice(0, 70));
if (soG) {
  say(soG['fylite:equilibrium_rounds'] === 0,
      '★★步 6 一轮都没转（g-file 上本来就没有可重解的边界）',
      `${soG['fylite:equilibrium_rounds']} 轮`);
  say(typeof soG['fylite:equilibrium_why'] === 'string'
      && soG['fylite:equilibrium_why'].length > 0,
      '★★而且理由写在文件里（不是让读者从缺的键里推）',
      soG['fylite:equilibrium_why'] || '（没写）');
  say((soG['fylite:rounds'] || []).every(
        (r) => r['fylite:equilibrium'] === null),
      '★逐轮的那个键也在，值是 null——「跳过」与「没这一步」是两句话');
}

console.log('\n〔戊〕解析 Miller：多轮必须拒绝');
const refused = await run('outer-miller', 'evolve-iter-15ma',
                          { ...BASECFG, fmouter: 4 }, { noExport: true });
say(/失败|Failed/.test(refused.state),
    '★★多轮 + 解析几何 → 失败，不是悄悄按一轮跑',
    refused.state.trim().slice(0, 90));

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);

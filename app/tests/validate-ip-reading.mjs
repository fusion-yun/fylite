// 「从 ψ 读 I_p」：两个宿主同一支式子（T-C16 的反馈量 · T-C14 第 4 步的核对量）
//
// ★★这道闸子判的不是「算出来了」，是三件会静默出错的事：
//
//   〔甲〕**常数**。`I = V′ gm2 (dψ/dρ) / (2π μ₀)` 的常数是从内核自己的电流
//        扩散度规读出来的；一处 2π 的滑落在剖面**形状**上完全看不见，却把答案
//        放到 6 倍或 38 倍之外。所以闸子把三个近似**一起**钉住：将来谁想靠挪
//        常数去「修掉」那 3 %，得先解释这三条为什么不再错。
//
//   〔乙〕**两个宿主是不是同一支式子**。浏览器与 Python 各写了同样六行（写出来
//        而不是各自调库，正是为了让「逐位相同」是关于**一支**式子的断言）。
//        这里把会话文件里的四行原样喂给 `fylite.fyo.enclosed_plasma_current`，
//        两边必须落在同一个数上。
//
//   〔丙〕**读不出电流时必须整块不出现**。解析 Miller 层不解平衡，ψ 恒为零，
//        读数无从谈起——页面本来就为此拒绝电流道。一块填满 null 的记录会读成
//        「算了但是零」。★这一条的**理由换过一次**：从前写的是「说不出 gm2」，
//        而 S-2c 批二 给这一层补上了真的 gm2（Miller 面集本来就定得出 ⟨|∇r|²/R²⟩，
//        只是内核从前没有这一列）。判据没变，缺的那样东西换了名字——若不跟着换，
//        这一块会从「不出现」变成「出现，写着 0」，而 0 是个错数，不是一次拒绝。
//
// ★★而那 3.2 % 的缺额**只报不判死**：它是梯子自己的求积精度（V′ 0.7 %、
// gm2 1.1 %，实测不随分辨率也不随边界位置收敛），所以闸子判的是「比值在一条
// 说得出理由的带里」，并把绝对值与比值一起印出来——**把已知缺陷锁进容差就是让
// 判据同意这个缺陷**（`FEATURE.md` §3.2 的规矩，也是 T-C13 那次改判的理由）。
//
//   node app/tests/validate-ip-reading.mjs [--playwright DIR] [--url BASE]

import { readFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const ROOT = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'fylite-ip-'));

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
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 900000 });
  const state = await page.evaluate(
    () => (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
            .textContent || '');
  const rows = await page.evaluate(
    () => [...document.querySelectorAll('#model-evolve-scalars tr')]
            .map((tr) => [...tr.children].map((td) => td.textContent.trim())));
  //: ★一次被拒绝的运行没有会话文件可导——闸子必须知道这件事，否则它会在
  //: 等一个永远不来的下载，而那看起来像页面挂了
  if (opts && opts.noExport) return { state, rows, doc: null };
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt')]);
  const f = join(OUT, `${seq++}-${tag}.json`);
  await dl.saveAs(f);
  return { state, rows, doc: JSON.parse(readFileSync(f, 'utf8')) };
}

// === 〔甲〕装置几何：读数出现，比值在带里 ====================================

console.log('〔甲〕EAST 那一档（装置几何，电流道开着）');
const a = await run('east', 'evolve-east-hmode', { nsteps: 10 });
say(/完成|Done/.test(a.state), '跑完了', a.state.trim().slice(0, 70));
const blk = a.doc['fylite:ip_from_psi'];
say(!!blk, '会话文件里有「从 ψ 读 I_p」这一块');
if (blk) {
  const ip = blk['fylite:i_p'], ask = blk['fylite:i_p_requested'];
  const ratio = blk['fylite:ratio'];
  console.log(`        I_p(ψ) = ${(ip / 1e3).toFixed(2)} kA · 请求 `
              + `${(ask / 1e3).toFixed(2)} kA · 比 ${ratio.toFixed(4)}`);
  //: ★带子宽，理由说得出：梯子的求积精度（V′ 0.7 % · gm2 1.1 %）加上这一档
  //: 的电流道自己在动（十步之后 I_p 本来就不必等于起手那个请求值）。判的是
  //: 「同一个量级、同一个符号、没有 2π 滑落」，不是「等于」。
  say(ratio > 0.80 && ratio < 1.20,
      '★比值在一条说得出理由的带里（不是把 3 % 锁进容差）',
      `${ratio.toFixed(4)} ∈ (0.80, 1.20)`);
  say(ip > 0 === ask > 0, '符号与请求的一致');
  //: 〔甲〕的近失：三个候选常数各差 2π 的幂次，一起钉住
  const near = [[1, '1/μ₀'], [1 / (4 * Math.PI ** 2), '1/(4π²μ₀)'],
                [4 * Math.PI ** 2, '2π/μ₀ ×2π']];
  const off = near.filter(([k]) => {
    const r = ratio * k * 2 * Math.PI;
    return r > 0.80 && r < 1.20;
  });
  say(off.length === 0,
      '★★没有一个「差 2π 的幂次」的常数也落在带里（所以常数是认出来的）',
      off.map((x) => x[1]).join(' '));
  //: 读数行也要在，且带着比值——一个只进文件不进页面的量，读者核不了
  const row = a.rows.find((r) => /ψ 读出|read from psi/.test(r[0]));
  say(!!row && /比/.test(row[1] || ''), '★读数行在，并且把比值印在旁边',
      row ? row[1] : '(没有这一行)');
}

// === 〔乙〕跨宿主：两个宿主同一支式子 ========================================

console.log('\n〔乙〕跨宿主——把文件里的四行原样喂给 Python 那一份');
if (blk) {
  const PY = `
import json, sys
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
import numpy as np
from fylite import fyo
d = json.load(open(${JSON.stringify(join(OUT, '0-east.json'))}))['fylite:ip_from_psi']
# ★浏览器那一份的 psi 是**总磁通** Wb（app 自己的 full_flux_Wb_axis_max），
# 而 fyo 那一份的式子是按 Wb/rad 写的 —— 所以这里除以 2π 再喂进去。
# 换算写在闸子里而不是藏在任一侧，正是这道闸子第一次跑就抓到的那件事。
psi_per_rad = np.asarray(d['fylite:psi'], float) / (2.0 * np.pi)
i = fyo.enclosed_plasma_current(d['fylite:rho_tor'], d['fylite:vprime'],
                                d['fylite:gm2'], psi_per_rad)
print(json.dumps({'edge': float(i[-1])}))
`;
  let py = null;
  try {
    py = JSON.parse(execFileSync('python3', ['-c', PY],
                                 { encoding: 'utf8' }).trim());
  } catch (e) {
    say(false, 'Python 侧跑得起来', String(e.message || e).slice(0, 200));
  }
  if (py) {
    const rel = Math.abs(py.edge / blk['fylite:i_p'] - 1);
    //: ★容差 1e-6，理由与 `validate-transport-app.mjs` 同一条：会话文件是
    //: **有意**按 12 位有效截断写的，两边读的是同一串截断过的数
    say(rel < 1e-6, '★★两个宿主落在同一个数上（同一支式子，各写各的六行）',
        `浏览器 ${(blk['fylite:i_p'] / 1e3).toFixed(6)} kA · `
        + `Python ${(py.edge / 1e3).toFixed(6)} kA · 相对差 ${rel.toExponential(2)}`);
  }
}

// === 〔丙〕解析几何：整块不出现 ==============================================

console.log('\n〔丙〕解析 Miller：解不出 ψ，这一块必须整块不在');
const b = await run('miller', 'evolve-iter-15ma', { nsteps: 10 });
say(/完成|Done/.test(b.state), '跑完了', b.state.trim().slice(0, 70));
say(b.doc['fylite:ip_from_psi'] === undefined,
    '★★读不出就整块不写（不是写一块 null、更不是写一个 0 冒充「算过了」）');
say(!b.rows.some((r) => /ψ 读出|read from psi/.test(r[0])),
    '读数里也没有这一行');

// === 〔丁〕回路本身：关掉跟不上，开着跟得上 ================================
//
// ★★一个只在「开着」时判的控制判据，判不出它有没有在工作——所以两次都跑，
// 而且判的是**同一个量在两次运行之间的差**。
// ★误差是**相对**的：从 ψ 读出的 I_p 在梯子上系统性低约 3 %，闭在绝对值上的
// 回路会稳稳驱到一个差 3 % 的 I_p 上。回路在第一步上自己标定，判据照着标定后的
// 相对误差判。

console.log('\n〔丁〕I_p 反馈：关掉与开着，跟得上跟不上');
//: ★把环电压推离平衡点，让电流真的偏离——否则「跟得上」是因为它本来就在那里
const OFF = { nsteps: 400, vloop: 0.6, ipctl: false };
const off = await run('ipctl-off', 'evolve-east-hmode', OFF);
//: ★增益**不在这里覆盖**：判的就是页面发出去的那一对缺省，否则闸子测的是
//: 一台读者拿不到的机器
const on = await run('ipctl-on', 'evolve-east-hmode', { ...OFF, ipctl: true });
const eOff = off.doc['fylite:ip_from_psi'];
const eOn = on.doc['fylite:ip_from_psi'];
say(!!eOff && !!eOn, '两次都写出了记录');
if (eOff && eOn) {
  const ctl = eOn['fylite:ip_control'];
  say(eOff['fylite:ip_control'] === null,
      '★关着时回路那一段是 null（不是一段填了零的记录）');
  say(!!ctl, '开着时回路那一段在，带着标定比与两个增益');
  //: 相对误差：两次都按开着那一次的标定比折算，才是同一把尺子
  const r0 = ctl ? ctl['fylite:calibration_ratio'] : 1;
  const relOff = Math.abs(eOff['fylite:i_p'] / (eOff['fylite:i_p_requested'] * r0) - 1);
  const relOn = Math.abs(eOn['fylite:i_p'] / (eOn['fylite:i_p_requested'] * r0) - 1);
  console.log(`        关着 ${(eOff['fylite:i_p'] / 1e3).toFixed(1)} kA（相对误差 `
              + `${(100 * relOff).toFixed(2)} %） · 开着 `
              + `${(eOn['fylite:i_p'] / 1e3).toFixed(1)} kA（`
              + `${(100 * relOn).toFixed(2)} %） · 标定比 ${r0.toFixed(4)}`);
  say(relOn < relOff, '★★开着比关着更接近请求电流（回路真的在工作）',
      `${(100 * relOn).toFixed(2)} % < ${(100 * relOff).toFixed(2)} %`);
  say(relOff > 0.02, '★关着时确实跟不上（否则这道判据判不出任何东西）',
      `${(100 * relOff).toFixed(2)} % > 2 %`);
  //: ★★立项判据就是「跟到 2 % 以内」，判它。
  //: ★★★而这里有一次**自己推翻自己**的记录，留着：第一次跑这一段时缺省增益
  //: 是 kp = 1 / ki = 0.2，终态差 28 %，当时的结论写的是「被控对象还没到，
  //: 电流扩散要若干个 τ_R，判 2 % 等于判等待时间」——**那个结论是错的**。
  //: 同一段窗口里开环电流从 400 kA 跑到 1229 kA，被控对象一点都不慢；慢的是
  //: 积分。逐档量过：ki = 0.2 → −28.2 %，ki = 2 → −2.0 %，**ki = 3 → −0.09 %**，
  //: 而收敛的几档稳态电压都落在 0.053 V（那就是真正的平衡点）。缺省因此改成
  //: kp = 2 / ki = 3，判据改回 2 %。
  //: ★教训与 §10.1 那条同源：**「判不动」先要排除「我把参数调坏了」**，
  //: 否则一条本来判得动的判据会被自己的手误改成一句记录。
  say(relOn < 0.02, '★★开着时跟到 2 % 以内（缺省增益）',
      `${(100 * relOn).toFixed(2)} %`);
  say(relOn < 0.2 * relOff, '★并且比开环小一个量级以上',
      `${(100 * relOn).toFixed(2)} % vs ${(100 * relOff).toFixed(2)} %`);
  const ctlSteps = ctl ? (ctl['fylite:steps'] || []) : [];
  if (ctlSteps.length > 20) {
    const errs = ctlSteps.map((x) => Math.abs(x['fylite:relative_error']));
    const head = errs.slice(0, 10).reduce((p2, q) => p2 + q, 0) / 10;
    const tail = errs.slice(-10).reduce((p2, q) => p2 + q, 0) / 10;
    //: ★误差确实在收敛——末十步的均值必须小于头十步。缺省增益下这一条成立；
    //: 它在 ki = 0.2 上不成立，那是增益的事，不是被控对象的事（见上）。
    say(tail < head, '★误差在收敛（末十步的均值小于头十步）',
        `${(100 * tail).toFixed(3)} % < ${(100 * head).toFixed(3)} %`);
    const vs = ctlSteps.map((x) => x['fylite:v_loop']);
    //: 这一档是电流**偏高**，所以正确的方向是把电压压下去
    say(vs[vs.length - 1] < vs[0], '★方向对（电流偏高时电压被压下去）',
        `${vs[0].toFixed(3)} → ${vs[vs.length - 1].toFixed(3)} V`);
  }
  if (ctl) {
    const steps = ctl['fylite:steps'] || [];
    say(steps.length > 3, '逐步记录在文件里', `${steps.length} 步`);
    const v = steps.map((x) => x['fylite:v_loop']);
    say(new Set(v.map((x) => x.toFixed(6))).size > 1,
        '★环电压确实被回路挪过（不是记了一串相同的数）',
        `${Math.min(...v).toFixed(3)} … ${Math.max(...v).toFixed(3)} V`);
    say(v.every((x) => x >= -1 - 1e-9 && x <= 5 + 1e-9),
        '★输出夹在环电压滑杆自己的量程里（积分不会绕到页面问不出的地方）');
  }
}

// === 〔己〕跟一条 I_p 时序，而不只是一个常数 ================================
//
// ★★立项判据写的是「给定 I_p **波形**」。一条只会按住常数的回路，跟的是一条
// 退化的时序——上游控的是 `pulse_schedule` 里的 I_p 时序，所以这里把目标挂到
// 波形上，判它跟得上**动着的**那个目标。

console.log('\n〔己〕I_p 目标跟随波形（不只是一个常数）');
const wav = await run('ipctl-wave', 'evolve-east-hmode',
                      { nsteps: 400, vloop: 0.6, ipctl: true,
                        wave: true, waveip: true,
                        waveramp: 0.5, waveflat: 1.5, waveend: 2.5,
                        wavestart: 0.5, waveend2: 1.0 });
const ew = wav.doc['fylite:ip_from_psi'];
say(!!ew && !!ew['fylite:ip_control'], '波形那一次也写出了回路记录');
if (ew && ew['fylite:ip_control']) {
  const st2 = ew['fylite:ip_control']['fylite:steps'] || [];
  const tg = st2.map((x) => x['fylite:target']);
  const lo = Math.min(...tg), hi = Math.max(...tg);
  say(hi / lo > 1.3, '★目标确实在动（不是一条退化的常数时序）',
      `${(lo / 1e3).toFixed(1)} … ${(hi / 1e3).toFixed(1)} kA`);
  const last = st2[st2.length - 1];
  const relW = Math.abs(last['fylite:relative_error']);
  say(relW < 0.02, '★★末步跟到 2 % 以内（目标是动着的那个）',
      `${(100 * relW).toFixed(2)} %`);
  //: ★误差在动目标上应当整体也小：取后四分之一的均值，避免拿单点当结论
  const tailErr = st2.slice(-Math.floor(st2.length / 4))
    .map((x) => Math.abs(x['fylite:relative_error']));
  const mean = tailErr.reduce((p2, q) => p2 + q, 0) / tailErr.length;
  say(mean < 0.05, '★后四分之一的平均误差也在 5 % 以内',
      `${(100 * mean).toFixed(2)} %`);
}

// === 〔戊〕两样缺一件就拒绝 =================================================

console.log('\n〔戊〕没有电流道 / 没有可读的 ψ 时，回路必须拒绝');
const refused = await run('ipctl-miller', 'evolve-iter-15ma',
                          { nsteps: 5, ipctl: true }, { noExport: true });
say(/失败|Failed/.test(refused.state),
    '★解析几何上开回路 → 失败，不是悄悄开环跑',
    refused.state.trim().slice(0, 90));

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);

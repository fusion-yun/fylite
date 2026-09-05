// The impurity in the quasi-neutrality — the composition the march ran on.
//
// ★★What this replaces.  Z_eff entered the resistivity, the radiation and
// the bootstrap while the main ion stayed undiluted (n_i = n_e), so a plasma
// declared at Z_eff = 1.7 had the fusion rate and the ion heat capacity of a
// pure hydrogenic one.  Every number in it was smooth, ordered and wrong in
// the same direction — which is why the page reported the implication and
// applied nothing until a reader asked.
//
// Three things have to hold and none of them shows up as an error:
//
//   the DILUTION is the kernel's, not a formula written again here;
//   the COMPOSITION closes — n_i + Z n_z is the electron density asked for,
//   which is the closure the core march applies to its own ion list;
//   the FUEL FRACTION follows the dilution rather than the slider, because
//   the alphas go as f squared and the slider is still on the page.
//
// ★And one refusal: a Z_eff this impurity cannot make (floored, it would be
// a composition nobody chose).
//
// ★★T-C20 取消了第二条拒绝（「粒子道开着时不做稀释」），而取消它的**不是放宽**
// ——是把缺的两件补上：闭包按 `n_ion × n` 开了空间却只填第一种离子，源也只填
// 第一块，杂质拿到的是 D = 0、v = 0（冻住，不是「不输运」）。补上之后那条拒绝
// 的**理由本身**不成立：两种离子都是道时，`n_e = Σ Z_s n_s` 是准中性的答案，
// **Z_eff 是结果**，没有两套成分要裁决。第四段判的就是这件事，而且判的是
// 「杂质真的动了」——换掉它自己的 D_z 与箍缩，n_z 必须看得见地变。
//
//   node app/tests/validate-composition.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'cm-'));
let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

const ZEFF = 1.7, SPECIES = 'Be';
const CFG = {
  geometry: 'miller', 'ch-heat': true, 'ch-density': false,
  'ch-current': false, nsteps: 20, nlev: 31, dt: 0.01, dttarget: 0,
  pe: 16.5, pi: 16.5, dep: 0, depw: 0.35, fuel: 0,
  alpha: true, brem: true, ohmic: false, bootstrap: false, icd: 0,
  zeff: ZEFF, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
  closure: 0, chi0: 0.6, te0: 8, ti0: 8, edgete: 3.0, edgeti: 3.0,
  edgene: 3.0, ne0: 10, peakt: 1.5, peakn: 0.4, vloop: 0, ip: 15000,
  useref: false, sawtooth: false, wave: false, resume: false,
  amin: 2.0, rmaj: 3.1, kappa: 1.70, delta: 0.34, q95: 3.0, bunit: 5.3,
  species: SPECIES, cimp: 1.65, dtfrac: 0.375,
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
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  //: ★★`/api/*` 上的 404 **不是错误，是答案**（2026-09-05）：静态宿主没有请求面，页面据此
  //: 判断该走 wasm（`factsdb.js` / `kernelapi.js` 探的就是这件事——探「这条路答不答」，
  //: 不看主机名）。发布出去的站点不在回环地址上，一个探测也不发；本地静态服务器上那几条
  //: 404 是这套判别的正常足迹，不该让「页面没有报错」变红。
  if (m.type() === 'error' && !/favicon/.test(m.text())
      && !/\/api\//.test((m.location() && m.location().url) || ''))
    errs.push('console: ' + m.text().slice(0, 200));
});
await page.goto(BASE + 'pages/model.html?device=east',
                { waitUntil: 'networkidle' });
//: ★★等**留得住的信号**，不等状态行（2026-09-05 真浏览器实测改）。这里从前等的是
//: 状态行里出现「就绪 / Ready」，而那句话在页面上只存在一瞬：各栏的初始状态紧接着把它
//: 换成自己的（实测 0.49 s 时已是「待机——摆好目标，合开关起放电」，`status.kernel_ready`
//: 在 MutationObserver 里一次痕迹也没留下）。于是这一等就是 180 秒的超时，而**页面本身
//: 一直是好的**——`FyDesignReady` 与 `FYLITE_KERNEL` 都按时到位。状态行是给读者看的：
//: 它会改词、会被覆盖、还随语言变，判据挂在它上面就是把闸子挂在措辞上。
await page.waitForFunction(() => !!self.FYLITE_KERNEL, null, { timeout: 180000 });

const set = (cfg) => page.evaluate((c) => {
  Object.keys(c).forEach((id) => {
    const el = document.getElementById('model-evolve-' + id)
               || document.getElementById('model-' + id);
    if (!el) throw new Error('no control ' + id);
    if (el.type === 'checkbox') el.checked = !!c[id];
    else el.value = c[id];
    el.dispatchEvent(new Event(el.tagName === 'SELECT' || el.type === 'checkbox'
                               ? 'change' : 'input'));
  });
}, cfg);
const wait = () => page.waitForFunction(
  () => /完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 900000 });
const state = () => page.evaluate(() =>
  (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
    .textContent || '');
let n = 0;
const grab = async () => {
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${n++}.json`);
  await dl.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
};

// --- 1. not applied --------------------------------------------------------

console.log('一、不进准中性（旧行为，仍然可用）');
await set({ ...CFG, quasi: false });
await page.click('#model-evolve-run');
await wait();
const offDoc = await grab();
const offCp = offDoc['fylite:result'].core_profiles.profiles_1d;
const offImp = offDoc['fylite:result'].core_profiles['fylite:impurity'];
say(offImp && offImp['fylite:applied'] === false,
    '文件说这条杂质没有被施加');
const offAlpha = offDoc['fylite:result'].summary.fusion.power.value;
say(offCp['fylite:ion_density'].every((v, i) =>
      Math.abs(v - offCp.electrons.density[i]) < 1e-6 * v),
    '主离子未被稀释：n_i = n_e');

// --- 2. applied ------------------------------------------------------------

console.log('\n二、进准中性');
await set({ ...CFG, quasi: true });
await page.click('#model-evolve-run');
await wait();
const onDoc = await grab();
const cp = onDoc['fylite:result'].core_profiles.profiles_1d;
const imp = onDoc['fylite:result'].core_profiles['fylite:impurity'];
const ne = cp.electrons.density, ni = cp['fylite:ion_density'];
const nz = imp['fylite:n_z'];
say(imp['fylite:applied'] === true, '文件说这条杂质被施加了');

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import kernel as K
d = json.load(sys.stdin)
ne = np.asarray(d["ne"], float)
#: ★the dilution is the KERNEL's, asked for again rather than re-derived
ni_want = K.ion_dilution(ne, zeff=${ZEFF}, z_imp=d["z"])
#: ...and the closure the core march applies to its own ion list
ne_back = K.quasi_neutral_ne([1.0, d["z"]],
                             np.vstack([np.asarray(d["ni"], float),
                                        np.asarray(d["nz"], float)]))
print(json.dumps({
  "ni_rel": float(np.max(np.abs(np.asarray(d["ni"], float) - ni_want)
                         / np.maximum(ni_want, 1e-30))),
  "ne_rel": float(np.max(np.abs(ne_back - ne) / np.maximum(ne, 1e-30))),
  "dilution": float(ni_want[0] / ne[0]),
}))
`;
const chk = JSON.parse(execFileSync('python3', ['-c', PY], {
  input: JSON.stringify({ ne, ni, nz, z: imp['fylite:z'] }),
  encoding: 'utf8' }));
say(chk.ni_rel < 1e-6, '主离子密度就是内核的 ion_dilution',
    `最大相对差 ${chk.ni_rel.toExponential(1)}`);
//: ★★THE COMPOSITION CLOSES.  This is the closure the core march applies to
//: whatever ion list it is handed, so a mix that failed it would be a plasma
//: with net charge and no warning anywhere.
say(chk.ne_rel < 1e-6, 'n_i + Z n_z 就是要的那条 n_e',
    `最大相对差 ${chk.ne_rel.toExponential(1)}`);
say(Math.abs(imp['fylite:dilution'] - chk.dilution) < 1e-6,
    '文件里的稀释与实算一致', imp['fylite:dilution'].toFixed(4));
//: ★the fuel fraction FOLLOWS the dilution: n_D = n_T = n_i/2.  The slider
//: is still on the page and is disabled, and this is why.
say(Math.abs(imp['fylite:dt_fraction'] - chk.dilution / 2) < 1e-6,
    '燃料占比 = 稀释的一半，而不是滑块上的数',
    `${imp['fylite:dt_fraction'].toFixed(4)} (滑块 ${CFG.dtfrac})`);
const onAlpha = onDoc['fylite:result'].summary.fusion.power.value;
say(Math.abs(onAlpha[onAlpha.length - 1] - offAlpha[offAlpha.length - 1])
      > 0.01 * offAlpha[offAlpha.length - 1],
    'α 功率确实变了（f 变了，α 走 f²）',
    `${(offAlpha[offAlpha.length - 1] / 1e6).toFixed(2)} → ${(onAlpha[onAlpha.length - 1] / 1e6).toFixed(2)} MW`);

// --- 3. the refusals -------------------------------------------------------

console.log('\n三、两条拒绝');
await set({ ...CFG, quasi: true, zeff: 4.0 });
await page.click('#model-evolve-run');
await wait();
const st1 = await state();
say(/配不出来|cannot be made/.test(st1),
    'Z_eff 高过 Z_imp：拒绝而不是取下限', st1.replace(/\s+/g, ' ').slice(0, 80));

//: ★★★这里原本是第二条拒绝：「粒子道开着时这一档被禁用」。**T-C20 把它取消
//: 了**，而取消它的不是放宽，是把缺的那两件补上——闭包按 `n_ion × n` 开了
//: 空间却只填第一种离子，源也只填第一块，所以杂质拿到 D = 0、v = 0，等于被
//: 冻住。补上之后那条拒绝的**理由本身**不成立了：两种离子都是道时，
//: `n_e = Σ Z_s n_s` 是准中性的答案，**Z_eff 是结果**，没有两套成分要裁决。
console.log('\n四、T-C20：杂质真的在演化，Z_eff 是结果');
//: ★★这一炮**两边都不加料**（`fuel: 0`, `zfuel: 0`），而那不是省事：
//: 输运相同、两边都无源，n_z/n_i 才逐点守恒，Z_eff 才**必须**恰好不动。
//: ★闸子上一轮就是在这里判红的，而红得对——当时主离子有加料而杂质没有，
//: 于是加料的地方 n_i 涨、n_z 不涨，Z_eff 掉了 1e-3。那是**物理**，不是缺陷，
//: 所以判据改成把这两件分开判：先判守恒，再单判源真的接上了。
await set({ ...CFG, zeff: ZEFF, quasi: true, 'ch-density': true,
            fuel: 0, zfuel: 0 });
const boxed = await page.evaluate(() => ({
  disabled: document.getElementById('model-evolve-quasi').disabled,
  note: (document.getElementById('model-evolve-quasi-note') || {}).textContent || '',
  dz: document.getElementById('model-evolve-dchiz').disabled,
  vz: document.getElementById('model-evolve-pinchz').disabled,
  sz: document.getElementById('model-evolve-zfuel').disabled,
}));
say(!boxed.disabled, '★★粒子道开着时这一档**不再被禁用**（缺的两件已经补上）');
say(/结果|RESULT/.test(boxed.note),
    '★并且说清了 Z_eff 此时是**结果**、滑杆只定起始成分',
    boxed.note.replace(/\s+/g, ' ').slice(0, 70));
say(!boxed.dz && !boxed.vz && !boxed.sz,
    '★杂质自己的 D_z / 箍缩 / 加料三个控件在这一档上可用');

//: ★★判的是「杂质真的动了」，不是「跑完了」。两次同样的运行，只把杂质的
//: D_z 换掉——**一个冻住的杂质会给出逐位相同的 n_z**，那正是这一段存在的理由。
await page.click('#model-evolve-run');
await wait();
const zDoc = await grab();
const zImp = zDoc['fylite:result'].core_profiles['fylite:impurity'];
const nz1 = zImp['fylite:n_z'];
say(zImp['fylite:z_eff_solved'] === true,
    '★★文件里写明 Z_eff 是解出来的（不是滑杆那个数铺平）');
const zp = zImp['fylite:z_eff_profile'];
say(Array.isArray(zp) && zp.length === nz1.length,
    '★逐面的 Z_eff 进了文件', zp ? `${zp.length} 个面` : '（没有）');
//: ★★★这一条闸子第一次跑时**判反了**，而判反的方式正好是它该判的东西。
//: 我原本断言「Z_eff 不是一条平的」，可这一炮里两种离子拿的是**同一个** D 与
//: 同一个 v（缺省相同），杂质也没有源——那么 n_z/n_i 逐点守恒，Z_eff **必须**
//: 恰好是起始那个数。平的才是对的。★所以这里判的是这一条：**输运相同 →
//: Z_eff 逐位不动**，而下面那一炮把 D_z 与箍缩换掉之后 **Z_eff 必须动**。
//: 两条一起，才是「杂质真的在按自己的输运走」的判据；单judg一条都判不出来。
const zSpread = zp ? Math.max(...zp) - Math.min(...zp) : NaN;
say(zp && zSpread < 1e-6,
    '★★两种离子输运相同时 Z_eff 恰好不动（n_z/n_i 逐点守恒）',
    zp ? `${Math.min(...zp).toFixed(6)} … ${Math.max(...zp).toFixed(6)}`
       + `（起始 ${ZEFF}）` : '');
say(zp && Math.abs(zp[0] - ZEFF) < 1e-3,
    '★而且它就是起始那个数（滑杆此时只定起始成分）',
    zp ? zp[0].toFixed(6) : '');

//: ★★杂质自己的源真的接上了没有——`evSourceFlat` 从前把第二块留成零，而
//: 那句注释（「the impurity has none」）读起来像物理，其实是接线。
//: ★速率取控件量程的上限（5），不是为了让数字好看，是因为这一段判的是
//: 「这一块源接上了没有」：0.5 时 n_z 只动 0.6 %，与「接上了但很小」和
//: 「没接上而这是别的东西」区分不开。判据要判得动，就把它推到判得动的地方。
await set({ ...CFG, zeff: ZEFF, quasi: true, 'ch-density': true,
            fuel: 0, zfuel: 5 });
await page.click('#model-evolve-run');
await wait();
const zDocS = await grab();
const impS = zDocS['fylite:result'].core_profiles['fylite:impurity'];
const nzS = impS['fylite:n_z'];
const dNzS = Math.max(...nz1.map((v, i) => Math.abs(nzS[i] / v - 1)));
say(dNzS > 0.01,
    '★★杂质加料速率真的进了它自己那一块源（从前那一块恒为零）',
    `最大相对差 ${(100 * dNzS).toFixed(1)} %`);
const zpS = impS['fylite:z_eff_profile'];
say(zpS && Math.max(...zpS) > ZEFF + 1e-3,
    '★而且加进去的杂质把 Z_eff 抬起来了（成分变了）',
    zpS ? `${Math.min(...zpS).toFixed(4)} … ${Math.max(...zpS).toFixed(4)}` : '');

await set({ ...CFG, zeff: ZEFF, quasi: true, 'ch-density': true,
            fuel: 0, zfuel: 0, dchiz: 1.2, pinchz: -1.5 });
await page.click('#model-evolve-run');
await wait();
const zDoc2 = await grab();
const nz2 = zDoc2['fylite:result'].core_profiles['fylite:impurity']['fylite:n_z'];
const dNz = Math.max(...nz1.map((v, i) => Math.abs(nz2[i] / v - 1)));
say(dNz > 0.01,
    '★★★换掉杂质自己的 D_z 与箍缩，n_z **看得见地变了**（冻住的杂质不会）',
    `最大相对差 ${(100 * dNz).toFixed(1)} %`);
//: ★而主离子的那两个控件没有动过——所以变的是杂质那一条道，不是整锅
const ne1 = zDoc['fylite:result'].core_profiles.profiles_1d.electrons.density;
const ne2 = zDoc2['fylite:result'].core_profiles.profiles_1d.electrons.density;
const dNe = Math.max(...ne1.map((v, i) => Math.abs(ne2[i] / v - 1)));
say(dNe > 0, '★n_e 跟着动（它是 Σ Z_s n_s，不是一条独立的道）',
    `最大相对差 ${(100 * dNe).toFixed(2)} %`);
//: ★★★而 Z_eff 这一炮**必须**动：两种离子不再同步，成分就不再是起始那一套。
//: 这是上面那条「输运相同则不动」的另一半——单判一条都判不出「杂质在按自己
//: 的输运走」。
const zp2 = zDoc2['fylite:result'].core_profiles['fylite:impurity']['fylite:z_eff_profile'];
const spread2 = zp2 ? Math.max(...zp2) - Math.min(...zp2) : NaN;
say(zp2 && spread2 > 1e-3,
    '★★★输运不同时 Z_eff 逐面地动了（成分是解出来的，不是钉住的）',
    zp2 ? `${Math.min(...zp2).toFixed(4)} … ${Math.max(...zp2).toFixed(4)}`
        + `（起始 ${ZEFF}）` : '');

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);

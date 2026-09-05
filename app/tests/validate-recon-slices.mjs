// 现读一炮的存储片表：画得出、点得动、试过的标得上（T-A21）
//
// ★★WHAT THIS CLOSES.  The reconstruction bar can read a slice off the
// institute's MDSplus server, and the slices of one shot do NOT all converge —
// measured on #165704: 2.083 s fits, 3.933 s and 5.968 s do not, on data that
// is complete in all three.  That is a fact about the discharge rather than a
// fault in the fetch, and until this batch the reader's only way to try
// another slice was to retype a number and press the button again, with no
// record of what had already been tried.
//
// ★★AND WHY IT DOES NOT NEED A GATEWAY.  What is under test is the PAGE: the
// endpoint already answers with `times`, and this gate hands the page exactly
// that answer through `page.route`, canned from the deck's own reference
// discharge.  Running a real gateway (and a fake mdsip behind it) would put
// two more processes between the assertion and the thing asserted — the
// server side has its own gates (`validate-mds.mjs`).
//
// ★The canned slices are the SHIPPED shot's channels scaled by a ramp, so one
// slice is the discharge this repository distributes and the others are not
// the same measurement.  ★WHETHER A GIVEN SLICE CONVERGES IS NOT ASSERTED and
// must not be: a live slice is fitted on the RAW total-flux basis with the
// coils fitted, which is a different question from the one the shipped
// delivered-basis reference answers, and either verdict is a real answer.
// What is asserted is that the mark and the status line say the SAME thing.
//
//   node app/tests/validate-recon-slices.mjs [--playwright DIR] [--chrome BIN]
//                                            [--url BASE]

import { readFileSync } from 'node:fs';
import { browser, flag } from './_browser.mjs';
import { deviceDoc, seedDevice, missingDeviceMessage } from './_device.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

const DECK = deviceDoc('east');
if (!DECK) { console.error(missingDeviceMessage('east')); process.exit(2); }
const REF = DECK['fylite:reference_discharge'];
if (!REF || !REF.loopMeasTotal) {
  console.error('EAST 的卷宗里没有参考放电，这道闸子没有可发的通道值。');
  process.exit(2);
}

//: the stored-slice table this fake shot has.  61 instants at 0.1 s — a real
//: EAST EFIT record is denser, and the number is not what is under test; what
//: is under test is that the page draws THIS table and reads back the slice a
//: click lands on.
const TIMES = Array.from({ length: 61 }, (_, i) => +(i * 0.1).toFixed(3));
const AT_REF = TIMES.indexOf(4);

/** 0 before 0.4 s, 1 from 1.8 to 4.4, down again by 5.2 — a discharge shape. */
function ramp(t) {
  if (t <= 0.4 || t >= 5.2) return 0;
  if (t < 1.8) return (t - 0.4) / 1.4;
  if (t <= 4.4) return 1;
  return (5.2 - t) / 0.8;
}
const scaleAt = (t) => 0.2 + 0.8 * ramp(t);

function measurements(shot, want) {
  let at = 0;
  for (let i = 1; i < TIMES.length; i++)
    if (Math.abs(TIMES[i] - want) < Math.abs(TIMES[at] - want)) at = i;
  const k = scaleAt(TIMES[at]) / scaleAt(TIMES[AT_REF]);
  //: ★the tree carries 76 probe channels while the deck describes 79 — the
  //: page pads the three and weights them zero, and a canned answer that
  //: handed over 79 would step around exactly that path
  const probes = REF.probeMeas.slice(0, 76).map((v) => v * k);
  return {
    server: 'canned', tree: 'efit_east', shot,
    time_requested: want, time_s: TIMES[at], slice_index: at,
    slices: TIMES.length, times: TIMES,
    loops: REF.loopMeasTotal.map((v) => v * k),
    probes,
    aturns: REF.aturns.slice(0, 12).map((v) => v * k),
    ip: REF.ipMeasured * k,
    bcentr: REF.bcentr,
    counts: { loops: REF.loopMeasTotal.length, probes: probes.length, coils: 12 },
    probe_gate: { min_tesla: 0.02, max_tesla: 1.0 },
    provenance: { nodes: {}, kind: 'canned from the shipped reference discharge' },
  };
}

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', viewport: { width: 1440, height: 1100 } });
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}

//: every request the source panel makes, answered here — and RECORDED, so the
//: gate can assert which slice a click actually asked for rather than
//: inferring it from what the page then printed
const asked = [];
await ctx.route('**/api/health', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json',
                  body: JSON.stringify({ mdsip: 'canned:0', ok: true }) }));
await ctx.route('**/api/measurements*', (route) => {
  const u = new URL(route.request().url());
  const shot = Number(u.searchParams.get('shot'));
  const want = Number(u.searchParams.get('time'));
  asked.push({ shot, want });
  route.fulfill({ status: 200, contentType: 'application/json',
                  body: JSON.stringify(measurements(shot, want)) });
});

const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
await page.goto(BASE + 'pages/analysis.html?device=east', { waitUntil: 'networkidle' });
//: the page's own status line, the same one `validate-recon.mjs` waits on
//: ★★等**留得住的信号**，不等状态行（2026-09-05 真浏览器实测改）。这里从前等的是
//: 状态行里出现「就绪 / Ready」，而那句话在页面上只存在一瞬：各栏的初始状态紧接着把它
//: 换成自己的（实测 0.49 s 时已是「待机——摆好目标，合开关起放电」，`status.kernel_ready`
//: 在 MutationObserver 里一次痕迹也没留下）。于是这一等就是 180 秒的超时，而**页面本身
//: 一直是好的**——`FyDesignReady` 与 `FYLITE_KERNEL` 都按时到位。状态行是给读者看的：
//: 它会改词、会被覆盖、还随语言变，判据挂在它上面就是把闸子挂在措辞上。
await page.waitForFunction(() => !!self.FYLITE_KERNEL, null, { timeout: 180000 });

const strip = '#reconstruction-mds-slices';
const readAt = async (shot, t) => {
  await page.fill('#reconstruction-mds-shot', String(shot));
  await page.fill('#reconstruction-mds-time', String(t));
  await page.click('#reconstruction-mds-read');
  await page.waitForFunction(
    () => /已读入|Read/.test(
      (document.getElementById('reconstruction-mds-note') || {}).textContent || ''),
    null, { timeout: 60000 });
};

const stripState = () => page.evaluate(() => ({
  hidden: !!(document.getElementById('reconstruction-mds-slices') || {}).hidden,
  summary: ((document.getElementById('reconstruction-mds-slices-note') || {})
             .textContent || '').trim(),
  width: (document.getElementById('reconstruction-mds-slices') || {}).clientWidth,
}));

//: --- read one slice, and the table must appear ---------------------------
await readAt(137985, 4.0);
const first = await stripState();

//: --- click a mark, and THAT slice is what gets read ----------------------
//: the click lands at the x of a chosen index, computed the way the strip
//: lays them out (10 px padding, first to last across the box)
const PICK = 20;
const box = await page.locator(strip).boundingBox();
const xOf = (i) => box.x + 10 + (box.width - 20) * (i / (TIMES.length - 1));
await page.mouse.click(xOf(PICK), box.y + box.height / 2);
await page.waitForFunction(
  (t) => new RegExp('实得 ' + t + '|got ' + t).test(
    (document.getElementById('reconstruction-mds-note') || {}).textContent || ''),
  TIMES[PICK].toFixed(3), { timeout: 60000 }).catch(() => {});
const afterClick = await page.evaluate(() => ({
  note: (document.getElementById('reconstruction-mds-note') || {}).textContent || '',
  time: (document.getElementById('reconstruction-mds-time') || {}).value,
}));

//: --- hover a mark that has not been tried --------------------------------
await page.mouse.move(xOf(PICK + 5), box.y + box.height / 2);
const hoverUntried = await page.evaluate(() =>
  ((document.getElementById('reconstruction-mds-hover') || {}).textContent || '').trim());

//: --- run the fit on the slice that is loaded, then look at the mark ------
const RUN = '#analysis-reconstruction-run';
await page.waitForFunction(
  () => !document.getElementById('analysis-reconstruction-run')
          .classList.contains('stop'), null, { timeout: 300000 });
await page.click(RUN);
await page.waitForFunction(
  () => /重构完成|converged|失败|fail/i.test(
    (document.getElementById('analysis-status') || {}).textContent || ''),
  null, { timeout: 900000 });
const verdictLine = await page.evaluate(() =>
  (document.getElementById('analysis-status') || {}).textContent || '');
await page.mouse.move(xOf(PICK), box.y + box.height / 2);
const hoverTried = await page.evaluate(() =>
  ((document.getElementById('reconstruction-mds-hover') || {}).textContent || '').trim());
const summaryTried = (await stripState()).summary;

//: --- another shot, and back: the verdicts are the SHOT's -----------------
await readAt(137984, 2.0);
const otherShot = await stripState();
await readAt(137985, 4.0);
await page.mouse.move(xOf(PICK), box.y + box.height / 2);
const hoverBack = await page.evaluate(() =>
  ((document.getElementById('reconstruction-mds-hover') || {}).textContent || '').trim());

await br.close();

// --- assertions ------------------------------------------------------------

let bad = 0, n = 0;
const ok = (cond, what, detail) => {
  n += 1;
  if (!cond) { bad += 1; console.log('  ✗ ' + what + (detail ? ' — ' + detail : '')); }
  else console.log('  ✓ ' + what + (detail ? ' — ' + detail : '')); };

console.log('\n〔一〕取回之后，这一炮的存储片表画得出来');
ok(!first.hidden && first.width > 0, '片表是画出来的，不是一句「共 N 片」',
   `${first.width} px`);
ok(new RegExp('\\b' + TIMES.length + '\\b').test(first.summary),
   `说的是这一炮的片数（${TIMES.length}）`, first.summary.slice(0, 40) + '…');

console.log('\n〔二〕点一下就换一片——这是这一条待办的全部内容');
const last = asked[asked.length - 1];
ok(asked.length >= 2, '点击确实发出了第二次取数', `${asked.length} 次`);
ok(last && Math.abs(last.want - TIMES[PICK]) < 0.051,
   '而且要的是点中的那一片的时刻',
   `点第 ${PICK} 片（${TIMES[PICK]} s），请求 ${last && last.want} s`);
ok(afterClick.time === TIMES[PICK].toFixed(3),
   '时刻框跟着走（读者看得见自己点了哪一片）', afterClick.time);
ok(new RegExp(TIMES[PICK].toFixed(3)).test(afterClick.note),
   '取回的注记写的是那一片', afterClick.note.slice(0, 48) + '…');

console.log('\n〔三〕试过的片按「收敛 / 失败 + 原因」标在片上');
ok(/未试过|not tried/.test(hoverUntried),
   '没试过的片说自己没试过，而不是留白', hoverUntried.slice(0, 40));
const converged = /重构完成|converged/.test(verdictLine);
ok(/收敛|converged|失败|failed/.test(hoverTried),
   '试过的片带上了判决', hoverTried.slice(0, 60));
ok(converged ? /收敛|converged/.test(hoverTried) : /失败|failed/.test(hoverTried),
   '而且与状态行说的是同一件事（不是第二个意见）',
   `状态行「${verdictLine.slice(0, 28)}…」`);
ok(summaryTried !== first.summary
   && new RegExp((converged ? '1' : '0') + '[^0-9]{0,24}' + (converged ? '0' : '1'))
        .test(summaryTried.replace(/\s+/g, ' ')),
   '汇总行数得对（收敛几片 / 失败几片）',
   summaryTried.replace(/\s+/g, ' ').slice(0, 80) + '…');

console.log('\n〔四〕判决是那一炮的：换一炮不继承，换回来还在');
ok(!/收敛|converged/.test(otherShot.summary) || /137984/.test(otherShot.summary),
   '另一炮的汇总说的是另一炮', otherShot.summary.slice(0, 46) + '…');
ok(/收敛|converged|失败|failed/.test(hoverBack),
   '换回原来那一炮，它的判决还在', hoverBack.slice(0, 48));

console.log('\n〔五〕页面没有报错');
ok(!errs.length, '控制台干净', errs.slice(0, 2).join(' | '));

console.log(`\n判定：${bad ? bad + ' / ' + n + ' 条不符' : n + ' 条全过'}`);
process.exit(bad ? 1 : 0);

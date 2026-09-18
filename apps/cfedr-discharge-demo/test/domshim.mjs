// 极小 DOM 垫片：只为在 node 里把页面脚本**跑一遍**（init + 载入输出），抓运行期错误。
export function makeDom() {
  const store = new Map();
  const mk = (id = "") => {
    const el = {
      id, innerHTML: "", textContent: "", value: "", checked: false, hidden: false, disabled: false,
      style: {}, dataset: {}, files: [], classList: { contains: () => false, add() {}, remove() {} },
      _attrs: new Map(), _events: new Map(),
      setAttribute(k, v) { this._attrs.set(k, String(v)); },
      getAttribute(k) { return this._attrs.has(k) ? this._attrs.get(k) : null; },
      removeAttribute(k) { this._attrs.delete(k); },
      addEventListener(k, fn) { (this._events.get(k) || this._events.set(k, []).get(k)).push(fn); },
      removeEventListener() {},
      _kids: new Map(),
      querySelector(sel) { if (!this._kids.has(sel)) this._kids.set(sel, mk(this.id + sel)); return this._kids.get(sel); },
      querySelectorAll() { return []; },
      appendChild(x) { return x; }, remove() {},
      click() { this.fire("click"); }, select() {},
      setPointerCapture() {}, releasePointerCapture() {},
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 520, height: 190 }),
      fire(kind, ev = {}) { for (const fn of (this._events.get(kind) || [])) fn({ preventDefault() {}, stopPropagation() {}, target: this, ...ev }); },
    };
    return el;
  };
  const document = {
    getElementById(id) { if (!store.has(id)) store.set(id, mk(id)); return store.get(id); },
    createElement: () => mk(),
    documentElement: mk("html"),
    body: mk("body"),
    addEventListener() {},
  };
  const localStorage = { _m: new Map(), getItem(k) { return this._m.has(k) ? this._m.get(k) : null; }, setItem(k, v) { this._m.set(k, v); } };
  return { document, localStorage, store, mk };
}

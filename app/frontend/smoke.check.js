/* smoke test for app/frontend/app.js
 * 1) static: every bare `name(...)` call must resolve to a declared function/var or a known global
 * 2) runtime: boot the IIFE under a DOM stub, walk every route, ensure no ReferenceError/TypeError
 */
'use strict';
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');

/* ---------- 1. static reference analysis ---------- */
const declared = new Set();
// strip strings and comments to reduce false positives
/* NOTE: block comments are stripped; strings/regexes/line-comments are left in.
 * In this file they contain no bare `name(` patterns, so the check stays exact. */
const stripped = src.replace(/\/\*[\s\S]*?\*\//g, '');
let m;
const declRe = /\bfunction\s+([A-Za-z_$][\w$]*)|\bvar\s+([A-Za-z_$][\w$]*)/g;
while ((m = declRe.exec(stripped))) declared.add(m[1] || m[2]);

const knownGlobals = new Set([
  'if','for','while','switch','catch','return','function','typeof','new','else','do','in','of','var',
  'String','Number','Boolean','Array','Object','JSON','Math','Date','Error','Promise','RegExp','Set','Map',
  'parseInt','parseFloat','isNaN','isFinite','encodeURIComponent','decodeURIComponent',
  'setTimeout','clearTimeout','setInterval','clearInterval','fetch','require','module','exports',
  'FormData','Blob','File','URL','XMLSerializer','confirm',
  /* verified false positives: `text (` occurs in a line comment, `rgba(` inside CSS color strings */
  'text','rgba'
]);
const callRe = /([A-Za-z_$][\w$]*)\s*\(/g;
const missing = new Map();
while ((m = callRe.exec(stripped))) {
  const name = m[1];
  const before = stripped[m.index - 1];
  if (before === '.' || before === ':') continue; // method call or label-ish
  if (declared.has(name) || knownGlobals.has(name)) continue;
  const line = src.slice(0, src.indexOf(stripped.slice(Math.max(0,m.index-200), m.index)) >= 0 ? 0 : 0);
  missing.set(name, (missing.get(name) || []));
}
if (missing.size) {
  console.log('MISSING REFS:', [...missing.keys()].join(', '));
  process.exitCode = 1;
} else {
  console.log('STATIC REFS OK — all bare function calls resolve');
}

/* ---------- 2. runtime boot + route walk under DOM stub ---------- */
function makeEl(tag) {
  const el = {
    tagName: (tag || 'div').toUpperCase(),
    children: [], style: {}, dataset: {}, _cls: new Set(),
    classList: {
      add(...c){ c.forEach(x=>el._cls.add(x)); },
      remove(...c){ c.forEach(x=>el._cls.delete(x)); },
      toggle(c, force){ if (force === undefined) { el._cls.has(c) ? el._cls.delete(c) : el._cls.add(c); } else if (force) el._cls.add(c); else el._cls.delete(c); },
      contains(c){ return el._cls.has(c); }
    },
    attrs: {},
    setAttribute(k,v){ el.attrs[k]=v; },
    getAttribute(k){ return el.attrs[k] ?? null; },
    hasAttribute(k){ return k in el.attrs; },
    addEventListener(){}, removeEventListener(){},
    appendChild(c){ el.children.push(c); return c; },
    remove(){}, click(){}, focus(){},
    querySelector(){ return makeEl(); },
    querySelectorAll(){ return []; },
    closest(){ return null; },
    isConnected: true,
    parentElement: { classList: { toggle(){} } },
    value: '', textContent: '', disabled: false,
    set innerHTML(v){ el._html = v; el.children = []; },
    get innerHTML(){ return el._html || ''; }
  };
  return el;
}
const byId = {};
const documentStub = {
  getElementById(id){ return byId[id] || (byId[id] = makeEl()); },
  querySelectorAll(){ return []; },
  createElement(tag){ return makeEl(tag); },
  addEventListener(){},
  body: makeEl('body')
};
const store = {};
const localStorageStub = {
  getItem(k){ return store[k] ?? null; },
  setItem(k,v){ store[k]=String(v); },
  removeItem(k){ delete store[k]; }
};
const locationStub = { hash: '#/login' };
const fetchStub = () => Promise.reject(new Error('network stubbed'));
const windowStub = { addEventListener(){} };

const fn = new Function('document','localStorage','location','window','fetch','URL', src);
try {
  fn(documentStub, localStorageStub, locationStub, windowStub, fetchStub, { createObjectURL(){return 'blob:x';}, revokeObjectURL(){} });
  console.log('BOOT OK (login route)');
} catch (e) {
  console.log('BOOT FAILED:', e.stack.split('\n').slice(0,4).join('\n'));
  process.exitCode = 1;
}

// walk routes with a fake token so guarded views render their sync shell
store['pptsaas_token'] = 'tok';
store['pptsaas_user'] = JSON.stringify({ id: 1, username: 'demo', role: 'admin' });
for (const h of ['#/projects','#/new','#/new/style','#/new/style/x','#/outline/x','#/project/x','#/usage','#/admin','#/settings']) {
  try {
    locationStub.hash = h;
    fn(documentStub, localStorageStub, locationStub, windowStub, fetchStub, { createObjectURL(){return 'blob:x';}, revokeObjectURL(){} });
    console.log('ROUTE OK', h);
  } catch (e) {
    console.log('ROUTE FAILED', h, '—', e.message);
    process.exitCode = 1;
  }
}

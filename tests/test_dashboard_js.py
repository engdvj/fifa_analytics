import re
import shutil
import subprocess

import pytest


def test_dashboard_embedded_javascript_node_check_and_stub_dom(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node nao esta disponivel")

    html_path = "reports/tournament/ranking_race.html"
    try:
        html = open(html_path, encoding="utf-8").read()
    except FileNotFoundError:
        pytest.skip("dashboard ainda nao foi gerado")

    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match, "dashboard sem bloco <script>"

    stub = r"""
function makeEl() {
  const el = {
    style: {}, dataset: {}, children: [], className: "", id: "",
    value: "", checked: false, disabled: false, innerHTML: "", textContent: "",
    clientWidth: 800, clientHeight: 600, offsetWidth: 800, offsetHeight: 40,
    scrollLeft: 0,
    classList: { add(){}, remove(){}, toggle(){ return false; }, contains(){ return false; } },
    appendChild(c){ this.children.push(c); return c; },
    prepend(c){ this.children.unshift(c); return c; },
    removeChild(c){ this.children = this.children.filter(x => x !== c); return c; },
    replaceChildren(...cs){ this.children = cs; },
    insertBefore(c){ this.children.push(c); return c; },
    addEventListener(){}, removeEventListener(){},
    setAttribute(k, v){ this[k] = v; }, getAttribute(k){ return this[k] || null; },
    removeAttribute(k){ delete this[k]; },
    querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
    closest(){ return null; }, focus(){}, blur(){}, click(){}, scrollIntoView(){},
    getBoundingClientRect(){ return {left: 0, top: 0, width: 800, height: 40, right: 800, bottom: 40}; },
  };
  return new Proxy(el, {
    get(t, p) {
      if (p in t) return t[p];
      if (p === "options") return [];
      if (p === "parentElement" || p === "parentNode") return makeEl();
      if (typeof p === "symbol") return undefined;
      return undefined;
    },
    set(t, p, v) { t[p] = v; return true; },
  });
}
const nodes = {};
global.document = {
  body: makeEl(), documentElement: makeEl(),
  getElementById(id){ return nodes[id] ||= makeEl(); },
  createElement(){ return makeEl(); },
  createTextNode(t){ const e = makeEl(); e.textContent = t; return e; },
  querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
  addEventListener(){}, removeEventListener(){},
};
global.window = {
  innerWidth: 1280, innerHeight: 720, location: {hash: ""},
  addEventListener(){}, removeEventListener(){}, getComputedStyle(){ return {}; },
  requestAnimationFrame(fn){ return setTimeout(fn, 0); },
  cancelAnimationFrame(id){ clearTimeout(id); },
};
global.requestAnimationFrame = window.requestAnimationFrame;
global.cancelAnimationFrame = window.cancelAnimationFrame;
global.localStorage = { getItem(){ return null; }, setItem(){}, removeItem(){} };
global.navigator = {userAgent: "node"};
global.ResizeObserver = class { observe(){} unobserve(){} disconnect(){} };
global.IntersectionObserver = class { observe(){} unobserve(){} disconnect(){} };
"""
    js_path = tmp_path / "dashboard.js"
    js_path.write_text(stub + "\n" + match.group(1), encoding="utf-8")

    subprocess.run([node, "--check", str(js_path)], check=True)
    subprocess.run([node, str(js_path)], check=True)

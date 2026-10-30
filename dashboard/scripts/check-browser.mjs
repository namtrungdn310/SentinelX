// Dependency-free headless Chromium verification. Start an isolated Chromium
// with --remote-debugging-port, then pass its endpoint as the second argument.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const appUrl = process.argv[2] ?? "http://localhost:5174";
const endpoint = process.argv[3] ?? "http://localhost:9223";
const artifacts = fileURLToPath(new URL("../node_modules/.cache/sentinelx-ui-qa/", import.meta.url));
const target = await fetch(`${endpoint}/json/new?${encodeURIComponent(appUrl)}`, { method: "PUT" }).then(r => r.json());
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let id = 0;
const pending = new Map();
const errors = [];
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
  const call = pending.get(message.id);
  if (call) {
    clearTimeout(call.timer);
    pending.delete(message.id);
    if (message.error) call.reject(message.error);
    else call.resolve(message.result);
  }
};
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const ticket = ++id;
    const timer = setTimeout(() => { pending.delete(ticket); reject(new Error(`Timeout: ${method}`)); }, 10000);
    pending.set(ticket, { resolve, reject, timer });
    socket.send(JSON.stringify({ id: ticket, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
const settle = () => evaluate("new Promise(resolve => setTimeout(resolve, 180))");
function contrast(foreground, background) {
  const luminance = (hex) => {
    const rgb = hex.trim().replace('#', '').match(/../g).map(channel => {
      const value = parseInt(channel, 16) / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  };
  const values = [luminance(foreground), luminance(background)];
  return (Math.max(...values) + 0.05) / (Math.min(...values) + 0.05);
}
try {
  await send("Page.enable");
  await send("Runtime.enable");
  // Freeze only demo polling after mount so a sliding window cannot discard the
  // oldest sample halfway through a keyboard/tooltip assertion.
  await send("Page.addScriptToEvaluateOnNewDocument", { source: "Math.random = (() => { let seed = 42; return () => ((seed = (seed * 16807) % 2147483647) / 2147483647); })(); window.__qaIntervals=[]; const originalInterval=window.setInterval; window.setInterval=(...args)=>{const handle=originalInterval(...args);window.__qaIntervals.push(handle);return handle;};" });
  await mkdir(artifacts, { recursive: true });
  await send("Page.navigate", { url: appUrl });
  for (let attempt = 0; attempt < 40; attempt++) {
    if (await evaluate("Boolean(document.querySelector('h1'))")) break;
    await settle();
  }
  assert.ok(await evaluate("Boolean(document.querySelector('h1'))"), "React did not mount");
  await settle();
  await evaluate("window.__qaIntervals.forEach(clearInterval)");
  await evaluate("Promise.race([document.fonts.ready, new Promise(resolve => setTimeout(resolve, 2000))])");
  console.log("Font availability:", await evaluate("({ ui: document.fonts.check('15px \"Be Vietnam Pro\"'), mono: document.fonts.check('13px \"IBM Plex Mono\"') })"));
  const appearance = await evaluate("getComputedStyle(document.documentElement).colorScheme");
  assert.equal(appearance, "light");
  const screenshotPrefix = `v4-${appearance}`;
  const tokens = await evaluate("Object.fromEntries([...getComputedStyle(document.documentElement)].filter(p=>p.startsWith('--')).map(p=>[p,getComputedStyle(document.documentElement).getPropertyValue(p).trim()]))");
  const pairs = [
    ['--text-primary', '--bg-panel', 4.5],
    ['--text-secondary', '--bg-panel', 4.5],
    ['--text-muted', '--bg-canvas', 4.5],
    ['--text-muted', '--bg-selected', 4.5],
    ['--brand-indigo', '--bg-panel', 4.5],
    ['--status-ok', '--status-ok-bg', 4.5],
    ['--status-warn', '--status-warn-bg', 4.5],
    ['--status-crit', '--status-crit-bg', 4.5],
    ['--status-neutral', '--status-neutral-bg', 4.5],
    ['--chart-cpu', '--bg-panel', 3],
    ['--chart-memory', '--bg-panel', 3],
    ['--border-strong', '--bg-canvas', 3],
    ['--focus-ring', '--bg-panel', 3],
  ];
  for (const [foreground, background, minimum] of pairs) {
    const ratio = contrast(tokens[foreground], tokens[background]);
    assert.ok(ratio >= minimum, `${foreground} on ${background}: ${ratio.toFixed(2)} < ${minimum}`);
    console.log(`PASS contrast ${foreground} on ${background}: ${ratio.toFixed(2)}:1`);
  }
  assert.ok(contrast('#ffffff', tokens['--action-primary']) >= 4.5);
  for (const width of [390, 768, 1366, 1920]) {
    await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
    for (const route of ["overview", "hosts", "metrics", "events"]) {
      await evaluate(`location.hash = ${JSON.stringify(route)}`);
      await settle();
      const dimensions = await evaluate("({ width: innerWidth, scroll: document.documentElement.scrollWidth })");
      const skipLink = await evaluate("({ focused:document.activeElement===document.querySelector('.skip-link'), bottom:document.querySelector('.skip-link').getBoundingClientRect().bottom })");
      assert.ok(skipLink.focused || skipLink.bottom <= 0, "Skip link should be off-screen until focused");
      if (dimensions.scroll > width + 1) console.log(await evaluate("['body','.app-workspace','.main-viewport','.fleet-panel','.table-scroll','.sr-only'].map(s => {const e=document.querySelector(s);const c=getComputedStyle(e);return {s,width:e.clientWidth,scroll:e.scrollWidth,x:e.getBoundingClientRect().x,overflow:c.overflow,position:c.position}})"));
      assert.ok(dimensions.scroll <= width + 1, `${route} overflows at ${width}: ${dimensions.scroll}`);
      if (route === "metrics") {
        const labels = await evaluate("[...document.querySelectorAll('.chart-axis')].filter(e => e.textContent.includes(':')).map(e => { const r = e.getBoundingClientRect(); return {left:r.left,right:r.right}; })");
        for (let index = 1; index < labels.length; index++) assert.ok(labels[index].left - labels[index - 1].right >= 8, "Clock labels overlap");
        await evaluate("document.querySelector('.chart-foot button').click()"); await settle();
        await evaluate("document.querySelector('.telemetry-svg').focus(); document.querySelector('.telemetry-svg').dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true}))"); await settle();
        for (const key of ['Home', 'End']) {
          await evaluate(`document.querySelector('.telemetry-svg').dispatchEvent(new KeyboardEvent('keydown',{key:'${key}',bubbles:true}))`); await settle();
          const chart = await evaluate("({latest:[...document.querySelectorAll('.legend-pill b')].map(e=>parseFloat(e.textContent)),table:[...document.querySelectorAll('.chart-data-table tbody tr:last-child td')].slice(1).map(e=>parseFloat(e.textContent)),bounds:(()=>{const t=document.querySelector('.chart-tooltip-box').getBoundingClientRect(), c=document.querySelector('.chart-canvas-container').getBoundingClientRect();return {left:t.left,right:t.right,min:c.left,max:c.right}})()})");
          assert.deepEqual(chart.latest, chart.table, 'Hover must not replace latest CPU/RAM readings');
          assert.ok(chart.bounds.left >= chart.bounds.min && chart.bounds.right <= chart.bounds.max + 1, 'Tooltip must stay inside chart');
        }
        await evaluate("document.querySelector('.telemetry-svg').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); document.querySelector('.chart-foot button').click(); document.activeElement.blur(); window.scrollTo(0,0)"); await settle();
      }
      if (route === 'events') {
        assert.equal(await evaluate("getComputedStyle(document.querySelector('.event-full .event-list')).overflowY"), 'visible', 'Event list must use page scrolling');
        assert.ok(await evaluate("document.querySelector('.event-filter-group button').getAttribute('aria-pressed') === 'true'"));
        await evaluate("document.querySelector('[aria-label=\"Tạm dừng nhật ký\"]').click()"); await settle();
        const frozen = await evaluate("document.querySelector('.event-list').textContent");
        await evaluate("document.querySelectorAll('.event-filter-group button')[1].click()"); await settle();
        assert.ok(await evaluate("[...document.querySelectorAll('.event-type-code')].every(e=>e.textContent!=='metric_update')"));
        await evaluate("document.querySelectorAll('.event-filter-group button')[2].click()"); await settle();
        assert.ok(await evaluate("[...document.querySelectorAll('.event-type-code')].every(e=>e.textContent==='metric_update')"));
        await evaluate("document.querySelectorAll('.event-filter-group button')[0].click()"); await settle();
        assert.equal(await evaluate("document.querySelector('.event-list').textContent"), frozen, 'Filtering must preserve the paused snapshot');
        assert.ok(await evaluate("document.querySelector('.event-stream-state').textContent.includes('Đã tạm dừng')"));
        assert.equal(await evaluate("getComputedStyle(document.querySelector('.event-controls')).position"), 'sticky');
        await evaluate("document.querySelector('[aria-label=\"Tiếp tục nhật ký\"]').click(); window.scrollTo(0,0)"); await settle();
      }
      if (route === "overview") {
        const design = await evaluate("({font:getComputedStyle(document.querySelector('.stat-value')).fontFamily,gap:getComputedStyle(document.querySelector('.kpi-grid')).columnGap,thresholds:[...document.querySelectorAll('.stat-track .threshold-mark')].map(e=>e.style.left),layout:getComputedStyle(document.querySelector('.overview-grid')).gridTemplateColumns,health:[...document.querySelector('.fleet-health-body').children].map(e=>({left:e.getBoundingClientRect().left,top:e.getBoundingClientRect().top}))})");
        assert.ok(design.font.includes("Be Vietnam Pro"), "KPI must use the UI sans family");
        assert.equal(design.gap, "16px");
        assert.deepEqual(design.thresholds, ["75%", "85%"]);
        assert.equal(design.layout.split(" ").length, 1, "Overview sections must remain full rows");
        if (width >= 1366) assert.ok(design.health[1].left > design.health[0].left + 150, "Desktop health needs distinct summary/distribution regions");
        if (width === 390) assert.ok(design.health[1].top > design.health[0].top, "Mobile health regions must stack");
        assert.equal(await evaluate("Boolean(document.querySelector('.demo-notice'))"), false);
        assert.ok(await evaluate("getComputedStyle(document.querySelector('.connection-state')).display !== 'none'"), 'Demo source must remain visible at every breakpoint');
      }
      await evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})"); await settle();
      const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
      await writeFile(`${artifacts}${screenshotPrefix}-${route}-${width}.png`, Buffer.from(screenshot.data, "base64"));
      console.log(`PASS ${route} at ${width}px: mounted, no page overflow`);
    }
  }
  await evaluate("location.hash='hosts'"); await settle();
  await evaluate("document.querySelector('[aria-label=\"Xem lưới máy chủ\"]').click()");
  await evaluate("location.hash='metrics'"); await settle();
  const host = await evaluate("document.querySelector('#telemetry-host').value");
  await evaluate("Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(document.querySelector('[aria-label=\"Tìm máy chủ\"]'),'no-such-host'); document.querySelector('[aria-label=\"Tìm máy chủ\"]').dispatchEvent(new Event('input',{bubbles:true}))");
  await settle();
  assert.equal(await evaluate("document.querySelector('#telemetry-host').value"), host);
  await evaluate("location.hash='hosts'"); await settle();
  assert.equal(await evaluate("document.querySelector('[aria-label=\"Xem lưới máy chủ\"]').getAttribute('aria-pressed')"), "true");
  await evaluate("document.querySelector('[aria-label=\"Dự án\"]').value = document.querySelector('[aria-label=\"Dự án\"] option:nth-child(2)').value; document.querySelector('[aria-label=\"Dự án\"]').dispatchEvent(new Event('change',{bubbles:true}))");
  await settle();
  const project = await evaluate("document.querySelector('[aria-label=\"Dự án\"]').value");
  await evaluate("document.querySelector('[aria-label=\"Lọc trạng thái\"]').value='crit'; document.querySelector('[aria-label=\"Lọc trạng thái\"]').dispatchEvent(new Event('change',{bubbles:true}))");
  await settle();
  await evaluate("document.querySelector('.clear-filters').click()"); await settle();
  assert.equal(await evaluate("document.querySelector('[aria-label=\"Dự án\"]').value"), project);
  await evaluate("location.hash='events'"); await settle();
  await evaluate("document.querySelector('[aria-label=\"Tạm dừng nhật ký\"]').click()"); await settle();
  assert.ok(await evaluate("Boolean(document.querySelector('[aria-label=\"Tiếp tục nhật ký\"]'))"));
  await evaluate("document.querySelector('[aria-label=\"Dự án\"]').value=''; document.querySelector('[aria-label=\"Dự án\"]').dispatchEvent(new Event('change',{bubbles:true}))");
  await settle();
  assert.ok(await evaluate("Boolean(document.querySelector('[aria-label=\"Tạm dừng nhật ký\"]'))"));
  await evaluate("location.hash='hosts'"); await settle();
  await evaluate("document.querySelector('[aria-label=\"Tìm máy chủ\"]').focus()");
  const focus = await evaluate("({ outer: getComputedStyle(document.querySelector('.global-search')).outlineWidth, inner: getComputedStyle(document.querySelector('.global-search input')).outlineStyle, offset:getComputedStyle(document.querySelector('.global-search')).outlineOffset, color:getComputedStyle(document.querySelector('.global-search')).outlineColor })");
  assert.equal(focus.outer, "2px");
  assert.equal(focus.inner, "none");
  assert.equal(focus.offset, "0px");
  assert.equal(focus.color, "rgb(75, 85, 99)");
  const focusImage = await send("Page.captureScreenshot", { format: "png" });
  await writeFile(`${artifacts}${screenshotPrefix}-search-focus.png`, Buffer.from(focusImage.data, "base64"));
  await evaluate("document.querySelector('.page-heading button').focus(); document.querySelector('.page-heading button').click()"); await settle();
  assert.ok(await evaluate("Boolean(document.querySelector('[role=dialog]'))"));
  assert.ok(await evaluate("Boolean(document.activeElement.closest('[role=dialog]'))"));
  const modalImage = await send("Page.captureScreenshot", { format: "png" });
  await writeFile(`${artifacts}${screenshotPrefix}-add-host-modal.png`, Buffer.from(modalImage.data, "base64"));
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape" });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape" });
  await settle();
  assert.ok(await evaluate("!document.querySelector('[role=dialog]')"));
  assert.ok(await evaluate("document.activeElement === document.querySelector('.page-heading button')"));
  assert.deepEqual(errors, []);
  console.log("PASS V4 source visibility, event filters, paused snapshot, single-scroll/sticky controls, latest chart readouts, bounded keyboard tooltips; host/view/scope/focus/modal regressions PASS; no runtime exceptions");
} finally {
  socket.close();
  await fetch(`${endpoint}/json/close/${target.id}`);
}

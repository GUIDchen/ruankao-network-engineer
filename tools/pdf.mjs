import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const [htmlPath, pdfPath] = process.argv.slice(2);
if (!htmlPath || !pdfPath) { console.error('usage: pdf.mjs in.html out.pdf'); process.exit(2); }

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9500 + Math.floor(Math.random() * 300);
const userDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dsh-chrome-'));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-extensions', '--hide-scrollbars', '--mute-audio',
  '--remote-debugging-port=' + port, '--user-data-dir=' + userDir, 'about:blank'
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function devtoolsUrl() {
  for (let i = 0; i < 150; i++) {
    try {
      const r = await fetch('http://127.0.0.1:' + port + '/json/version');
      if (r.ok) {
        const j = await r.json();
        if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl;
      }
    } catch (e) { /* not ready */ }
    await sleep(100);
  }
  throw new Error('devtools not ready');
}

const wsUrl = await devtoolsUrl();
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let seq = 0;
const pending = new Map();
const events = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
  } else if (msg.method) {
    events.push(msg);
  }
};

function send(method, params = {}, sessionId) {
  const id = ++seq;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  ws.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
await send('Page.enable', {}, sessionId);

const fileUrl = 'file://' + path.resolve(htmlPath);
await send('Page.navigate', { url: fileUrl }, sessionId);

for (let i = 0; i < 200; i++) {
  if (events.some((e) => e.method === 'Page.loadEventFired' && e.sessionId === sessionId)) break;
  await sleep(100);
}
await sleep(600);

const footer = '<div style="width:100%;padding:0 17mm;font-size:8.5px;color:#8c8c8c;'
  + 'font-family:\'PingFang SC\',\'Songti SC\',serif;display:flex;justify-content:space-between;align-items:center;">'
  + '<span>软考中级网络工程师 · 2024—2026 真题研究与考点精讲</span>'
  + '<span>第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页</span></div>';

const { data } = await send('Page.printToPDF', {
  printBackground: true,
  preferCSSPageSize: true,
  displayHeaderFooter: true,
  headerTemplate: '<div></div>',
  footerTemplate: footer,
  marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0,
  scale: 1,
}, sessionId);

fs.writeFileSync(pdfPath, Buffer.from(data, 'base64'));
await send('Target.closeTarget', { targetId });
ws.close();
chrome.kill('SIGTERM');
await sleep(300);
fs.rmSync(userDir, { recursive: true, force: true });
console.log('pdf written', pdfPath, fs.statSync(pdfPath).size);

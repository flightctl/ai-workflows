#!/usr/bin/env node
/**
 * Browser integration test for ux-design preview bundles.
 *
 * Packages a mock prototype via preview-bundle.py, serves the result
 * at a nested PR/revision path, and verifies rendering with Puppeteer:
 *   - DOM content populated by JavaScript
 *   - Click interaction toggles CSS visibility class
 *   - CSS and JS assets load successfully
 *   - No external network requests (all blocked)
 *   - No backend calls observed
 *
 * Requires: Node.js, Puppeteer (npm install puppeteer)
 *
 * Usage:
 *   node test_preview_browser.js [--puppeteer-path /path/to/node_modules/puppeteer]
 *
 * Exit codes:
 *   0 — all assertions passed
 *   1 — test failure or missing dependency
 */

'use strict';

const { execSync } = require('child_process');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');

// --- Parse args ---
let puppeteerPath = '/tmp/node_modules/puppeteer';
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === '--puppeteer-path' && process.argv[i + 1]) {
    puppeteerPath = process.argv[i + 1];
    i++;
  }
}

// --- Helpers ---
const SCRIPT_DIR = __dirname;
const BUNDLE_SCRIPT = path.join(SCRIPT_DIR, 'preview-bundle.py');

function assert(condition, msg) {
  if (!condition) {
    console.error(`FAIL: ${msg}`);
    process.exitCode = 1;
    throw new Error(msg);
  }
  console.log(`  PASS: ${msg}`);
}

function mkTmpDir(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function rmDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}

// --- Build a mock prototype with interactive elements ---
function createMockPrototype(protoDir) {
  const prototype = path.join(protoDir, 'prototype');
  fs.mkdirSync(prototype, { recursive: true });

  fs.writeFileSync(path.join(prototype, 'index.html'), `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Fleet Management — Preview Test</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1 id="title">Device Fleet Dashboard</h1>
  <p>Active devices: <span id="count">0</span></p>
  <button id="toggle-btn">Show Details</button>
  <div id="details" class="hidden">
    <ul id="device-list"></ul>
  </div>
  <img src="logo.svg" alt="logo" id="logo" width="32" height="32">
  <script src="app.js"></script>
</body>
</html>`);

  fs.writeFileSync(path.join(prototype, 'style.css'), `
body { font-family: sans-serif; margin: 2rem; color: #333; }
.hidden { display: none; }
.visible { display: block; background: #eef; padding: 1rem; border-radius: 4px; }
button { padding: 0.5rem 1rem; cursor: pointer; }
`);

  fs.writeFileSync(path.join(prototype, 'app.js'), `
// Mock data — no backend required
const devices = [
  { name: 'edge-01', status: 'active' },
  { name: 'edge-02', status: 'active' },
  { name: 'edge-03', status: 'offline' },
];

// Populate count via JS (proves JS execution)
document.getElementById('count').textContent = devices.filter(d => d.status === 'active').length;

// Populate device list
const list = document.getElementById('device-list');
devices.forEach(d => {
  const li = document.createElement('li');
  li.textContent = d.name + ' (' + d.status + ')';
  list.appendChild(li);
});

// Toggle visibility on click
document.getElementById('toggle-btn').addEventListener('click', function() {
  const panel = document.getElementById('details');
  if (panel.className === 'hidden') {
    panel.className = 'visible';
    this.textContent = 'Hide Details';
  } else {
    panel.className = 'hidden';
    this.textContent = 'Show Details';
  }
});
`);

  // SVG asset
  fs.writeFileSync(path.join(prototype, 'logo.svg'),
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><circle cx="16" cy="16" r="14" fill="#0066cc"/></svg>');
}

// --- Package the prototype ---
function packageBundle(protoDir, outputDir) {
  const cmd = `python3 "${BUNDLE_SCRIPT}" package ` +
    `--prototype-dir "${protoDir}" ` +
    `--output-dir "${outputDir}" ` +
    `--issue-key TEST-BROWSER ` +
    `--revision iteration-1 ` +
    `--mode standalone`;
  const result = execSync(cmd, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
  return JSON.parse(result);
}

// --- Serve a directory via HTTP at a nested path ---
function startServer(siteRoot) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent(req.url.split('?')[0]);
      const filePath = path.join(siteRoot, urlPath);

      if (!filePath.startsWith(siteRoot)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
      }

      let target = filePath;
      if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        target = path.join(filePath, 'index.html');
      }

      if (!fs.existsSync(target)) {
        res.writeHead(404);
        res.end('Not Found');
        return;
      }

      const ext = path.extname(target).toLowerCase();
      const mimeTypes = {
        '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
        '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json',
      };
      res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
      fs.createReadStream(target).pipe(res);
    });

    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

// --- Main test ---
async function main() {
  let puppeteer;
  try {
    puppeteer = require(puppeteerPath);
  } catch (e) {
    console.error(`SKIP: Puppeteer not found at ${puppeteerPath}: ${e.message}`);
    console.error('Install with: npm install puppeteer');
    process.exit(1);
  }

  const tmpDir = mkTmpDir('preview-browser-test-');
  const protoDir = path.join(tmpDir, 'proto');
  const outputDir = path.join(tmpDir, 'output');
  let browser, srv;

  try {
    // 1. Create mock prototype and package it
    console.log('=== Step 1: Create and package mock prototype ===');
    fs.mkdirSync(protoDir, { recursive: true });
    createMockPrototype(protoDir);
    const pkg = packageBundle(protoDir, outputDir);
    assert(pkg.entry_point === 'index.html', 'Entry point is index.html');
    assert(pkg.file_count >= 3, `Bundle has ${pkg.file_count} files (>=3 expected)`);
    console.log(`  Bundle at: ${pkg.bundle_dir}`);

    // 2. Serve the bundle at nested PR/revision path
    console.log('=== Step 2: Serve bundle at nested path ===');
    srv = await startServer(outputDir);
    const baseUrl = `http://127.0.0.1:${srv.port}/previews/TEST-BROWSER/iteration-1`;
    console.log(`  Serving at: ${baseUrl}`);

    // 3. Launch headless browser with network blocking
    console.log('=== Step 3: Launch headless browser ===');
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();

    // Block all non-local network requests
    const networkLog = [];
    const blockedRequests = [];
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      const url = req.url();
      networkLog.push({ url, method: req.method(), resourceType: req.resourceType() });
      if (url.startsWith('http://127.0.0.1:' + srv.port)) {
        req.continue();
      } else {
        blockedRequests.push(url);
        req.abort('blockedbyclient');
      }
    });

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));
    const consoleMessages = [];
    page.on('console', (msg) => consoleMessages.push({ type: msg.type(), text: msg.text() }));

    // 4. Navigate and verify
    console.log('=== Step 4: Navigate and verify DOM ===');
    const resp = await page.goto(`${baseUrl}/index.html`, { waitUntil: 'networkidle0', timeout: 10000 });
    assert(resp.status() === 200, 'Entry point returns HTTP 200');

    // DOM content populated by JavaScript
    const title = await page.$eval('#title', el => el.textContent);
    assert(title === 'Device Fleet Dashboard', `Title is "${title}"`);

    const count = await page.$eval('#count', el => el.textContent);
    assert(count === '2', `JS-populated device count is "${count}" (expected "2")`);

    // Device list populated by JS
    const listItems = await page.$$eval('#device-list li', items => items.map(i => i.textContent));
    assert(listItems.length === 3, `Device list has ${listItems.length} items`);

    // 5. Click interaction and CSS visibility change
    console.log('=== Step 5: Click interaction + CSS state change ===');
    const detailsBefore = await page.$eval('#details', el => el.className);
    assert(detailsBefore === 'hidden', `Details panel starts hidden (class="${detailsBefore}")`);

    const displayBefore = await page.$eval('#details', el => getComputedStyle(el).display);
    assert(displayBefore === 'none', `Details panel CSS display is "${displayBefore}"`);

    await page.click('#toggle-btn');
    await page.waitForFunction(() => document.getElementById('details').className === 'visible', { timeout: 2000 });

    const detailsAfter = await page.$eval('#details', el => el.className);
    assert(detailsAfter === 'visible', `After click: details class="${detailsAfter}"`);

    const displayAfter = await page.$eval('#details', el => getComputedStyle(el).display);
    assert(displayAfter === 'block', `After click: CSS display="${displayAfter}"`);

    const btnText = await page.$eval('#toggle-btn', el => el.textContent);
    assert(btnText === 'Hide Details', `Button text changed to "${btnText}"`);

    // 6. Verify assets loaded
    console.log('=== Step 6: Verify asset loading ===');
    const cssLoaded = networkLog.some(r => r.url.includes('style.css') && r.resourceType === 'stylesheet');
    assert(cssLoaded, 'CSS stylesheet loaded');

    const jsLoaded = networkLog.some(r => r.url.includes('app.js') && r.resourceType === 'script');
    assert(jsLoaded, 'JavaScript loaded');

    const svgLoaded = networkLog.some(r => r.url.includes('logo.svg'));
    assert(svgLoaded, 'SVG asset loaded');

    // 7. Verify no external/backend network requests
    console.log('=== Step 7: Verify network isolation ===');
    assert(blockedRequests.length === 0, `No blocked external requests (${blockedRequests.length} blocked)`);

    const backendCalls = networkLog.filter(r =>
      r.url.includes('/api/') || r.url.includes('localhost:3000')
    );
    assert(backendCalls.length === 0, `No backend API calls (${backendCalls.length} found)`);
    assert(pageErrors.length === 0, `No page errors (${pageErrors.length} errors)`);

    // 8. Summary
    console.log('\n=== Results ===');
    console.log(`  Network requests: ${networkLog.length} (all local)`);
    console.log(`  Blocked requests: ${blockedRequests.length}`);
    console.log(`  Page errors: ${pageErrors.length}`);
    console.log(`  Console messages: ${consoleMessages.length}`);
    console.log('  ALL BROWSER ASSERTIONS PASSED');

  } catch (e) {
    console.error(`\nTest error: ${e.message}`);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    if (srv) srv.server.close();
    rmDir(tmpDir);
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});

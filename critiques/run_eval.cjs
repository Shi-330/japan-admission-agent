/**
 * One-command eval harness.
 *
 * Fixes the "Playwright 一直不行" problem: Playwright itself works, but the eval
 * scripts require the app running on :8000. This runner guarantees the server is
 * built + up + healthy before the browser eval runs, then tears it down.
 *
 * Usage:
 *   node critiques/run_eval.cjs eval_sprint4.js            # build frontend, start server, run eval
 *   node critiques/run_eval.cjs eval_sprint4.js --no-build # skip npm build (faster, uses current dist)
 *   node critiques/run_eval.cjs --smoke                    # just prove server+browser wire up
 *
 * Exit code = eval script's exit code (0 pass-through). 2 = server failed to start.
 */
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BASE = 'http://127.0.0.1:8000';
const PY = path.join(ROOT, 'venv', 'Scripts', 'python.exe');
const LOG = path.join(ROOT, 'critiques', '.server.log');

const args = process.argv.slice(2);
const smoke = args.includes('--smoke');
const noBuild = args.includes('--no-build');
const evalScript = args.find((a) => !a.startsWith('--')) || 'eval_sprint4.js';

function log(msg) {
  console.log(`[run_eval] ${msg}`);
}

async function waitHealth(timeoutMs = 45000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(BASE + '/health');
      if (r.ok) return true;
    } catch {
      /* server not up yet */
    }
    await new Promise((res) => setTimeout(res, 800));
  }
  return false;
}

function killServer(pid) {
  if (!pid) return;
  try {
    // /T kills the whole tree, /F force. Windows uvicorn is single-process but be safe.
    spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' });
  } catch {
    try { process.kill(pid); } catch {}
  }
}

(async () => {
  if (!fs.existsSync(PY)) {
    log(`FATAL: venv python not found at ${PY}`);
    process.exit(2);
  }

  // 1. Build frontend so dist reflects current source (eval-before-deploy needs this).
  if (!noBuild && !smoke) {
    log('building frontend (npm run build)...');
    const b = spawnSync('npm', ['run', 'build'], {
      cwd: path.join(ROOT, 'frontend'),
      stdio: 'inherit',
      shell: true, // npm is npm.cmd on Windows
    });
    if (b.status !== 0) {
      log('FATAL: frontend build failed');
      process.exit(2);
    }
  } else {
    log('skipping build (--no-build/--smoke), using current dist');
  }

  // 2. Start the server, piping its output to a log file for post-mortem.
  const logFd = fs.openSync(LOG, 'w');
  log('starting server on :8000 ...');
  const server = spawn(
    PY,
    ['-m', 'uvicorn', 'backend.api.server:app', '--host', '127.0.0.1', '--port', '8000'],
    { cwd: ROOT, stdio: ['ignore', logFd, logFd] }
  );
  const cleanup = () => killServer(server.pid);
  process.on('exit', cleanup);
  process.on('SIGINT', () => { cleanup(); process.exit(130); });

  // 3. Wait for /health.
  const up = await waitHealth();
  if (!up) {
    log('FATAL: server did not become healthy in 45s. Last server log:');
    try { console.log(fs.readFileSync(LOG, 'utf8').split('\n').slice(-25).join('\n')); } catch {}
    cleanup();
    process.exit(2);
  }
  log('server healthy.');

  if (smoke) {
    log('SMOKE OK: server up + reachable. (browser launch already verified separately)');
    cleanup();
    process.exit(0);
  }

  // 4. Run the eval script against the live server.
  log(`running ${evalScript} ...`);
  const res = spawnSync('node', [path.join('critiques', evalScript)], {
    cwd: ROOT,
    stdio: 'inherit',
  });

  // 5. Teardown.
  cleanup();
  const code = res.status == null ? 1 : res.status;
  log(`eval finished (exit ${code}). server stopped.`);
  process.exit(code);
})();

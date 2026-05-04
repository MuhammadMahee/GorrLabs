// start-jobs.js
// One-command launcher for essential background jobs (observation layer).
// Spawns child processes, forwards env, prefixes logs, and shuts down cleanly.
import { fork } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const ARG_WITH_FULLSCAN    = process.argv.includes('--with-fullscan');
const ARG_WITH_FX_BACKFILL = process.argv.includes('--with-fx-backfill');

const BASE_ENV = {
  ...process.env,
  DATABASE_URL: process.env.DATABASE_URL,
  CMC_API_KEY: process.env.CMC_API_KEY,
};

// Map job name -> module + exported start function
const JOBS = [
  { name: 'FX-FEED',     mod: 'jobs/fx-zig.js',           fn: 'startFx' },
  { name: 'ROLLUPS',     mod: 'jobs/wallet-rollups.js',   fn: 'startWalletRollups' },
  { name: 'META',        mod: 'jobs/meta-refresher.js',   fn: 'startMetaRefresher' },
  { name: 'LEADERBOARD', mod: 'jobs/leaderboards.js',     fn: 'startLeaderboards' },
  { name: 'IBC-REFRESH', mod: 'jobs/holders-refresher.js',fn: 'startHoldersRefresher' },
];

if (ARG_WITH_FULLSCAN) {
  JOBS.push({ name: 'IBC-FULL', mod: 'jobs/ibc-holders-fullscan.js', fn: 'startIbcHoldersFullscan' });
}
if (ARG_WITH_FX_BACKFILL) {
  JOBS.push({ name: 'FX-BACKFILL', mod: 'jobs/fx-zig-backfill.js', fn: 'runFxBackfillStork' });
}

const children = new Map();
let shuttingDown = false;

function prefixLog(name, data) {
  const lines = data.toString().trimEnd().split(/\r?\n/);
  for (const line of lines) {
    if (!line) continue;
    console.log(`[${name}] ${line}`);
  }
}

function spawnJob(job) {
  const runner = resolve(__dirname, 'jobs/run-job.js');
  const target = resolve(__dirname, job.mod);
  const child = fork(runner, [target, job.fn], {
    env: BASE_ENV,
    stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
  });

  children.set(job.name, child);

  child.stdout?.on('data', (d) => prefixLog(job.name, d));
  child.stderr?.on('data', (d) => prefixLog(job.name, d));

  child.on('exit', (code, signal) => {
    children.delete(job.name);
    if (!shuttingDown) {
      console.error(`[${job.name}] exited unexpectedly (code=${code}, signal=${signal})`);
    } else {
      console.log(`[${job.name}] exited (code=${code}, signal=${signal})`);
    }
  });

  child.on('error', (err) => {
    console.error(`[${job.name}] error`, err);
  });
}

function startAll() {
  console.log('[JOBS] starting:', JOBS.map(j => j.name).join(', '));
  JOBS.forEach(spawnJob);
}

async function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log('[JOBS] shutting down…');
  const kills = [];
  for (const [, child] of children.entries()) {
    kills.push(new Promise((resolveKill) => {
      child.once('exit', () => resolveKill());
      child.kill('SIGTERM');
      setTimeout(() => {
        if (!child.killed) child.kill('SIGKILL');
      }, 5000);
    }));
  }
  await Promise.allSettled(kills);
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

startAll();

// Keep master alive
setInterval(() => {}, 1 << 30);

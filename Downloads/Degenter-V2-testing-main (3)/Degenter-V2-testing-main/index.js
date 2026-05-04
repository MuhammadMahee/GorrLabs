// index.js - Stage 2 Orchestrator: spawn one worker per active chain.
import { Worker } from 'worker_threads';
import { DB, init as dbInit, close as dbClose } from './lib/db.js';
import { info, err, warn } from './lib/log.js';

const RESTART_DELAY_MS = Number(process.env.WORKER_RESTART_DELAY_MS || 10_000);
const WORKER_PATH = new URL('./worker/indexer-worker.js', import.meta.url);

async function fetchActiveChains() {
  const { rows } = await DB.query(
    `SELECT chain_id, rpc_url, lcd_url, native_denom
       FROM chains
      WHERE is_active = TRUE`
  );
  return rows;
}

function parseBackfillArgs() {
  // --backfill=chain:start[:end]
  const map = new Map();
  for (const arg of process.argv.slice(2)) {
    const m = arg.match(/^--backfill=([^:]+):(\d+)(?::(\d+))?$/);
    if (m) {
      map.set(m[1], { start: Number(m[2]), end: m[3] ? Number(m[3]) : null });
    }
  }
  return map;
}

function spawnWorker(chain, backfill = null) {
  const workerName = `${chain.chain_id.toUpperCase()}-WORKER`;
  info('[orchestrator] starting worker', chain.chain_id);
  const worker = new Worker(WORKER_PATH, {
    workerData: {
      ...chain,
      workerName,
      backfillHeight: backfill?.start ?? null,
      stopHeight: backfill?.end ?? null
    }
  });

  worker.on('online', () => info('[worker]', chain.chain_id, 'online'));

  worker.on('exit', (code) => {
    if (code === 0) {
      info('[worker]', chain.chain_id, 'exited cleanly');
      return;
    }
    warn('[worker]', chain.chain_id, 'exited with code', code, '→ restart in', RESTART_DELAY_MS, 'ms');
    setTimeout(() => spawnWorker(chain), RESTART_DELAY_MS);
  });

  worker.on('error', (e) => {
    err('[worker]', chain.chain_id, 'error', e?.message || e);
    worker.terminate().catch(()=>{});
    setTimeout(() => spawnWorker(chain), RESTART_DELAY_MS);
  });

  return worker;
}

async function main() {
  await dbInit();
  const backfillMap = parseBackfillArgs();
  const chains = await fetchActiveChains();
  if (!chains.length) {
    warn('[orchestrator] no active chains found; exiting');
    await dbClose();
    return;
  }
  info('[orchestrator] active chains', chains.map(c => c.chain_id).join(', '));
  for (const c of chains) {
    const bf = backfillMap.get(c.chain_id) || null;
    spawnWorker(c, bf);
  }
  // free orchestrator DB connection
  await dbClose().catch(()=>{});
}

main().catch(async (e) => {
  err('[orchestrator] fatal', e?.stack || e);
  await dbClose().catch(()=>{});
  process.exit(1);
});

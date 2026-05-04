// worker/indexer-worker.js
// Receives chain config via workerData and starts the indexer for that chain.
import { parentPort, workerData } from 'worker_threads';

async function boot(chain) {
  // Set per-worker env so downstream modules pick up correct endpoints.
  process.env.CHAIN_ID = chain.chain_id;
  process.env.WORKER_NAME = chain.workerName || `${chain.chain_id}-worker`;
  process.env.LOG_PREFIX = `[${chain.workerName || chain.chain_id}]`;
  process.env.RPC_PRIMARY = chain.rpc_url;
  process.env.LCD_PRIMARY = chain.lcd_url;
  process.env.NATIVE_DENOM = chain.native_denom || process.env.NATIVE_DENOM || 'uzig';
  // Optionally shrink pool per worker
  if (!process.env.DB_POOL_MAX) process.env.DB_POOL_MAX = '8';
  if (chain.backfillHeight != null) {
    process.env.START_HEIGHT = String(chain.backfillHeight);
  }
  if (chain.stopHeight != null) {
    process.env.STOP_HEIGHT = String(chain.stopHeight);
  }

  // Lazy import after env is set to avoid stale config
  await import('../bin/start-indexer.js');
}

boot(workerData).catch((e) => {
  console.error('[worker fatal]', workerData?.chain_id, e?.stack || e);
  process.exit(1);
});

if (parentPort) {
  parentPort.postMessage({ ok: true, chain_id: workerData?.chain_id });
}

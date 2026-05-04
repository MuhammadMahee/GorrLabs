// bin/start-indexer.js
import 'dotenv/config';
import { init, close } from '../lib/db.js';
import { getStatus } from '../lib/rpc.js';
import { info, err } from '../lib/log.js';
import { readCheckpoint, writeCheckpoint } from '../core/checkpoint.js';
import { processHeight } from '../core/block-processor.js';
import { drainTrades } from '../core/trades.js';
import { drainOHLCV } from '../core/ohlcv.js';
import { drainPoolState } from '../core/pool_state.js';
import { quitRedis } from '../lib/redis.js';
import { updateWorkerStatus } from '../core/worker_status.js';

const ENV_MAX_BLOCKS   = parseInt(process.env.MAX_BLOCKS || '0', 10);
const STOP_HEIGHT      = process.env.STOP_HEIGHT ? Number(process.env.STOP_HEIGHT) : null;
const POLL_SLEEP_MS    = parseInt(process.env.POLL_SLEEP_MS || '400', 10);
const PIPELINE_DEPTH   = parseInt(process.env.PIPELINE_DEPTH || '3', 10);
const BLOCK_CAP        = Number.isFinite(ENV_MAX_BLOCKS) && ENV_MAX_BLOCKS > 0 ? ENV_MAX_BLOCKS : Infinity;
const IS_INFINITE_MODE = !Number.isFinite(BLOCK_CAP);
const CHAIN_ID         = process.env.CHAIN_ID || 'zigchain-1';
const WORKER_NAME      = process.env.WORKER_NAME || CHAIN_ID.toUpperCase() + '-WORKER';

function sleep(ms){ return new Promise(r=>setTimeout(r, ms)); }

const unwrapStatus = (j) => {
  const h = j?.result?.sync_info?.latest_block_height
         ?? j?.sync_info?.latest_block_height
         ?? null;
  const n = Number(h);
  return Number.isFinite(n) ? n : null;
};

async function drainAll() {
  await Promise.all([drainTrades(), drainOHLCV(), drainPoolState()]);
}

async function main() {
  await init();

  const tip0 = unwrapStatus(await getStatus());
  if (!tip0) throw new Error('status: no latest_block_height');
  const saved = await readCheckpoint(CHAIN_ID);
  const backfillEnv = process.env.START_HEIGHT ? Number(process.env.START_HEIGHT) : null;
  let current = backfillEnv && Number.isFinite(backfillEnv)
    ? backfillEnv
    : (saved !== null && saved !== undefined) ? Number(saved) : tip0;
  info('startup heights:', { chain_id: CHAIN_ID, tip: tip0, saved_from_chains: saved, start: current, cap: IS_INFINITE_MODE ? 'infinite' : BLOCK_CAP });

  let processed = 0;
  const inflight = new Map(); // height -> Promise

  const commitInOrder = async () => {
    const keys = Array.from(inflight.keys()).sort((a,b)=>a-b);
    for (const h of keys) {
      const p = inflight.get(h);
      if (!p) continue;
      const r = await p.catch(e => ({ ok:false, error:e }));
      inflight.delete(h);
      if (r && r.ok !== false) {
        await writeCheckpoint(CHAIN_ID, h);
        if (h % 10 === 0) {
          await updateWorkerStatus(CHAIN_ID, WORKER_NAME, h);
        }
      }
      processed++;
      const progress = IS_INFINITE_MODE ? `(${processed})` : `(${processed}/${BLOCK_CAP})`;
      info('done height', h, progress);
      await drainAll();
      if (r && r.ok === false && r.error) {
        err(`height ${h} error:`, r.error.stack || r.error);
      }
    }
  };

  while (processed < BLOCK_CAP) {
    const tipNow = unwrapStatus(await getStatus()) ?? tip0;

    while (inflight.size < PIPELINE_DEPTH && current <= tipNow && processed + inflight.size < BLOCK_CAP) {
      if (STOP_HEIGHT != null && current > STOP_HEIGHT) break;
      const h = current++;
      inflight.set(h, (async () => {
        try { await processHeight(h); return { ok: true }; }
        catch (e) { return { ok:false, error:e }; }
      })());
    }

    await commitInOrder();

    if (STOP_HEIGHT != null && current > STOP_HEIGHT && inflight.size === 0) break;
    if (current > tipNow) await sleep(POLL_SLEEP_MS);
  }

  await drainAll();
}

async function shutdown(code = 0) {
  await drainAll().catch(() => {});
  await quitRedis().catch(() => {});
  await close().catch(() => {});
  process.exit(code);
}

process.on('SIGINT', () => shutdown(0));
process.on('SIGTERM', () => shutdown(0));

main()
  .then(async () => { await shutdown(0); })
  .catch(async (e) => { err(e); await shutdown(1); });

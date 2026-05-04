import { DB } from '../lib/db.js';

const ensureSql = `
CREATE TABLE IF NOT EXISTS worker_status (
  chain_id     text primary key,
  worker_name  text,
  last_height  bigint,
  updated_at   timestamptz default now()
);
`;

export async function updateWorkerStatus(chainId, workerName, height) {
  if (!chainId) return;
  await DB.query(ensureSql);
  await DB.query(
    `INSERT INTO worker_status(chain_id, worker_name, last_height, updated_at)
     VALUES ($1,$2,$3, now())
     ON CONFLICT (chain_id) DO UPDATE
       SET worker_name = EXCLUDED.worker_name,
           last_height = EXCLUDED.last_height,
           updated_at  = now()`,
    [chainId, workerName || null, height ?? null]
  );
}

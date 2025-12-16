// core/ohlcv.js
import { DB } from '../lib/db.js';
import BatchQueue from '../lib/batch.js';

/**
 * -------------- SHARED HELPERS (ZIG + USD) --------------
 */

function keyOf(pool_id, bucket_start) {
  // bucket_start is a Date; we store as ISO to avoid floating equality issues in a Map key
  return `${pool_id}__${new Date(bucket_start).toISOString()}`;
}

/**
 * ZIG-side aggregation
 */
function aggregateBatchZig(items) {
  // Collapse duplicates for same (pool_id,bucket) so we do a single row per key in the INSERT
  const map = new Map();
  for (const it of items) {
    const k = keyOf(it.pool_id, it.bucket_start);
    const prev = map.get(k);
    if (!prev) {
      map.set(k, {
        pool_id: it.pool_id,
        bucket_start: it.bucket_start,
        // initialize with this trade's price
        high: it.price,
        low: it.price,
        close: it.price, // last price in this batch (order preserved below)
        volume_zig: it.vol_zig || 0,
        trade_count: it.trade_inc || 0,
        liquidity_zig: it.liquidity_zig ?? null,
      });
    } else {
      // update high/low/close, accumulate volume/trades
      if (it.price > prev.high) prev.high = it.price;
      if (it.price < prev.low) prev.low = it.price;
      prev.close = it.price; // last seen in arrival order
      prev.volume_zig += it.vol_zig || 0;
      prev.trade_count += it.trade_inc || 0;
      // keep latest non-null liquidity if provided
      if (it.liquidity_zig != null) prev.liquidity_zig = it.liquidity_zig;
    }
  }
  return Array.from(map.values());
}

async function fetchPrevClosesZig(rows) {
  if (!rows.length) return new Map();

  const params = [];
  const valuesSQL = rows
    .map((r, idx) => {
      const i = idx * 2;
      params.push(r.pool_id, r.bucket_start);
      return `($${i + 1}::BIGINT, $${i + 2}::timestamptz)`;
    })
    .join(',');

  const sql = `
    WITH keys(pool_id, bucket_start) AS (
      VALUES ${valuesSQL}
    )
    SELECT k.pool_id, k.bucket_start, o.close
    FROM keys k
    LEFT JOIN ohlcv_1m o
      ON o.pool_id = k.pool_id
     AND o.bucket_start = (k.bucket_start - INTERVAL '1 minute')
  `;

  const { rows: prevs } = await DB.query(sql, params);
  const out = new Map();
  for (const r of prevs) {
    const k = keyOf(r.pool_id, r.bucket_start);
    out.set(k, r.close == null ? null : Number(r.close));
  }
  return out;
}

function buildInsertSQLZig(rowsWithOpens) {
  const cols = [
    'pool_id',
    'bucket_start',
    'open',
    'high',
    'low',
    'close',
    'volume_zig',
    'trade_count',
    'liquidity_zig',
  ];
  const placeholders = [];
  const args = [];
  let p = 1;
  for (const r of rowsWithOpens) {
    placeholders.push(
      `($${p++},$${p++},$${p++},$${p++},$${p++},$${p++},$${p++},$${p++},$${p++})`
    );
    args.push(
      r.pool_id,
      r.bucket_start,
      r.open,
      r.high,
      r.low,
      r.close,
      r.volume_zig || 0,
      r.trade_count || 0,
      r.liquidity_zig ?? null
    );
  }

  const sql = `
    INSERT INTO ohlcv_1m
      (${cols.join(',')})
    VALUES
      ${placeholders.join(',')}
    ON CONFLICT (pool_id, bucket_start) DO UPDATE
      SET high          = GREATEST(ohlcv_1m.high, EXCLUDED.high),
          low           = LEAST(ohlcv_1m.low,  EXCLUDED.low),
          close         = EXCLUDED.close,
          volume_zig    = ohlcv_1m.volume_zig + EXCLUDED.volume_zig,
          trade_count   = ohlcv_1m.trade_count + EXCLUDED.trade_count,
          liquidity_zig = COALESCE(EXCLUDED.liquidity_zig, ohlcv_1m.liquidity_zig)
  `;
  return { sql, args };
}

/**
 * USD-side aggregation
 */
function aggregateBatchUsd(items) {
  const map = new Map();
  for (const it of items) {
    const k = keyOf(it.pool_id, it.bucket_start);
    const prev = map.get(k);
    if (!prev) {
      map.set(k, {
        pool_id: it.pool_id,
        bucket_start: it.bucket_start,
        high: it.price,
        low: it.price,
        close: it.price,
        volume_usd: it.vol_usd || 0,
        trade_count: it.trade_inc || 0,
        liquidity_usd: it.liquidity_usd ?? null,
      });
    } else {
      if (it.price > prev.high) prev.high = it.price;
      if (it.price < prev.low) prev.low = it.price;
      prev.close = it.price;
      prev.volume_usd += it.vol_usd || 0;
      prev.trade_count += it.trade_inc || 0;
      if (it.liquidity_usd != null) prev.liquidity_usd = it.liquidity_usd;
    }
  }
  return Array.from(map.values());
}

async function fetchPrevClosesUsd(rows) {
  if (!rows.length) return new Map();

  const params = [];
  const valuesSQL = rows
    .map((r, idx) => {
      const i = idx * 2;
      params.push(r.pool_id, r.bucket_start);
      return `($${i + 1}::BIGINT, $${i + 2}::timestamptz)`;
    })
    .join(',');

  const sql = `
    WITH keys(pool_id, bucket_start) AS (
      VALUES ${valuesSQL}
    )
    SELECT k.pool_id, k.bucket_start, o.close
    FROM keys k
    LEFT JOIN ohlcv_1m_usd o
      ON o.pool_id = k.pool_id
     AND o.bucket_start = (k.bucket_start - INTERVAL '1 minute')
  `;

  const { rows: prevs } = await DB.query(sql, params);
  const out = new Map();
  for (const r of prevs) {
    const k = keyOf(r.pool_id, r.bucket_start);
    out.set(k, r.close == null ? null : Number(r.close));
  }
  return out;
}

function buildInsertSQLUsd(rowsWithOpens) {
  const cols = [
    'pool_id',
    'bucket_start',
    'open',
    'high',
    'low',
    'close',
    'volume_usd',
    'trade_count',
    'liquidity_usd',
  ];
  const placeholders = [];
  const args = [];
  let p = 1;
  for (const r of rowsWithOpens) {
    placeholders.push(
      `($${p++},$${p++},$${p++},$${p++},$${p++},$${p++},$${p++},$${p++},$${p++})`
    );
    args.push(
      r.pool_id,
      r.bucket_start,
      r.open,
      r.high,
      r.low,
      r.close,
      r.volume_usd || 0,
      r.trade_count || 0,
      r.liquidity_usd ?? null
    );
  }

  const sql = `
    INSERT INTO ohlcv_1m_usd
      (${cols.join(',')})
    VALUES
      ${placeholders.join(',')}
    ON CONFLICT (pool_id, bucket_start) DO UPDATE
      SET high           = GREATEST(ohlcv_1m_usd.high, EXCLUDED.high),
          low            = LEAST(ohlcv_1m_usd.low,  EXCLUDED.low),
          close          = EXCLUDED.close,
          volume_usd     = ohlcv_1m_usd.volume_usd + EXCLUDED.volume_usd,
          trade_count    = ohlcv_1m_usd.trade_count + EXCLUDED.trade_count,
          liquidity_usd  = COALESCE(EXCLUDED.liquidity_usd, ohlcv_1m_usd.liquidity_usd)
  `;
  return { sql, args };
}

/**
 * -------------- ZIG OHLCV QUEUE --------------
 */

const ohlcvQueue = new BatchQueue({
  maxItems: Number(process.env.OHLCV_BATCH_MAX || 600),
  maxWaitMs: Number(process.env.OHLCV_BATCH_WAIT_MS || 120),
  flushFn: async (items) => {
    const agg = aggregateBatchZig(items);
    const prevMap = await fetchPrevClosesZig(agg);
    const rowsWithOpens = agg.map((r) => {
      const k = keyOf(r.pool_id, r.bucket_start);
      const prevClose = prevMap.get(k);
      const openVal = prevClose ?? r.close; // 👈 open = previous close, or close if none
      return { ...r, open: openVal };
    });
    const { sql, args } = buildInsertSQLZig(rowsWithOpens);
    await DB.query(sql, args);
  },
});

/**
 * price: candle price to merge (in quote token units for that pair)
 */
export async function upsertOHLCV1m({
  pool_id,
  bucket_start,
  price,
  vol_zig,
  trade_inc,
  liquidity_zig = null,
}) {
  ohlcvQueue.push({
    pool_id,
    bucket_start,
    price,
    vol_zig: vol_zig || 0,
    trade_inc: trade_inc || 0,
    liquidity_zig,
  });
}

/**
 * -------------- USD OHLCV QUEUE --------------
 */

const ohlcvUsdQueue = new BatchQueue({
  maxItems: Number(process.env.OHLCV_USD_BATCH_MAX || 600),
  maxWaitMs: Number(process.env.OHLCV_USD_BATCH_WAIT_MS || 120),
  flushFn: async (items) => {
    const agg = aggregateBatchUsd(items);
    const prevMap = await fetchPrevClosesUsd(agg);
    const rowsWithOpens = agg.map((r) => {
      const k = keyOf(r.pool_id, r.bucket_start);
      const prevClose = prevMap.get(k);
      const openVal = prevClose ?? r.close;
      return { ...r, open: openVal };
    });
    const { sql, args } = buildInsertSQLUsd(rowsWithOpens);
    await DB.query(sql, args);
  },
});

/**
 * price: candle price in USD (for ZIG-quote pools)
 */
export async function upsertOHLCV1mUsd({
  pool_id,
  bucket_start,
  price,
  vol_usd,
  trade_inc,
  liquidity_usd = null,
}) {
  ohlcvUsdQueue.push({
    pool_id,
    bucket_start,
    price,
    vol_usd: vol_usd || 0,
    trade_inc: trade_inc || 0,
    liquidity_usd,
  });
}

export async function drainOHLCV() {
  await ohlcvQueue.drain();
  await ohlcvUsdQueue.drain();
}

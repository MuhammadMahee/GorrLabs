// jobs/fx-zig-backfill.js
import { fetch } from 'undici';
import { DB } from '../lib/db.js';
import { info, warn } from '../lib/log.js';

const CMC_KEY     = process.env.CMC_API_KEY;
const CMC_SYMBOL  = process.env.CMC_SYMBOL || 'ZIG';
const CMC_CONVERT = process.env.CMC_CONVERT || 'USD';

// default from your requirement
const BACKFILL_START_ISO = '2025-09-27T21:31:14.441807Z';

const CMC_BASE_URL =
  'https://pro-api.coinmarketcap.com/v1/cryptocurrency/ohlcv/historical';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function fetchOhlcvHourly({ timeStart, timeEnd }) {
  if (!CMC_KEY) {
    throw new Error('CMC_API_KEY not set for OHLCV backfill');
  }

  const params = new URLSearchParams({
    symbol: CMC_SYMBOL,
    time_period: 'hourly',
    interval: '1h',
    time_start: timeStart.toISOString(),
    time_end: timeEnd.toISOString(),
    convert: CMC_CONVERT,
    // we can hint count, but for this range it's well under 10k
    // if you later backfill larger ranges, you may want to chunk
  });

  const url = `${CMC_BASE_URL}?${params.toString()}`;

  let backoff = 1500;
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(url, {
      headers: {
        accept: 'application/json',
        'X-CMC_PRO_API_KEY': CMC_KEY,
      },
    });

    if (res.status === 200) {
      const j = await res.json();
      const data = j?.data;
      if (!data) {
        throw new Error('CMC OHLCV: no data field');
      }

      // v2 format: data can be keyed by symbol or id
      let series = [];
      if (Array.isArray(data)) {
        // very unlikely for single symbol, but just in case
        const first = data[0];
        series = first?.quotes || [];
      } else if (data[CMC_SYMBOL]?.quotes) {
        series = data[CMC_SYMBOL].quotes;
      } else if (data.quotes) {
        series = data.quotes;
      } else {
        // fall back: take first key
        const firstKey = Object.keys(data)[0];
        series = data[firstKey]?.quotes || [];
      }

      if (!Array.isArray(series) || !series.length) {
        warn('[fx-backfill] CMC OHLCV: empty quotes array');
        return [];
      }
      return series;
    }

    if (res.status === 429 || res.status >= 500) {
      warn(`[fx-backfill] CMC ${res.status} → retry in ${backoff}ms`);
      await sleep(backoff);
      backoff = Math.min(backoff * 2, 15000);
      continue;
    }

    const text = await res.text();
    throw new Error(`CMC OHLCV ${res.status}: ${text.slice(0, 200)}`);
  }

  throw new Error('CMC OHLCV retries exhausted');
}

export async function runFxBackfill() {
  const start = new Date(BACKFILL_START_ISO);
  const end   = new Date(); // “when the job is started”

  if (Number.isNaN(start.getTime())) {
    throw new Error(`Invalid FX_BACKFILL_START: ${BACKFILL_START_ISO}`);
  }

  if (start >= end) {
    info('[fx-backfill] start >= end, nothing to do');
    return;
  }

  info('[fx-backfill] starting from', start.toISOString(), 'to', end.toISOString());

  const quotes = await fetchOhlcvHourly({ timeStart: start, timeEnd: end });

  let inserted = 0;
  for (const q of quotes) {
    const tClose = q.time_close || q.time_open || q.timestamp;
    const quoteObj = q.quote?.[CMC_CONVERT];

    if (!tClose || !quoteObj) continue;

    const price = Number(quoteObj.close);
    if (!Number.isFinite(price)) continue;

    // align to the minute like fx-zig.js
    const ts = new Date(tClose);

    await DB.query(
      `INSERT INTO exchange_rates (ts, zig_usd)
       VALUES (date_trunc('minute', $1::timestamptz), $2::numeric)
       ON CONFLICT (ts) DO UPDATE SET zig_usd = EXCLUDED.zig_usd`,
      [ts.toISOString(), price]
    );

    inserted += 1;
  }

  info(`[fx-backfill] inserted/updated ${inserted} rows into exchange_rates`);
}

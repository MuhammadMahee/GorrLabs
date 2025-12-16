// jobs/ibc-market-refresher.js
import { fetch } from 'undici';
import { DB } from '../lib/db.js';
import { info, warn } from '../lib/log.js';

const CMC_KEY = process.env.CMC_API_KEY;
const IBC_REFRESH_SEC = parseInt(process.env.IBC_REFRESH_SEC || '300', 10); // 5 min default
const MAX_SYMBOLS_PER_CALL = 50; // CMC allows quite a few, keep it sane

function chunk(arr, n) {
  const out = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
}

async function loadIbcTokens() {
  const { rows } = await DB.query(
    `
      SELECT
        token_id,
        denom,
        COALESCE(cmc_symbol, symbol) AS cmc_symbol
      FROM tokens
      WHERE type = 'ibc'
        AND COALESCE(cmc_symbol, symbol) IS NOT NULL
      ORDER BY token_id
    `
  );
  return rows;
}


async function fetchQuotesForSymbols(symbols) {
  if (!CMC_KEY) throw new Error('CMC_API_KEY not set for IBC market refresher');
  if (!symbols.length) return {};

  const url = `https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol=${encodeURIComponent(
    symbols.join(',')
  )}`;

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
      const data = j?.data || {};
      // data is keyed by symbol: { WBTC: { ... }, ... }
      return data;
    }

    if (res.status === 429 || res.status >= 500) {
      warn(`[ibc-market] CMC ${res.status} → retry in ${backoff}ms`);
      await new Promise((r) => setTimeout(r, backoff));
      backoff = Math.min(backoff * 2, 15000);
      continue;
    }

    const text = await res.text();
    throw new Error(`CMC IBC quotes ${res.status}: ${text.slice(0, 200)}`);
  }

  throw new Error('CMC IBC retries exhausted');
}

async function refreshOnce() {
  const ibcTokens = await loadIbcTokens();
  console.log("this is ibc token",ibcTokens);
  if (!ibcTokens.length) {
    info('[ibc-market] no IBC tokens with cmc_symbol configured');
    return;
  }

  info(
    '[ibc-market] refreshing IBC market data for',
    ibcTokens.length,
    'tokens'
  );

  const chunks = chunk(ibcTokens, MAX_SYMBOLS_PER_CALL);
  let updated = 0;

  for (const group of chunks) {
    const symbols = Array.from(
      new Set(group.map((t) => (t.cmc_symbol || '').trim()).filter(Boolean))
    );
    if (!symbols.length) continue;

    let data;
    try {
      data = await fetchQuotesForSymbols(symbols);
    } catch (e) {
      warn('[ibc-market] fetch error', e.message || e);
      continue;
    }

    // Upsert per token
    for (const tok of group) {
      const sym = (tok.cmc_symbol || '').trim();
      const entry = data?.[sym];
      if (!entry) {
        warn(
          '[ibc-market] missing CMC data for',
          sym,
          ' (token_id=',
          tok.token_id,
          ', denom=',
          tok.denom,
          ')'
        );
        continue;
      }

      const qUsd = entry.quote?.USD;
      if (!qUsd) {
        warn(
          '[ibc-market] no USD quote for',
          sym,
          ' (token_id=',
          tok.token_id,
          ')'
        );
        continue;
      }

      const priceUsd = Number(qUsd.price);
      const mcapUsd = Number(qUsd.market_cap);
      const circ = Number(entry.circulating_supply);
      const total = Number(entry.total_supply);

      // sanity checks
      const priceUsdClean =
        Number.isFinite(priceUsd) && priceUsd > 0 ? priceUsd : null;
      const mcapUsdClean =
        Number.isFinite(mcapUsd) && mcapUsd > 0 ? mcapUsd : null;
      const circClean = Number.isFinite(circ) && circ >= 0 ? circ : null;
      const totalClean = Number.isFinite(total) && total >= 0 ? total : null;

      await DB.query(
        `
          INSERT INTO ibc_token_stats
            (token_id, price_usd, market_cap_usd, circulating_supply, total_supply, last_updated)
          VALUES ($1, $2, $3, $4, $5, now())
          ON CONFLICT (token_id) DO UPDATE
            SET price_usd          = EXCLUDED.price_usd,
                market_cap_usd     = EXCLUDED.market_cap_usd,
                circulating_supply = EXCLUDED.circulating_supply,
                total_supply       = EXCLUDED.total_supply,
                last_updated       = now()
        `,
        [tok.token_id, priceUsdClean, mcapUsdClean, circClean, totalClean]
      );

      updated++;
    }
  }

  info('[ibc-market] updated IBC stats rows =', updated);
}

export function startIbcMarketRefresher() {
  (async function loop() {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      try {
        await refreshOnce();
      } catch (e) {
        warn('[ibc-market]', e.message || e);
      }
      await new Promise((r) => setTimeout(r, IBC_REFRESH_SEC * 1000));
    }
  })().catch(() => {});
}

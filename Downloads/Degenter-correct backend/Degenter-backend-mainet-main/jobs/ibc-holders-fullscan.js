// jobs/ibc-holders-fullscan.js
import { fetch } from 'undici';
import { DB } from '../lib/db.js';
import { info, warn, debug } from '../lib/log.js';

const LCD_URL =
  process.env.LCD_URL || 'https://zigchain-mainnet-api.wickhub.cc';
const IBC_HOLDERS_INTERVAL_SEC = parseInt(
  process.env.IBC_HOLDERS_INTERVAL_SEC || String(24 * 3600),
  10
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function ensureTmpTable() {
  await DB.query(`
    CREATE TABLE IF NOT EXISTS public.ibc_holders_tmp (
      token_id      BIGINT        NOT NULL,
      address       TEXT          NOT NULL,
      balance_base  NUMERIC(78,0) NOT NULL,
      PRIMARY KEY (token_id, address)
    );
  `);
  await DB.query(`TRUNCATE public.ibc_holders_tmp;`);
}

// load all IBC tokens we care about (type='ibc')
async function loadIbcTokens() {
  const { rows } = await DB.query(
    `
      SELECT token_id, denom
      FROM tokens
      WHERE type = 'ibc'
      ORDER BY token_id
    `
  );
  const denomToTokenId = new Map();
  for (const r of rows) {
    denomToTokenId.set(r.denom, Number(r.token_id));
  }
  return denomToTokenId;
}

// properly extract address for all account types
function extractAddress(acc) {
  if (!acc) return null;
  // common shape: { address: "zig..." }
  if (acc.address) return acc.address;

  // base account
  if (acc.base_account?.address) return acc.base_account.address;

  // vesting: { base_vesting_account: { base_account: { address } } }
  if (acc.base_vesting_account?.base_account?.address) {
    return acc.base_vesting_account.base_account.address;
  }

  // some SDK types embed base_account
  if (
    acc['@type'] &&
    typeof acc['@type'] === 'string' &&
    acc['@type'].includes('BaseAccount') &&
    acc.base_account?.address
  ) {
    return acc.base_account.address;
  }

  return null;
}

// stream all accounts via pagination
async function *iterateAllAccounts() {
  let nextKey = null;
  let page = 0;
  while (true) {
    const url =
      `${LCD_URL}/cosmos/auth/v1beta1/accounts` +
      `?pagination.limit=100` +
      (nextKey ? `&pagination.key=${encodeURIComponent(nextKey)}` : '');

    const res = await fetch(url);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(
        `auth/accounts HTTP ${res.status}: ${text.slice(0, 200)}`
      );
    }
    const j = await res.json();
    const accounts = j.accounts || [];
    page += 1;
    debug('[ibc-holders] accounts page', page, 'size', accounts.length);

    for (const acc of accounts) {
      const addr = extractAddress(acc);
      if (!addr) continue;
      yield addr;
    }

    nextKey = j.pagination?.next_key || null;
    if (!nextKey) break;
  }
}

// fetch all balances for an address once
async function fetchBalancesForAddress(address) {
  const url = `${LCD_URL}/cosmos/bank/v1beta1/balances/${address}?pagination.limit=1000`;
  const res = await fetch(url);
  if (res.status === 404) {
    return [];
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `bank/balances HTTP ${res.status} for ${address}: ${text.slice(0, 200)}`
    );
  }
  const j = await res.json();
  return j.balances || [];
}

async function fullScanOnce() {
  info('[ibc-holders] full scan started');

  await ensureTmpTable();

  const denomToTokenId = await loadIbcTokens();
  if (denomToTokenId.size === 0) {
    info('[ibc-holders] no IBC tokens (type=ibc) in tokens table');
    return;
  }
  const ibcTokenIds = Array.from(denomToTokenId.values());
  info(
    '[ibc-holders] IBC tokens configured =',
    ibcTokenIds.length
  );

  let addrCount = 0;
  let holderRows = 0;

  for await (const addr of iterateAllAccounts()) {
    addrCount += 1;
    try {
      const balances = await fetchBalancesForAddress(addr);
      for (const b of balances) {
        const denom = b.denom;
        if (!denom || !denom.startsWith('ibc/')) continue;
        const tokenId = denomToTokenId.get(denom);
        if (!tokenId) continue; // IBC denom we don't index as a token

        const amountStr = String(b.amount || '0');
        if (!/^\d+$/.test(amountStr)) continue;
        if (amountStr === '0') continue;

        await DB.query(
          `
            INSERT INTO ibc_holders_tmp (token_id, address, balance_base)
            VALUES ($1, $2, $3::numeric)
            ON CONFLICT (token_id, address) DO UPDATE
              SET balance_base = EXCLUDED.balance_base
          `,
          [tokenId, addr, amountStr]
        );
        holderRows += 1;
      }
    } catch (e) {
      warn('[ibc-holders] balances error for', addr, e.message || e);
    }

    // avoid hammering LCD
    await sleep(50);
  }

  info(
    '[ibc-holders] scan done, addresses seen =',
    addrCount,
    ', ibc holder rows =',
    holderRows
  );

  if (holderRows === 0) {
    info(
      '[ibc-holders] no non-zero IBC balances found; skipping swap into holders'
    );
    return;
  }

  // swap tmp into holders + stats in one transaction
  await DB.query('BEGIN');

  try {
    await DB.query(
      `
        DELETE FROM holders
        WHERE token_id = ANY($1::bigint[])
      `,
      [ibcTokenIds]
    );

    await DB.query(
      `
        INSERT INTO holders (token_id, address, balance_base, updated_at, last_seen_height)
        SELECT token_id,
               address,
               balance_base,
               now() AS updated_at,
               NULL::bigint AS last_seen_height
        FROM ibc_holders_tmp
      `
    );

    await DB.query(
      `
        INSERT INTO token_holders_stats (token_id, holders_count, updated_at)
        SELECT token_id,
               COUNT(*)::bigint AS holders_count,
               now()            AS updated_at
        FROM ibc_holders_tmp
        GROUP BY token_id
        ON CONFLICT (token_id) DO UPDATE
          SET holders_count = EXCLUDED.holders_count,
              updated_at    = EXCLUDED.updated_at
      `
    );

    await DB.query(
      `
        UPDATE token_security s
        SET holders_count = h.c
        FROM (
          SELECT token_id, COUNT(*)::bigint AS c
          FROM ibc_holders_tmp
          GROUP BY token_id
        ) h
        WHERE s.token_id = h.token_id
      `
    );

    await DB.query('COMMIT');
    info('[ibc-holders] swap into holders + stats committed');
  } catch (e) {
    await DB.query('ROLLBACK');
    warn('[ibc-holders] swap failed, rolled back:', e.message || e);
    throw e;
  } finally {
    await DB.query('TRUNCATE ibc_holders_tmp;');
  }
}

export function startIbcHoldersFullscan() {
  (async function loop() {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      try {
        await fullScanOnce();
      } catch (e) {
        warn('[ibc-holders]', e.message || e);
      }
      info(
        '[ibc-holders] sleeping for',
        IBC_HOLDERS_INTERVAL_SEC,
        'seconds'
      );
      await sleep(IBC_HOLDERS_INTERVAL_SEC * 1000);
    }
  })().catch(() => {});
}

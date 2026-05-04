// core/adapters/astroport-v2.js
// Extracted swap/liquidity parsing for Astroport/Oroswap-style WASM DEX.
import {
  wasmByAction,
  parseReservesKV,
  parseAssetsList,
  digitsOrNull,
  classifyDirection,
} from '../parse.js';
import { dec } from '../../lib/decimal.js';

function baseToDisp(raw, exp) {
  if (raw == null) return null;
  return dec(raw).div(dec(10).pow(exp ?? 0));
}

export function parseCreatePairs({ wasms, insts, msgSenderByIndex }) {
  const out = [];
  const cps = wasmByAction(wasms, 'create_pair');
  for (const cp of cps) {
    const factoryAddr = (cp.m.get('_contract_address') || '').trim();
    const pairType = String(cp.m.get('pair_type') || 'xyk');
    const [base, quoteRaw] = String(cp.m.get('pair') || '').split('-');
    const baseDenom = base || null;
    const quoteDenom = quoteRaw || null;
    const reg = wasms.find(
      (w) =>
        w.m.get('action') === 'register' &&
        w.m.get('_contract_address') === factoryAddr
    );
    const poolAddr =
      reg?.m.get('pair_contract_addr') || insts.at(-1)?.m.get('_contract_address');
    const signer = msgSenderByIndex.get(Number(cp.m.get('msg_index'))) || null;
    if (poolAddr && baseDenom && quoteDenom) {
      out.push({
        factoryAddr,
        poolAddr,
        pairType,
        baseDenom,
        quoteDenom,
        signer,
      });
    }
  }
  return out;
}

export function parseSwaps({ wasms, msgSenderByIndex, executes, poolMapByContract, routerAddr = null }) {
  const out = [];
  // capture swap-like actions (swap, router_swap, swap_tokens etc.)
  const swaps = wasms.filter((w) => {
    const act = (w.m.get('action') || '').toLowerCase();
    return act === 'swap' || act === 'router_swap' || act === 'swap_tokens' || act === 'swap_exact' || act === 'router';
  });
  const seen = new Set();
  for (let idx = 0; idx < swaps.length; idx++) {
    const s = swaps[idx];
    let pairContract = s.m.get('_contract_address');
    const altPair = s.m.get('pair_contract') || s.m.get('pair_contract_addr');
    if (!pairContract && altPair) pairContract = altPair;
    if (!pairContract) continue;
    let pool = poolMapByContract.get(pairContract);
    // fallback: if event pointed to router, try the altPair above
    if (!pool && altPair) pool = poolMapByContract.get(altPair);
    if (!pool) continue;

    const offer = s.m.get('offer_asset') || s.m.get('offer_asset_denom');
    const ask = s.m.get('ask_asset') || s.m.get('ask_asset_denom');
    const offerAmt = digitsOrNull(s.m.get('offer_amount'));
    const askAmt = digitsOrNull(s.m.get('ask_amount'));
    const retAmt = digitsOrNull(s.m.get('return_amount'));

    let res1d = s.m.get('reserve_asset1_denom') || s.m.get('asset1_denom') || null;
    let res1a = digitsOrNull(s.m.get('reserve_asset1_amount') || s.m.get('asset1_amount'));
    let res2d = s.m.get('reserve_asset2_denom') || s.m.get('asset2_denom') || null;
    let res2a = digitsOrNull(s.m.get('reserve_asset2_amount') || s.m.get('asset2_amount'));
    const reservesStr = s.m.get('reserves');
    if ((!res1d || !res1a || !res2d || !res2a) && reservesStr) {
      const kv = parseReservesKV(reservesStr);
      if (kv?.[0]) { res1d = res1d ?? kv[0].denom; res1a = res1a ?? digitsOrNull(kv[0].amount_base); }
      if (kv?.[1]) { res2d = res2d ?? kv[1].denom; res2a = res2a ?? digitsOrNull(kv[1].amount_base); }
    }

    const msgIndex = Number(s.m.get('msg_index') ?? idx);
    const signerEOA = msgSenderByIndex.get(msgIndex) || null;
    const isRouter = !!(
      routerAddr &&
      (s.m.get('sender') === routerAddr ||
        executes.some(
          (e) =>
            e.m.get('_contract_address') === routerAddr &&
            Number(e.m.get('msg_index') || -1) === msgIndex
        ))
    );

    const baseExp = pool.base_exp ?? 6;
    const quoteExp = pool.quote_exp ?? 6;

    out.push({
      type: 'swap',
      pairContract,
      pool,
      offer,
      ask,
      offerAmt,
      askAmt,
      retAmt,
      res1d,
      res1a,
      res2d,
      res2a,
      msgIndex,
      signerEOA,
      isRouter,
      baseExp,
      quoteExp,
      offerDisp: offerAmt ? baseToDisp(offerAmt, offer === pool.base_denom ? baseExp : quoteExp) : null,
      askDisp: askAmt ? baseToDisp(askAmt, ask === pool.base_denom ? baseExp : quoteExp) : null,
      retDisp: retAmt ? baseToDisp(retAmt, ask === pool.base_denom ? baseExp : quoteExp) : null,
      res1Disp: res1a ? baseToDisp(res1a, res1d === pool.base_denom ? baseExp : quoteExp) : null,
      res2Disp: res2a ? baseToDisp(res2a, res2d === pool.base_denom ? baseExp : quoteExp) : null,
    });
    seen.add(`${pairContract}:${msgIndex}`);
  }

  // Fallback: capture swap-like events even if action tag isn't exactly "swap"
  for (const s of wasms) {
    const action = s.m.get('action');
    if (action === 'swap' || action === 'provide_liquidity' || action === 'withdraw_liquidity' || action === 'create_pair') continue;
    const pairContract = s.m.get('_contract_address');
    if (!pairContract) continue;
    const pool = poolMapByContract.get(pairContract);
    if (!pool) continue;

    const msgIndex = Number(s.m.get('msg_index') ?? -1);
    if (seen.has(`${pairContract}:${msgIndex}`)) continue;

    const offer = s.m.get('offer_asset') || s.m.get('offer_asset_denom') || s.m.get('offer');
    const ask = s.m.get('ask_asset') || s.m.get('ask_asset_denom') || s.m.get('ask');
    const offerAmt = digitsOrNull(s.m.get('offer_amount'));
    const askAmt = digitsOrNull(s.m.get('ask_amount'));
    const retAmt = digitsOrNull(s.m.get('return_amount') || s.m.get('return'));
    if (!offer && !ask && !offerAmt && !retAmt) continue; // not swap-like

    let res1d = s.m.get('reserve_asset1_denom') || s.m.get('asset1_denom') || null;
    let res1a = digitsOrNull(s.m.get('reserve_asset1_amount') || s.m.get('asset1_amount'));
    let res2d = s.m.get('reserve_asset2_denom') || s.m.get('asset2_denom') || null;
    let res2a = digitsOrNull(s.m.get('reserve_asset2_amount') || s.m.get('asset2_amount'));
    const reservesStr = s.m.get('reserves');
    if ((!res1d || !res1a || !res2d || !res2a) && reservesStr) {
      const kv = parseReservesKV(reservesStr);
      if (kv?.[0]) { res1d = res1d ?? kv[0].denom; res1a = res1a ?? digitsOrNull(kv[0].amount_base); }
      if (kv?.[1]) { res2d = res2d ?? kv[1].denom; res2a = res2a ?? digitsOrNull(kv[1].amount_base); }
    }

    const signerEOA = msgSenderByIndex.get(msgIndex) || null;
    const baseExp = pool.base_exp ?? 6;
    const quoteExp = pool.quote_exp ?? 6;

    out.push({
      type: 'swap',
      pairContract,
      pool,
      offer,
      ask,
      offerAmt,
      askAmt,
      retAmt,
      res1d,
      res1a,
      res2d,
      res2a,
      msgIndex,
      signerEOA,
      isRouter: false,
      baseExp,
      quoteExp,
      offerDisp: offerAmt ? baseToDisp(offerAmt, offer === pool.base_denom ? baseExp : quoteExp) : null,
      askDisp: askAmt ? baseToDisp(askAmt, ask === pool.base_denom ? baseExp : quoteExp) : null,
      retDisp: retAmt ? baseToDisp(retAmt, ask === pool.base_denom ? baseExp : quoteExp) : null,
      res1Disp: res1a ? baseToDisp(res1a, res1d === pool.base_denom ? baseExp : quoteExp) : null,
      res2Disp: res2a ? baseToDisp(res2a, res2d === pool.base_denom ? baseExp : quoteExp) : null,
    });
    seen.add(`${pairContract}:${msgIndex}`);
  }
  return out;
}

export function parseLiquidity({ wasms, msgSenderByIndex, poolMapByContract }) {
  const out = [];
  const provides = wasmByAction(wasms, 'provide_liquidity');
  const withdraws = wasmByAction(wasms, 'withdraw_liquidity');
  const liqs = [...provides, ...withdraws];

  for (let li = 0; li < liqs.length; li++) {
    const le = liqs[li];
    const pairContract = le.m.get('_contract_address');
    if (!pairContract) continue;
    const pool = poolMapByContract.get(pairContract);
    if (!pool) continue;
    const isProvide = le.m.get('action') === 'provide_liquidity';
    const action = isProvide ? 'provide' : 'withdraw';

    let res1d = le.m.get('reserve_asset1_denom') || null;
    let res1a = digitsOrNull(le.m.get('reserve_asset1_amount'));
    let res2d = le.m.get('reserve_asset2_denom') || null;
    let res2a = digitsOrNull(le.m.get('reserve_asset2_amount'));

    const assetsStr = isProvide ? le.m.get('assets') : le.m.get('refund_assets');
    if ((!res1d || !res1a || !res2d || !res2a) && assetsStr) {
      const parsed = parseAssetsList(assetsStr);
      if (parsed?.a1) { res1d = res1d ?? parsed.a1.denom; res1a = res1a ?? digitsOrNull(parsed.a1.amount_base); }
      if (parsed?.a2) { res2d = res2d ?? parsed.a2.denom; res2a = res2a ?? digitsOrNull(parsed.a2.amount_base); }
    }

    const reservesStr = le.m.get('reserves');
    if ((!res1d || !res1a || !res2d || !res2a) && reservesStr) {
      const kv = parseReservesKV(reservesStr);
      if (kv?.[0]) { res1d = res1d ?? kv[0].denom; res1a = res1a ?? digitsOrNull(kv[0].amount_base); }
      if (kv?.[1]) { res2d = res2d ?? kv[1].denom; res2a = res2a ?? digitsOrNull(kv[1].amount_base); }
    }

    const shareBase = digitsOrNull(
      isProvide
        ? le.m.get('share')
        : le.m.get('withdrawn_share') ||
          le.m.get('withdraw_share') ||
          le.m.get('liquidity') ||
          le.m.get('burn_share') ||
          le.m.get('burnt_share') ||
          le.m.get('share')
    );

    const msgIndex = Number(le.m.get('msg_index') ?? li);
    const signerEOA = msgSenderByIndex.get(msgIndex) || null;

    const baseExp = pool.base_exp ?? 6;
    const quoteExp = pool.quote_exp ?? 6;

    out.push({
      type: 'liquidity',
      action,
      pairContract,
      pool,
      res1d,
      res1a,
      res2d,
      res2a,
      shareBase,
      msgIndex,
      signerEOA,
      baseExp,
      quoteExp,
      res1Disp: res1a ? baseToDisp(res1a, res1d === pool.base_denom ? baseExp : quoteExp) : null,
      res2Disp: res2a ? baseToDisp(res2a, res2d === pool.base_denom ? baseExp : quoteExp) : null,
      shareDisp: shareBase ? baseToDisp(shareBase, baseExp) : null,
    });
  }
  return out;
}

// Derivations: price/value/TVL/OHLCV using display units provided by parseSwaps/liquidity.
export async function computeSwapDerived(sw, pool, { zigUsd, priceLookup }) {
  const baseExp = sw.baseExp ?? pool.base_exp ?? 6;
  const quoteExp = sw.quoteExp ?? pool.quote_exp ?? 6;

  // price in quote from reserves (display)
  const baseDisp = sw.res1d === pool.base_denom ? dec(sw.res1Disp || 0) : dec(sw.res2Disp || 0);
  const quoteDisp = sw.res1d === pool.base_denom ? dec(sw.res2Disp || 0) : dec(sw.res1Disp || 0);
  let priceInQuote = null;
  if (baseDisp.gt(0) && quoteDisp.gt(0)) {
    priceInQuote = quoteDisp.div(baseDisp);
  }

  let quotePriceInZig = pool.is_uzig_quote ? dec(1) : null;
  if (!quotePriceInZig && typeof priceLookup === 'function') {
    const p = await priceLookup(pool.quote_id);
    if (p && p.gt(0)) quotePriceInZig = p;
  }

  let priceInZig = null;
  let priceInUsd = null;
  let valueInQuote = null;
  let valueInZig = null;
  let valueInUsd = null;
  if (priceInQuote && quotePriceInZig) {
    priceInZig = priceInQuote.mul(quotePriceInZig);
    valueInQuote = (sw.offer === pool.quote_denom ? dec(sw.offerDisp || 0) : dec(sw.retDisp || 0));
    valueInZig = valueInQuote.mul(quotePriceInZig);
    if (zigUsd != null) {
      const zu = dec(zigUsd);
      if (zu.gt(0)) {
        priceInUsd = priceInZig.mul(zu);
        valueInUsd = valueInZig.mul(zu);
      }
    }
  }

  // TVL
  let tvlZig = null;
  let tvlUsd = null;
  if (quotePriceInZig && quotePriceInZig.gt(0) && baseDisp.gt(0) && quoteDisp.gt(0) && priceInQuote) {
    const basePriceInZig = priceInQuote.mul(quotePriceInZig);
    const baseTvlZig = baseDisp.mul(basePriceInZig);
    const quoteTvlZig = quoteDisp.mul(quotePriceInZig);
    tvlZig = baseTvlZig.add(quoteTvlZig);
    if (zigUsd != null) {
      const zu = dec(zigUsd);
      if (zu.gt(0)) tvlUsd = tvlZig.mul(zu);
    }
  }

  return {
    tradeRow: {
      offer_amount_base: sw.offerDisp,
      ask_amount_base: sw.askDisp,
      return_amount_base: sw.retDisp,
      reserve_asset1_amount_base: sw.res1Disp,
      reserve_asset2_amount_base: sw.res2Disp,
      price_in_quote: priceInQuote,
      price_in_zig: priceInZig,
      price_in_usd: priceInUsd,
      value_in_quote: valueInQuote,
      value_in_zig: valueInZig,
      value_in_usd: valueInUsd,
      quote_price_in_zig: quotePriceInZig,
    },
    poolState: {
      tvlZig,
      tvlUsd,
    },
    ohlcvZig: priceInQuote && valueInZig && valueInZig.gt(0)
      ? { price: priceInQuote, vol_zig: valueInZig, trade_inc: 1, liquidity_zig: tvlZig ?? null }
      : null,
    ohlcvUsd: pool.is_uzig_quote && priceInZig && valueInUsd && valueInUsd.gt(0)
      ? {
          price: priceInZig.mul(dec(zigUsd || 0)),
          vol_usd: valueInUsd,
          trade_inc: 1,
          liquidity_usd: tvlUsd ?? null,
        }
      : null,
    priceRow: priceInZig && priceInZig.gt(0)
      ? { token_id: pool.base_id, pool_id: pool.pool_id, price_in_zig: priceInZig, is_pair_native: pool.is_uzig_quote === true }
      : null,
    baseExp,
    quoteExp,
  };
}

export async function computeLiquidityDerived(liq, pool, { zigUsd, priceLookup }) {
  const baseExp = liq.baseExp ?? pool.base_exp ?? 6;
  const quoteExp = liq.quoteExp ?? pool.quote_exp ?? 6;

  let RbRaw = null;
  let RqRaw = null;
  if (liq.res1d === pool.base_denom && liq.res2d === pool.quote_denom) {
    RbRaw = liq.res1Disp;
    RqRaw = liq.res2Disp;
  } else if (liq.res2d === pool.base_denom && liq.res1d === pool.quote_denom) {
    RbRaw = liq.res2Disp;
    RqRaw = liq.res1Disp;
  }

  const Rb = dec(RbRaw || 0);
  const Rq = dec(RqRaw || 0);

  let tvlZig = null;
  let tvlUsd = null;

  if (Rb.gt(0) && Rq.gt(0)) {
    let quotePriceInZig = pool.is_uzig_quote ? dec(1) : null;
    if (!quotePriceInZig && typeof priceLookup === 'function') {
      const p = await priceLookup(pool.quote_id);
      if (p && p.gt(0)) quotePriceInZig = p;
    }
    if (quotePriceInZig && quotePriceInZig.gt(0)) {
      const priceInQuote = Rq.div(Rb);
      const basePriceInZig = priceInQuote.mul(quotePriceInZig);
      const baseTvlZig = Rb.mul(basePriceInZig);
      const quoteTvlZig = Rq.mul(quotePriceInZig);
      tvlZig = baseTvlZig.add(quoteTvlZig);
      if (zigUsd != null) {
        const zu = dec(zigUsd);
        if (zu.gt(0)) tvlUsd = tvlZig.mul(zu);
      }
    }
  }

  return {
    tradeRow: {
      return_amount_base: liq.shareDisp,
      reserve_asset1_amount_base: liq.res1Disp,
      reserve_asset2_amount_base: liq.res2Disp,
    },
    poolState: { tvlZig, tvlUsd },
    priceRow: pool.is_uzig_quote && Rb.gt(0) && Rq.gt(0)
      ? {
          token_id: pool.base_id,
          pool_id: pool.pool_id,
          price_in_zig: Rq.div(dec(10).pow(quoteExp)).div(Rb.div(dec(10).pow(baseExp))),
          is_pair_native: true,
        }
      : null,
    baseExp,
    quoteExp,
  };
}

export default {
  type: 'astroport-v2',
  match: ({ identifierType }) => identifierType === 'WASM_CONTRACT',
  parseCreatePairs,
  parseSwaps,
  parseLiquidity,
  computeSwapDerived,
  computeLiquidityDerived,
  helpers: { baseToDisp, classifyDirection },
};

import { TokensEntity } from './tokens.js';
import { PoolsEntity } from './pools.js';
import { TradesEntity } from './trades.js';
import { PoolStateEntity } from './pool_state.js';
import { PricesEntity } from './prices.js';
import { Ohlcv1mEntity } from './ohlcv_1m.js';
import { PoolMatrixEntity } from './pool_matrix.js';
import { TokenMatrixEntity } from './token_matrix.js';
import { IndexStateEntity } from './index_state.js';
import { HoldersEntity } from './holders.js';
import { TokenHoldersStatsEntity } from './token_holders_stats.js';
import { PriceTicksEntity } from './price_ticks.js';
import { LeaderboardTradersEntity } from './leaderboard_traders.js';
import { LargeTradesEntity } from './large_trades.js';
import { ExchangeRatesEntity } from './exchange_rates.js';
import { WalletsEntity } from './wallets.js';
import { WatchlistEntity } from './watchlist.js';
import { AlertsEntity } from './alerts.js';
import { AlertEventsEntity } from './alert_events.js';
import { TokenTwitterEntity } from './token_twitter.js';
import { Ohlcv1mUsdEntity } from './ohlcv_1m_usd.js';
import { IbcTokensEntity } from './ibc_tokens.js';
import { ExternalPricesEntity } from './external_prices.js';
import { IbcHoldersTmpEntity } from './ibc_holders_tmp.js';
import { IbcHolderCandidatesEntity } from './ibc_holder_candidates.js';

export const Entities = [
  TokensEntity,
  PoolsEntity,
  TradesEntity,
  PoolStateEntity,
  PricesEntity,
  Ohlcv1mEntity,
  Ohlcv1mUsdEntity,
  PoolMatrixEntity,
  TokenMatrixEntity,
  IndexStateEntity,
  HoldersEntity,
  TokenHoldersStatsEntity,
  PriceTicksEntity,
  LeaderboardTradersEntity,
  LargeTradesEntity,
  ExchangeRatesEntity,
  WalletsEntity,
  WatchlistEntity,
  AlertsEntity,
  AlertEventsEntity,
  TokenTwitterEntity,
  IbcTokensEntity,
  ExternalPricesEntity,
  IbcHoldersTmpEntity,
  IbcHolderCandidatesEntity,
];

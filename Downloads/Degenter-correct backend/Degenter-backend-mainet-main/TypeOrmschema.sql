-- Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enums
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='token_type') THEN
    CREATE TYPE token_type AS ENUM ('native','factory','ibc','cw20');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='pair_type') THEN
    CREATE TYPE pair_type AS ENUM ('xyk','concentrated','custom-concentrated');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='trade_action') THEN
    CREATE TYPE trade_action AS ENUM ('swap','provide','withdraw');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='trade_direction') THEN
    CREATE TYPE trade_direction AS ENUM ('buy','sell','provide','withdraw');
  END IF;
END$$;

-- Cast columns to enums
ALTER TABLE public.tokens ALTER COLUMN type TYPE token_type USING type::token_type;
ALTER TABLE public.pools  ALTER COLUMN pair_type TYPE pair_type USING pair_type::pair_type;
ALTER TABLE public.trades ALTER COLUMN action TYPE trade_action USING action::trade_action;
ALTER TABLE public.trades ALTER COLUMN direction TYPE trade_direction USING direction::trade_direction;
ALTER TABLE public.large_trades ALTER COLUMN direction TYPE trade_direction USING direction::trade_direction;

-- Hypertables (idempotent)
SELECT create_hypertable('public.trades', 'created_at', if_not_exists => TRUE);
SELECT create_hypertable('public.price_ticks', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('public.ohlcv_1m', 'bucket_start', if_not_exists => TRUE);

-- New USD OHLCV table
CREATE TABLE IF NOT EXISTS public.ohlcv_1m_usd (
  pool_id BIGINT NOT NULL REFERENCES public.pools(pool_id),
  bucket_start TIMESTAMPTZ NOT NULL,
  open NUMERIC(38,18) NOT NULL,
  high NUMERIC(38,18) NOT NULL,
  low NUMERIC(38,18) NOT NULL,
  close NUMERIC(38,18) NOT NULL,
  volume_usd NUMERIC(38,8) NOT NULL DEFAULT 0,
  trade_count INTEGER NOT NULL DEFAULT 0,
  liquidity_usd NUMERIC(38,8),
  PRIMARY KEY (pool_id, bucket_start)
);
SELECT create_hypertable('public.ohlcv_1m_usd', 'bucket_start', if_not_exists => TRUE);

-- Trade snapshot columns
ALTER TABLE public.trades
  ADD COLUMN IF NOT EXISTS price_in_quote NUMERIC(38,18),
  ADD COLUMN IF NOT EXISTS price_in_zig NUMERIC(38,18),
  ADD COLUMN IF NOT EXISTS price_in_usd NUMERIC(38,18),
  ADD COLUMN IF NOT EXISTS value_in_quote NUMERIC(38,8),
  ADD COLUMN IF NOT EXISTS value_in_zig NUMERIC(38,8),
  ADD COLUMN IF NOT EXISTS value_in_usd NUMERIC(38,8),
  ADD COLUMN IF NOT EXISTS quote_price_in_zig NUMERIC(38,18),
  ADD COLUMN IF NOT EXISTS zig_usd_at_trade NUMERIC(38,8);

-- Pool state TVL columns
ALTER TABLE public.pool_state
  ADD COLUMN IF NOT EXISTS tvl_zig NUMERIC(38,8),
  ADD COLUMN IF NOT EXISTS tvl_usd NUMERIC(38,8);

-- New tables: IBC metadata, external prices, temp holders/candidates
CREATE TABLE IF NOT EXISTS public.ibc_tokens (
  token_id BIGINT PRIMARY KEY REFERENCES public.tokens(token_id) ON DELETE CASCADE,
  base_denom TEXT,
  source_chain TEXT,
  source_channel TEXT,
  coingecko_id TEXT,
  cmc_id TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.external_prices (
  token_id BIGINT NOT NULL REFERENCES public.tokens(token_id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  price_usd NUMERIC(38,18) NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (token_id, source)
);
CREATE TABLE IF NOT EXISTS public.ibc_holders_tmp (
  token_id BIGINT NOT NULL,
  address TEXT NOT NULL,
  balance_base NUMERIC(78,0) NOT NULL,
  PRIMARY KEY (token_id, address)
);
CREATE TABLE IF NOT EXISTS public.ibc_holder_candidates (
  token_id BIGINT NOT NULL REFERENCES public.tokens(token_id),
  address TEXT NOT NULL,
  last_seen_h BIGINT NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (token_id, address)
);

-- Missing uniques
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='trades' AND indexname='uq_trades_tx_pool_msg_time') THEN
    CREATE UNIQUE INDEX uq_trades_tx_pool_msg_time ON public.trades (tx_hash, pool_id, msg_index, created_at);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='large_trades' AND indexname='ux_large_trades_tx_pool_dir') THEN
    CREATE UNIQUE INDEX ux_large_trades_tx_pool_dir ON public.large_trades (tx_hash, pool_id, direction);
  END IF;
END$$;

-- Check constraints
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_pool_matrix_bucket') THEN
    ALTER TABLE public.pool_matrix ADD CONSTRAINT ck_pool_matrix_bucket CHECK (bucket IN ('30m','1h','4h','24h'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_token_matrix_bucket') THEN
    ALTER TABLE public.token_matrix ADD CONSTRAINT ck_token_matrix_bucket CHECK (bucket IN ('30m','1h','4h','24h'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_leaderboard_bucket') THEN
    ALTER TABLE public.leaderboard_traders ADD CONSTRAINT ck_leaderboard_bucket CHECK (bucket IN ('30m','1h','4h','24h'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_large_trades_bucket') THEN
    ALTER TABLE public.large_trades ADD CONSTRAINT ck_large_trades_bucket CHECK (bucket IN ('30m','1h','4h','24h'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_alerts_type') THEN
    ALTER TABLE public.alerts ADD CONSTRAINT ck_alerts_type CHECK (alert_type IN ('price_cross','wallet_trade','large_trade','tvl_change'));
  END IF;
END$$;

-- ON DELETE CASCADE fixes
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='watchlist_wallet_id_fkey') THEN
    ALTER TABLE public.watchlist DROP CONSTRAINT watchlist_wallet_id_fkey;
  END IF;
  ALTER TABLE public.watchlist
    ADD CONSTRAINT watchlist_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallets(wallet_id) ON DELETE CASCADE;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='alerts_wallet_id_fkey') THEN
    ALTER TABLE public.alerts DROP CONSTRAINT alerts_wallet_id_fkey;
  END IF;
  ALTER TABLE public.alerts
    ADD CONSTRAINT alerts_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallets(wallet_id) ON DELETE CASCADE;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='alert_events_alert_id_fkey') THEN
    ALTER TABLE public.alert_events DROP CONSTRAINT alert_events_alert_id_fkey;
  END IF;
  ALTER TABLE public.alert_events
    ADD CONSTRAINT alert_events_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(alert_id) ON DELETE CASCADE;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='alert_events_wallet_id_fkey') THEN
    ALTER TABLE public.alert_events DROP CONSTRAINT alert_events_wallet_id_fkey;
  END IF;
  ALTER TABLE public.alert_events
    ADD CONSTRAINT alert_events_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallets(wallet_id) ON DELETE CASCADE;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='token_twitter_token_id_fkey') THEN
    ALTER TABLE public.token_twitter DROP CONSTRAINT token_twitter_token_id_fkey;
  END IF;
  ALTER TABLE public.token_twitter
    ADD CONSTRAINT token_twitter_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.tokens(token_id) ON DELETE CASCADE;
END$$;

-- Function + index for twitter normalization
CREATE OR REPLACE FUNCTION public.norm_twitter_handle(in_raw TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE STRICT AS $$
SELECT lower(
    regexp_replace(
        regexp_replace(
            regexp_replace(coalesce(in_raw, ''),
                '^(https?://)?(www\.)?(x|twitter)\.com/', '', 'i'
            ),
            '^@', '', 'i'
        ),
        '[/\?\#].*$', '', 'g'
    )
);
$$;
CREATE INDEX IF NOT EXISTS idx_tokens_twitter_handle ON public.tokens (public.norm_twitter_handle(twitter));

-- Indexes (idempotent)
CREATE INDEX IF NOT EXISTS idx_price_ticks_pool_ts ON public.price_ticks(pool_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_pool_time ON public.ohlcv_1m(pool_id, bucket_start DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_usd_pool_time ON public.ohlcv_1m_usd(pool_id, bucket_start DESC);
CREATE INDEX IF NOT EXISTS idx_tokens_created_at ON public.tokens(created_at);
CREATE INDEX IF NOT EXISTS idx_pools_created_at ON public.pools(created_at);
CREATE INDEX IF NOT EXISTS idx_pools_pair_contract ON public.pools(pair_contract);
CREATE INDEX IF NOT EXISTS idx_pools_base_token_id ON public.pools(base_token_id);
CREATE INDEX IF NOT EXISTS idx_pools_quote_token_id ON public.pools(quote_token_id);
CREATE INDEX IF NOT EXISTS idx_pools_base_quote ON public.pools(base_token_id, quote_token_id);
CREATE INDEX IF NOT EXISTS idx_pools_pair_type ON public.pools(pair_type);
CREATE INDEX IF NOT EXISTS idx_trades_time ON public.trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_signer ON public.trades(signer);
CREATE INDEX IF NOT EXISTS idx_trades_action_signer_time ON public.trades(action, signer, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_pool_time ON public.trades(pool_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_height ON public.trades(height);
CREATE INDEX IF NOT EXISTS idx_trades_tx ON public.trades(tx_hash);
CREATE INDEX IF NOT EXISTS idx_prices_token_time ON public.prices(token_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prices_pool_time ON public.prices(pool_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_holders_token_time ON public.holders(token_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_holders_address ON public.holders(address);
CREATE INDEX IF NOT EXISTS idx_pool_matrix_updated ON public.pool_matrix(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_matrix_bucket ON public.token_matrix(bucket, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_leaderboard_updated ON public.leaderboard_traders(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_large_trades_bucket_time ON public.large_trades(bucket, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_last_seen ON public.wallets(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_last_seen_at ON public.wallets(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_alert_time ON public.alert_events(alert_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_twitter_handle ON public.token_twitter(handle);
CREATE INDEX IF NOT EXISTS idx_token_twitter_last_refreshed ON public.token_twitter(last_refreshed DESC);
CREATE INDEX IF NOT EXISTS idx_ibc_tokens_base_denom ON public.ibc_tokens(base_denom);
CREATE INDEX IF NOT EXISTS idx_ibc_tokens_cmc_id ON public.ibc_tokens(cmc_id);
CREATE INDEX IF NOT EXISTS idx_ibc_tokens_coingecko_id ON public.ibc_tokens(coingecko_id);
CREATE INDEX IF NOT EXISTS idx_external_prices_updated ON public.external_prices(updated_at DESC);

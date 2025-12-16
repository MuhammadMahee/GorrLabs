import { EntitySchema } from 'typeorm';

export const Ohlcv1mEntity = new EntitySchema({
  name: 'ohlcv_1m',
  tableName: 'ohlcv_1m',
  columns: {
    pool_id: { type: 'bigint', primary: true },
    bucket_start: { type: 'timestamptz', primary: true },
    open: { type: 'numeric', precision: 38, scale: 18 },
    high: { type: 'numeric', precision: 38, scale: 18 },
    low: { type: 'numeric', precision: 38, scale: 18 },
    close: { type: 'numeric', precision: 38, scale: 18 },
    volume_zig: { type: 'numeric', precision: 38, scale: 8, default: 0 },
    trade_count: { type: 'int', default: 0 },
    liquidity_zig: { type: 'numeric', precision: 38, scale: 8, nullable: true },
  },
  indices: [
    { name: 'idx_ohlcv_pool_time', columns: ['pool_id', 'bucket_start'] },
  ],
});

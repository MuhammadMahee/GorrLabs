import { EntitySchema } from 'typeorm';

export const PriceTicksEntity = new EntitySchema({
  name: 'price_ticks',
  tableName: 'price_ticks',
  columns: {
    pool_id: { type: 'bigint', primary: true },
    token_id: { type: 'bigint' },
    price_in_zig: { type: 'numeric', precision: 38, scale: 18 },
    ts: { type: 'timestamptz', primary: true, default: () => 'now()' },
  },
  indices: [
    { name: 'idx_price_ticks_pool_ts', columns: ['pool_id', 'ts'] },
  ],
});

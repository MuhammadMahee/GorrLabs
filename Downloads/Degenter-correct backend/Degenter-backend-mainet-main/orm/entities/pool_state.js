import { EntitySchema } from 'typeorm';

export const PoolStateEntity = new EntitySchema({
  name: 'pool_state',
  tableName: 'pool_state',
  columns: {
    pool_id: { type: 'bigint', primary: true },
    reserve_base_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    reserve_quote_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    updated_at: { type: 'timestamptz', default: () => 'now()' },
    tvl_zig: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    tvl_usd: { type: 'numeric', precision: 38, scale: 8, nullable: true },
  },
});

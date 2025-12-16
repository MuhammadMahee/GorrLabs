import { EntitySchema } from 'typeorm';

export const PoolMatrixEntity = new EntitySchema({
  name: 'pool_matrix',
  tableName: 'pool_matrix',
  columns: {
    pool_id: { type: 'bigint', primary: true },
    bucket: { type: 'text', primary: true },
    vol_buy_quote: { type: 'numeric', precision: 38, scale: 8, default: 0 },
    vol_sell_quote: { type: 'numeric', precision: 38, scale: 8, default: 0 },
    vol_buy_zig: { type: 'numeric', precision: 38, scale: 8, default: 0 },
    vol_sell_zig: { type: 'numeric', precision: 38, scale: 8, default: 0 },
    tx_buy: { type: 'int', default: 0 },
    tx_sell: { type: 'int', default: 0 },
    unique_traders: { type: 'int', default: 0 },
    tvl_zig: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    reserve_base_disp: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    reserve_quote_disp: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    updated_at: { type: 'timestamptz' },
  },
  indices: [
    { name: 'idx_pool_matrix_updated', columns: ['updated_at'] },
  ],
});

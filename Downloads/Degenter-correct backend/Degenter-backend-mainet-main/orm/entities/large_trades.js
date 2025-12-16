import { EntitySchema } from 'typeorm';

export const LargeTradesEntity = new EntitySchema({
  name: 'large_trades',
  tableName: 'large_trades',
  columns: {
    id: { type: 'bigint', primary: true, generated: true },
    bucket: { type: 'text' },
    pool_id: { type: 'bigint' },
    tx_hash: { type: 'text' },
    signer: { type: 'text', nullable: true },
    value_zig: { type: 'numeric', precision: 38, scale: 8 },
    direction: {
      type: 'enum',
      enumName: 'trade_direction',
      enum: ['buy', 'sell', 'provide', 'withdraw']
    },
    created_at: { type: 'timestamptz' },
    inserted_at: { type: 'timestamptz', default: () => 'now()' },
  },
  uniques: [
    { name: 'ux_large_trades_tx_pool_dir', columns: ['tx_hash', 'pool_id', 'direction'] },
  ],
  indices: [
    { name: 'idx_large_trades_bucket_time', columns: ['bucket', 'created_at'] },
  ],
});

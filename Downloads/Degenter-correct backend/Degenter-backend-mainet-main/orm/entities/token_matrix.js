import { EntitySchema } from 'typeorm';

export const TokenMatrixEntity = new EntitySchema({
  name: 'token_matrix',
  tableName: 'token_matrix',
  columns: {
    token_id: { type: 'bigint', primary: true },
    bucket: { type: 'text', primary: true },
    price_in_zig: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    mcap_zig: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    fdv_zig: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    holders: { type: 'bigint', nullable: true },
    updated_at: { type: 'timestamptz', default: () => 'now()' },
  },
  indices: [
    { name: 'idx_token_matrix_bucket', columns: ['bucket', 'updated_at'] },
  ],
});

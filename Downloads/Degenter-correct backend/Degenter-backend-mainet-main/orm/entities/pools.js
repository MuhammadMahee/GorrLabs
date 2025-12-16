import { EntitySchema } from 'typeorm';

export const PoolsEntity = new EntitySchema({
  name: 'pools',
  tableName: 'pools',
  columns: {
    pool_id: { type: 'bigint', primary: true, generated: true },
    pair_contract: { type: 'text', unique: true },
    base_token_id: { type: 'bigint' },
    quote_token_id: { type: 'bigint' },
    lp_token_denom: { type: 'text', nullable: true },
    pair_type: {
      type: 'enum',
      enumName: 'pair_type',
      enum: ['xyk', 'concentrated', 'custom-concentrated']
    },
    is_uzig_quote: { type: 'boolean', default: false },
    factory_contract: { type: 'text', nullable: true },
    router_contract: { type: 'text', nullable: true },
    created_at: { type: 'timestamptz', nullable: true },
    created_height: { type: 'bigint', nullable: true },
    created_tx_hash: { type: 'text', nullable: true },
    signer: { type: 'text', nullable: true },
  },
  indices: [
    { name: 'idx_pools_created_at', columns: ['created_at'] },
    { name: 'idx_pools_pair_contract', columns: ['pair_contract'] },
    { name: 'idx_pools_base_token_id', columns: ['base_token_id'] },
    { name: 'idx_pools_quote_token_id', columns: ['quote_token_id'] },
    { name: 'idx_pools_base_quote', columns: ['base_token_id', 'quote_token_id'] },
    { name: 'idx_pools_pair_type', columns: ['pair_type'] },
  ],
});

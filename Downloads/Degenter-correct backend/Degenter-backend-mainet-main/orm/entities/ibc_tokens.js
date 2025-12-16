import { EntitySchema } from 'typeorm';

export const IbcTokensEntity = new EntitySchema({
  name: 'ibc_tokens',
  tableName: 'ibc_tokens',
  columns: {
    token_id: { type: 'bigint', primary: true },
    base_denom: { type: 'text', nullable: true },
    source_chain: { type: 'text', nullable: true },
    source_channel: { type: 'text', nullable: true },
    coingecko_id: { type: 'text', nullable: true },
    cmc_id: { type: 'text', nullable: true },
    updated_at: { type: 'timestamptz', default: () => 'now()' },
  },
  indices: [
    { name: 'idx_ibc_tokens_base_denom', columns: ['base_denom'] },
    { name: 'idx_ibc_tokens_cmc_id', columns: ['cmc_id'] },
    { name: 'idx_ibc_tokens_coingecko_id', columns: ['coingecko_id'] },
  ],
});

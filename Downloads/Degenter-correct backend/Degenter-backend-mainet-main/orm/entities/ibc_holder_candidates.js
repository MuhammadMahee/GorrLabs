import { EntitySchema } from 'typeorm';

export const IbcHolderCandidatesEntity = new EntitySchema({
  name: 'ibc_holder_candidates',
  tableName: 'ibc_holder_candidates',
  columns: {
    token_id: { type: 'bigint', primary: true },
    address: { type: 'text', primary: true },
    last_seen_h: { type: 'bigint' },
    last_seen_at: { type: 'timestamptz', default: () => 'now()' },
  },
});

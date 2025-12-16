import { EntitySchema } from 'typeorm';

export const TokenHoldersStatsEntity = new EntitySchema({
  name: 'token_holders_stats',
  tableName: 'token_holders_stats',
  columns: {
    token_id: { type: 'bigint', primary: true },
    holders_count: { type: 'bigint' },
    updated_at: { type: 'timestamptz' },
  },
});

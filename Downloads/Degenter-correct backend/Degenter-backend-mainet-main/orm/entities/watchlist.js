import { EntitySchema } from 'typeorm';

export const WatchlistEntity = new EntitySchema({
  name: 'watchlist',
  tableName: 'watchlist',
  columns: {
    id: { type: 'bigint', primary: true, generated: true },
    wallet_id: { type: 'bigint' },
    token_id: { type: 'bigint', nullable: true },
    pool_id: { type: 'bigint', nullable: true },
    note: { type: 'text', nullable: true },
    created_at: { type: 'timestamptz', default: () => 'now()' },
  },
  uniques: [
    { columns: ['wallet_id', 'token_id'] },
    { columns: ['wallet_id', 'pool_id'] },
  ],
});

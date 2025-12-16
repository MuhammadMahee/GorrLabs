import { EntitySchema } from 'typeorm';

export const WalletsEntity = new EntitySchema({
  name: 'wallets',
  tableName: 'wallets',
  columns: {
    wallet_id: { type: 'bigint', primary: true, generated: true },
    address: { type: 'text', unique: true },
    display_name: { type: 'text', nullable: true },
    created_at: { type: 'timestamptz', default: () => 'now()' },
    last_seen: { type: 'timestamptz', nullable: true },
    last_seen_at: { type: 'timestamptz', nullable: true },
  },
  indices: [
    { name: 'idx_wallets_last_seen', columns: ['last_seen'] },
    { name: 'idx_wallets_last_seen_at', columns: ['last_seen_at'] },
  ],
});

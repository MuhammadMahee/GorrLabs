import { EntitySchema } from 'typeorm';

export const HoldersEntity = new EntitySchema({
  name: 'holders',
  tableName: 'holders',
  columns: {
    token_id: { type: 'bigint', primary: true },
    address: { type: 'text', primary: true },
    balance_base: { type: 'numeric', precision: 78, scale: 0 },
    updated_at: { type: 'timestamptz' },
    last_seen_height: { type: 'bigint', nullable: true },
  },
  indices: [
    { name: 'idx_holders_token_time', columns: ['token_id', 'updated_at'] },
    { name: 'idx_holders_address', columns: ['address'] },
  ],
});

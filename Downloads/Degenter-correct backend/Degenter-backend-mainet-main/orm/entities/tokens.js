import { EntitySchema } from 'typeorm';

export const TokensEntity = new EntitySchema({
  name: 'tokens',
  tableName: 'tokens',
  columns: {
    token_id: { type: 'bigint', primary: true, generated: true },
    denom: { type: 'text', unique: true },
    type: {
      type: 'enum',
      enumName: 'token_type',
      enum: ['native', 'factory', 'ibc', 'cw20'],
      default: 'factory'
    },
    name: { type: 'text', nullable: true },
    symbol: { type: 'text', nullable: true },
    display: { type: 'text', nullable: true },
    exponent: { type: 'smallint', default: 6 },
    image_uri: { type: 'text', nullable: true },
    website: { type: 'text', nullable: true },
    twitter: { type: 'text', nullable: true },
    telegram: { type: 'text', nullable: true },
    max_supply_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    total_supply_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    description: { type: 'text', nullable: true },
    created_at: { type: 'timestamptz', default: () => 'now()' },
  },
  indices: [
    { name: 'idx_tokens_created_at', columns: ['created_at'] },
  ],
});

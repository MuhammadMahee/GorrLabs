import { EntitySchema } from 'typeorm';

export const ExternalPricesEntity = new EntitySchema({
  name: 'external_prices',
  tableName: 'external_prices',
  columns: {
    token_id: { type: 'bigint', primary: true },
    source: { type: 'text', primary: true },
    price_usd: { type: 'numeric', precision: 38, scale: 18 },
    updated_at: { type: 'timestamptz', default: () => 'now()' },
  },
  indices: [
    { name: 'idx_external_prices_updated', columns: ['updated_at'] },
  ],
});

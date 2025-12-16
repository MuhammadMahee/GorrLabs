import { EntitySchema } from 'typeorm';

export const ExchangeRatesEntity = new EntitySchema({
  name: 'exchange_rates',
  tableName: 'exchange_rates',
  columns: {
    ts: { type: 'timestamptz', primary: true },
    zig_usd: { type: 'numeric', precision: 38, scale: 8 },
  },
});

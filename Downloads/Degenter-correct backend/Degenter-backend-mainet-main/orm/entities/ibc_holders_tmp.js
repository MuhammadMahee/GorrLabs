import { EntitySchema } from 'typeorm';

export const IbcHoldersTmpEntity = new EntitySchema({
  name: 'ibc_holders_tmp',
  tableName: 'ibc_holders_tmp',
  columns: {
    token_id: { type: 'bigint', primary: true },
    address: { type: 'text', primary: true },
    balance_base: { type: 'numeric', precision: 78, scale: 0 },
  },
});

import { EntitySchema } from 'typeorm';

export const IndexStateEntity = new EntitySchema({
  name: 'index_state',
  tableName: 'index_state',
  columns: {
    id: { type: 'text', primary: true },
    last_height: { type: 'bigint' },
    updated_at: { type: 'timestamptz', default: () => 'now()' },
  },
});

import { EntitySchema } from 'typeorm';

export const AlertsEntity = new EntitySchema({
  name: 'alerts',
  tableName: 'alerts',
  columns: {
    alert_id: { type: 'bigint', primary: true, generated: true },
    wallet_id: { type: 'bigint' },
    alert_type: { type: 'text' },
    params: { type: 'jsonb' },
    is_active: { type: 'boolean', default: true },
    throttle_sec: { type: 'int', default: 300 },
    last_triggered: { type: 'timestamptz', nullable: true },
    created_at: { type: 'timestamptz', default: () => 'now()' },
  },
});

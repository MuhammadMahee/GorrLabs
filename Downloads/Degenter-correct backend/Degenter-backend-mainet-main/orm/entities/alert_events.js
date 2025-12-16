import { EntitySchema } from 'typeorm';

export const AlertEventsEntity = new EntitySchema({
  name: 'alert_events',
  tableName: 'alert_events',
  columns: {
    id: { type: 'bigint', primary: true, generated: true },
    alert_id: { type: 'bigint' },
    wallet_id: { type: 'bigint' },
    kind: { type: 'text' },
    payload: { type: 'jsonb' },
    triggered_at: { type: 'timestamptz', default: () => 'now()' },
  },
  indices: [
    { name: 'idx_alert_events_alert_time', columns: ['alert_id', 'triggered_at'] },
  ],
});

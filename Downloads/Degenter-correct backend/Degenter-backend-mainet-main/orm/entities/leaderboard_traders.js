import { EntitySchema } from 'typeorm';

export const LeaderboardTradersEntity = new EntitySchema({
  name: 'leaderboard_traders',
  tableName: 'leaderboard_traders',
  columns: {
    bucket: { type: 'text', primary: true },
    address: { type: 'text', primary: true },
    trades_count: { type: 'int' },
    volume_zig: { type: 'numeric', precision: 38, scale: 8 },
    gross_pnl_zig: { type: 'numeric', precision: 38, scale: 8 },
    updated_at: { type: 'timestamptz', default: () => 'now()' },
  },
  indices: [
    { name: 'idx_leaderboard_updated', columns: ['updated_at'] },
  ],
});

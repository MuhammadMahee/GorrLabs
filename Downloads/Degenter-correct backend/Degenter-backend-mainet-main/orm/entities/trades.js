import { EntitySchema } from 'typeorm';

export const TradesEntity = new EntitySchema({
  name: 'trades',
  tableName: 'trades',
  columns: {
    trade_id: { type: 'bigint', primary: true, generated: true },
    pool_id: { type: 'bigint' },
    pair_contract: { type: 'text' },
    action: {
      type: 'enum',
      enumName: 'trade_action',
      enum: ['swap', 'provide', 'withdraw']
    },
    direction: {
      type: 'enum',
      enumName: 'trade_direction',
      enum: ['buy', 'sell', 'provide', 'withdraw']
    },
    offer_asset_denom: { type: 'text', nullable: true },
    offer_amount_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    ask_asset_denom: { type: 'text', nullable: true },
    ask_amount_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    return_amount_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    is_router: { type: 'boolean', default: false },
    reserve_asset1_denom: { type: 'text', nullable: true },
    reserve_asset1_amount_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    reserve_asset2_denom: { type: 'text', nullable: true },
    reserve_asset2_amount_base: { type: 'numeric', precision: 78, scale: 0, nullable: true },
    height: { type: 'bigint', nullable: true },
    tx_hash: { type: 'text', nullable: true },
    signer: { type: 'text', nullable: true },
    msg_index: { type: 'int', nullable: true },
    price_in_quote: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    price_in_zig: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    price_in_usd: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    value_in_quote: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    value_in_zig: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    value_in_usd: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    quote_price_in_zig: { type: 'numeric', precision: 38, scale: 18, nullable: true },
    zig_usd_at_trade: { type: 'numeric', precision: 38, scale: 8, nullable: true },
    created_at: { type: 'timestamptz', primary: true },
  },
  uniques: [
    { name: 'uq_trades_tx_pool_msg_time', columns: ['tx_hash', 'pool_id', 'msg_index', 'created_at'] },
  ],
  indices: [
    { name: 'idx_trades_time', columns: ['created_at'] },
    { name: 'idx_trades_signer', columns: ['signer'] },
    { name: 'idx_trades_action_signer_time', columns: ['action', 'signer', 'created_at'] },
    { name: 'idx_trades_pool_time', columns: ['pool_id', 'created_at'] },
    { name: 'idx_trades_height', columns: ['height'] },
    { name: 'idx_trades_tx', columns: ['tx_hash'] },
  ],
});

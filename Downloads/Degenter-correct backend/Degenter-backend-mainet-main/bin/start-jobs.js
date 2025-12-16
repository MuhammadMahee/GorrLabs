// bin/start-jobs.js
import 'dotenv/config';
import { init } from '../lib/db.js';
import { info } from '../lib/log.js';

import { startMetaRefresher } from '../jobs/meta-refresher.js';
import { startHoldersRefresher } from '../jobs/holders-refresher.js';
import { startPriceFromReserves } from '../jobs/price-from-reserves.js';
import { startLeaderboards } from '../jobs/leaderboards.js';
import { startPartitionsMaintainer } from '../jobs/partitions.js';
import { startTokenSecurityScanner } from '../jobs/token-security.js';
import { startFx } from '../jobs/fx-zig.js';
import matrix from '../jobs/matrix-rollups.js';
import { startIbcMetaRefresher } from '../jobs/ibc-meta-refresher.js';
import { startIbcMarketRefresher } from '../jobs/ibc-market-refresher.js';
import { startFasttrackListener } from '../jobs/fasttrack-listener.js';
import { startIbcHoldersFullscan } from '../jobs/ibc-holders-fullscan.js';

// import { runFxBackfill } from '../jobs/fx-zig-backfill.js';

async function main() {
  console.log('start-jobs from:', import.meta.url);
  await init();
  info('jobs: starting…');

  // // optional backfill: controlled via env
  // if (process.env.FX_BACKFILL_ENABLED === '1') {
  //   info('jobs: running FX backfill…');
  //   try {
  //     await runFxBackfill();
  //     info('jobs: FX backfill done');
  //   } catch (e) {
  //     console.error('FX backfill failed:', e);
  //     // decide if you want to exit or continue
  //     // process.exit(1);
  //   }
  // }

  // periodic jobs
  matrix.start();
  startMetaRefresher();
  startHoldersRefresher();
  startPriceFromReserves();
  startLeaderboards();
  startPartitionsMaintainer();
  startTokenSecurityScanner();
  startIbcMarketRefresher();
  startIbcHoldersFullscan();   
  // live FX
  startFx();

  startIbcMetaRefresher();

  // 🔔 fast-track listener
  startFasttrackListener();

  // keep process alive
  setInterval(()=>{}, 1<<30);
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});

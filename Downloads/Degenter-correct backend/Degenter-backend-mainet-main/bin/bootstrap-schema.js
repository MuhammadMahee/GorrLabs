// bin/bootstrap-schema.js
// One-off helper to let TypeORM auto-create tables before applying the SQL patch.
// Usage: node bin/bootstrap-schema.js
import 'dotenv/config';
import { DataSource } from 'typeorm';
import { Entities } from '../orm/entities/index.js';

async function main() {
  const ds = new DataSource({
    type: 'postgres',
    url: process.env.DATABASE_URL,
    synchronize: true,
    logging: true,
    entities: Entities,
  });

  console.log('[bootstrap] initializing DataSource with synchronize=true…');
  await ds.initialize();
  console.log('[bootstrap] schema synchronized (plain tables created)');
  await ds.destroy();
  console.log('[bootstrap] done');
}

main().catch((e) => {
  console.error('[bootstrap] failed:', e);
  process.exit(1);
});

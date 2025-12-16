// lib/db.js
import 'dotenv/config';
import { DataSource } from 'typeorm';
import { Entities } from '../orm/entities/index.js';
import { info, warn, err } from './log.js';

const DEFAULTS = {
  max: 20,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 10_000,
  statement_timeout: '120s',
  idle_in_transaction_session_timeout: '60s'
};

const dataSource = new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  synchronize: true,
  logging: false,
  entities: Entities,
  extra: {
    max: DEFAULTS.max,
    idleTimeoutMillis: DEFAULTS.idleTimeoutMillis,
    connectionTimeoutMillis: DEFAULTS.connectionTimeoutMillis,
    statement_timeout: DEFAULTS.statement_timeout,
    idle_in_transaction_session_timeout: DEFAULTS.idle_in_transaction_session_timeout,
    keepAlive: true,
    keepAliveInitialDelayMillis: 30000
  }
});

// keep native query for TypeORM use, and provide pg-like shape ({ rows }) for existing callers
const rawQuery = dataSource.query.bind(dataSource);
dataSource.queryRaw = rawQuery;
dataSource.query = async (sql, params) => {
  const rows = await rawQuery(sql, params);
  return { rows };
};

export const DB = dataSource;

// Provide a pg-like client for legacy callers (with .query and .release)
DB.connect = async () => {
  const runner = DB.createQueryRunner();
  await runner.connect();
  const client = runner.databaseConnection;
  client.release = async () => {
    try { await runner.release(); } catch {}
  };
  return client;
};

export async function init() {
  try {
    if (!DB.isInitialized) {
      await DB.initialize();
    }
    const r = await DB.query('SELECT NOW() as now');
    info('db connected @', r.rows?.[0]?.now);
  } catch (e) {
    err('db connect failed:', e.message);
    throw e;
  }
}

export async function tx(fn) {
  const runner = DB.createQueryRunner();
  await runner.connect();
  await runner.startTransaction();
  try {
    const res = await fn(runner.manager);
    await runner.commitTransaction();
    return res;
  } catch (e) {
    await runner.rollbackTransaction();
    throw e;
  } finally {
    await runner.release();
  }
}

/** simple helper that retries transient failures a few times */
export async function queryRetry(sql, args = [], attempts = 3) {
  for (let i = 0; i < attempts; i++) {
    try {
      return await DB.query(sql, args);
    } catch (e) {
      const last = i === attempts - 1;
      if (last) throw e;
      warn('db retry', i + 1, e.message);
      await new Promise(r => setTimeout(r, 150 * (i + 1)));
    }
  }
}

/** graceful shutdown */
export async function close() {
  try {
    if (DB.isInitialized) {
      await DB.destroy();
      info('db connection closed');
    }
  } catch (e) {
    warn('db close error:', e.message);
  }
}

export default { DB, init, tx, queryRetry, close };

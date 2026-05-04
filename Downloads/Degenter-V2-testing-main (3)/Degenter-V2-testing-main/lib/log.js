// lib/log.js
import process from 'node:process';

const VERBOSE = (process.env.VERBOSE || '1') !== '0';
const PREFIX = process.env.LOG_PREFIX ? `${process.env.LOG_PREFIX} ` : '';

function ts() {
  return new Date().toISOString();
}

export function debug(...a) {
  if (VERBOSE) console.log(PREFIX + '[debug]', ts(), ...a);
}
export function info(...a) {
  console.log(PREFIX + '[info ]', ts(), ...a);
}
export function warn(...a) {
  console.warn(PREFIX + '[warn ]', ts(), ...a);
}
export function err(...a) {
  console.error(PREFIX + '[error]', ts(), ...a);
}

export default { debug, info, warn, err };

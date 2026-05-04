// jobs/run-job.js
// Generic runner: import a module and invoke an exported start function.
import { pathToFileURL } from 'url';

const [,, modPath, fnName] = process.argv;
if (!modPath || !fnName) {
  console.error('Usage: node jobs/run-job.js <module> <exportedFunction>');
  process.exit(1);
}

async function main() {
  const mod = await import(pathToFileURL(modPath));
  const fn = mod[fnName];
  if (typeof fn !== 'function') {
    throw new Error(`Export ${fnName} not found in ${modPath}`);
  }
  await fn(); // expected to keep event loop alive
  // In case it resolves immediately, keep process alive
  setInterval(() => {}, 1 << 30);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

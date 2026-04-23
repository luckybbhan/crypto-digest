import { spawn } from 'child_process';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_FILE = resolve(__dirname, 'DIGEST_SKILL.md');
const CLAUDE_PATH = process.env.CLAUDE_PATH || '/Users/ahao/.local/bin/claude';

const isProd = process.argv.includes('--prod');
const skill = readFileSync(SKILL_FILE, 'utf-8');

const prompt =
  `Follow the instructions in the skill doc below exactly.\n\n` +
  `Arguments:\n` +
  `- target: ${isProd ? 'PROD (use TELEGRAM_GROUP_ID)' : 'TEST (use TEST_GROUP_ID)'}\n` +
  `- use_threads: ${isProd ? 'true' : 'false'}\n\n` +
  `---\n\n` +
  skill;

console.log(`[agent] Starting digest — target: ${isProd ? 'PROD' : 'TEST'}`);
console.log(`[agent] ${new Date().toISOString()}`);

const proc = spawn(CLAUDE_PATH, [
  '-p', prompt,
  '--allowedTools', 'WebFetch,Bash,Read,Write',
], {
  cwd: __dirname,
  stdio: ['ignore', 'pipe', 'pipe'],
});

proc.stdout.on('data', (d) => process.stdout.write(`[claude] ${d}`));
proc.stderr.on('data', (d) => process.stderr.write(`[claude] ${d}`));

proc.on('close', (code) => {
  console.log(`[agent] Claude exited with code ${code}`);
  console.log(`[agent] Done — ${new Date().toISOString()}`);
  process.exit(code);
});

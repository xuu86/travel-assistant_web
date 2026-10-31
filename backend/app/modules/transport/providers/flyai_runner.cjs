'use strict';

// This guard wraps the published CLI; the application does not implement its MCP protocol.
const path = require('node:path');
const originalFetch = globalThis.fetch;
const audit = { fetch_count: 0, authorization_matches: false };
process.on('exit', () => {
  process.stderr.write('\nFLYAI_APP_AUDIT=' + JSON.stringify(audit) + '\n');
});

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  input += chunk;
  if (Buffer.byteLength(input) > 4096) process.exit(1);
});
process.stdin.on('end', () => {
  try {
    const query = JSON.parse(input);
    const key = (process.env.FLYAI_API_KEY || '').trim();
    if (!key || !query.origin || !query.destination || !/^\d{4}-\d{2}-\d{2}$/.test(query.date)) {
      throw new Error('Invalid CLI input');
    }
    const timeout = Number(process.env.FLYAI_APP_TIMEOUT_MS);
    const limit = Number(process.env.FLYAI_APP_MAX_RESPONSE_BYTES);
    globalThis.fetch = async (input, options = {}) => {
      const target = new URL(typeof input === 'string' ? input : input.url);
      if (target.origin !== 'https://flyai.open.fliggy.com' || target.pathname !== '/mcp' ||
          target.search || target.hash || target.username || target.password ||
          (options.method || '').toUpperCase() !== 'POST' || ++audit.fetch_count > 1) {
        throw new Error('CLI network boundary rejected');
      }
      const headers = new Headers(options.headers);
      audit.authorization_matches = headers.get('authorization') ===
        (key.startsWith('Bearer ') ? key : 'Bearer ' + key);
      const body = JSON.parse(options.body);
      if (!audit.authorization_matches || body.method !== 'tools/call' ||
          body.params?.name !== 'search_domestic_train' ||
          body.params?.arguments?.origin !== query.origin ||
          body.params?.arguments?.destination !== query.destination ||
          body.params?.arguments?.depDate !== query.date) {
        throw new Error('CLI request boundary rejected');
      }
      const response = await originalFetch(input, {
        ...options, redirect: 'error', signal: AbortSignal.timeout(timeout),
      });
      audit.http_status = response.status;
      const chunks = [];
      let size = 0;
      if (response.body) {
        for await (const chunk of response.body) {
          size += chunk.byteLength;
          if (size > limit) throw new Error('CLI response exceeded limit');
          chunks.push(Buffer.from(chunk));
        }
      }
      audit.response_bytes = size;
      return new Response(Buffer.concat(chunks), {
        status: response.status, statusText: response.statusText, headers: response.headers,
      });
    };
    const bundle = path.resolve(__dirname, '../../../../../.tools/flyai/dist/flyai-bundle.cjs');
    process.argv = [process.execPath, bundle, 'search-train', '--origin', query.origin,
      '--destination', query.destination, '--dep-date', query.date];
    require(bundle);
  } catch {
    process.exitCode = 1;
  }
});

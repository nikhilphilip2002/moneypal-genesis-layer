const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const compiled = ts.transpileModule(readFileSync(`${__dirname}/api.ts`, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function clientFor(body) {
  const context = {
    exports: {}, process, TextDecoder,
    fetch: async () => new Response(body),
  };
  vm.runInNewContext(compiled, context);
  return context.exports.workbench;
}

const frame = (event, data) => new TextEncoder().encode(
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`,
);

test('yields fragmented answer text before the stream closes, then the final answer', async () => {
  let controller;
  let cancelled = false;
  const body = new ReadableStream({
    start(value) { controller = value; },
    cancel() { cancelled = true; },
  });
  const events = clientFor(body).ask('question', null);
  const pending = events.next();
  controller.enqueue(frame('trace_delta', {
    id: 'model-1', reasoning_delta: 'Checking available data…',
  }));
  const reasoning = (await pending).value;
  assert.equal(reasoning.type, 'trace_delta');
  assert.equal(reasoning.reasoning_delta, 'Checking available data…');
  const toolPending = events.next();
  controller.enqueue(frame('trace_delta', {
    id: 'model-1', tool_call: { index: 0, id: 'call-1', name: 'query_metrics' },
  }));
  const tool = (await toolPending).value;
  assert.equal(tool.type, 'trace_delta');
  assert.equal(tool.tool_call.name, 'query_metrics');
  const answerPending = events.next();
  const bytes = frame('answer_delta', { text: '₹ 42' });
  for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
  const delta = (await answerPending).value;
  assert.equal(delta.type, 'answer_delta');
  assert.equal(delta.text, '₹ 42');
  controller.enqueue(frame('answer_reset', {}));
  controller.enqueue(frame('answer', { text: 'Verified answer' }));
  controller.enqueue(frame('done', { total_ms: 12 }));
  assert.equal((await events.next()).value.type, 'answer_reset');
  assert.equal((await events.next()).value.answer.text, 'Verified answer');
  assert.equal((await events.next()).value.type, 'done');
  assert.equal((await events.next()).done, true);
  assert.equal(cancelled, true);
  assert.equal(body.locked, false);
});

test('rejects premature EOF and releases the response reader', async () => {
  const body = new ReadableStream({ start(controller) { controller.close(); } });
  await assert.rejects(clientFor(body).ask('q', null).next(), /interrupted/);
  assert.equal(body.locked, false);
});

test('cancels the response when the consumer stops early', async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { controller.enqueue(frame('answer_delta', { text: 'first' })); },
    cancel() { cancelled = true; },
  });
  for await (const event of clientFor(body).ask('q', null)) {
    assert.equal(event.type, 'answer_delta');
    break;
  }
  assert.equal(cancelled, true);
  assert.equal(body.locked, false);
});

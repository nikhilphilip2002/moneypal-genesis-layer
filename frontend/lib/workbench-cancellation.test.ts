import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { WorkbenchTurnData } from '../components/workbench/WorkbenchTurn';
import { finishInterruptedTurn } from './workbench-cancellation.ts';

function activeTurn(): WorkbenchTurnData {
  return {
    id: 'turn-1', question: 'Show PAR 30', stage: 'routing', pending: ['db'],
    cards: [], done: false,
    executionTrace: [
      { id: 'model-1', kind: 'model', status: 'complete', label: 'Model', elapsed_ms: 1 },
      { id: 'tool-1', kind: 'tool', status: 'running', label: 'Query', detail: 'Calling tool', elapsed_ms: 2 },
    ],
    queryRegistry: [
      {
        query_id: 'q1', attempt_id: 'q1:a1', tool_call_id: 'call-1', tool_name: 'query',
        status: 'success', purpose: 'answer', has_data: true, visual_available: true,
        duration_ms: 1,
      },
      {
        query_id: 'q2', attempt_id: 'q2:a1', tool_call_id: 'call-2', tool_name: 'query',
        status: 'running', purpose: 'answer', has_data: false, visual_available: false,
        duration_ms: 0,
      },
      {
        query_id: 'q3', attempt_id: 'q3:a1', tool_call_id: 'call-3', tool_name: 'query',
        status: 'pending', purpose: 'answer', has_data: false, visual_available: false,
        duration_ms: 0,
      },
    ],
  };
}

test('stopping a response closes active work and preserves completed results', () => {
  const turn = activeTurn();
  const finished = finishInterruptedTurn(turn, true, 'Response stopped.');

  assert.equal(finished.done, true);
  assert.equal(finished.stage, undefined);
  assert.deepEqual(finished.pending, []);
  assert.equal(finished.error?.message, 'Response stopped.');
  assert.equal(finished.executionTrace?.[0].status, 'complete');
  assert.equal(finished.executionTrace?.[1].status, 'error');
  assert.equal(finished.executionTrace?.[1].detail, 'Stopped by user');
  assert.deepEqual(finished.queryRegistry?.map((query) => query.status), [
    'success', 'cancelled', 'cancelled',
  ]);
  assert.equal(finished.queryRegistry?.[1].error_code, 'CANCELLED');
  assert.equal(turn.executionTrace?.[1].status, 'running');
});

test('stream failure closes active work as an error', () => {
  const finished = finishInterruptedTurn(activeTurn(), false, 'Connection lost.');

  assert.equal(finished.executionTrace?.[1].detail, 'Stream interrupted');
  assert.equal(finished.queryRegistry?.[1].status, 'error');
  assert.equal(finished.queryRegistry?.[1].error_code, 'STREAM_INTERRUPTED');
  assert.equal(finished.error?.message, 'Connection lost.');
});

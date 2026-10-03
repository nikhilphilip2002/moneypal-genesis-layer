import assert from 'node:assert/strict';
import { test } from 'node:test';
import { emptyMessageQueue, nextQueuedMessage, updateMessageQueue } from './workbench-queue.ts';

function queuedMessages() {
  return ['B', 'C', 'D'].reduce((queue, text) => updateMessageQueue(queue, {
    type: 'enqueue', message: { id: text, text },
  }), emptyMessageQueue);
}

test('messages leave the queue in submission order', () => {
  let queue = queuedMessages();
  for (const id of ['B', 'C', 'D']) {
    assert.equal(nextQueuedMessage(queue)?.id, id);
    queue = updateMessageQueue(queue, { type: 'remove', id });
  }
  assert.equal(nextQueuedMessage(queue), undefined);
});

test('editing holds that entry and later messages while earlier messages proceed', () => {
  let queue = updateMessageQueue(queuedMessages(), { type: 'edit', id: 'C' });
  assert.equal(nextQueuedMessage(queue)?.id, 'B');
  queue = updateMessageQueue(queue, { type: 'remove', id: 'B' });
  assert.equal(nextQueuedMessage(queue), undefined);
  queue = updateMessageQueue(queue, { type: 'enqueue', message: { id: 'E', text: 'E' } });
  assert.equal(nextQueuedMessage(queue), undefined);
  queue = updateMessageQueue(queue, { type: 'save', id: 'C', text: ' Revised C ' });
  assert.equal(nextQueuedMessage(queue)?.text, 'Revised C');
  assert.deepEqual(queue.messages.map((message) => message.id), ['C', 'D', 'E']);
});

test('cancel restores the original text and empty edits remain blocked', () => {
  const queue = updateMessageQueue(queuedMessages(), { type: 'edit', id: 'B' });
  assert.equal(updateMessageQueue(queue, { type: 'save', id: 'B', text: '  ' }), queue);
  assert.equal(nextQueuedMessage(queue), undefined);
  const cancelled = updateMessageQueue(queue, { type: 'cancelEdit' });
  assert.equal(nextQueuedMessage(cancelled)?.text, 'B');
});

test('removing the edited entry releases the next message and clear resets editing', () => {
  const queue = updateMessageQueue(queuedMessages(), { type: 'edit', id: 'B' });
  const removed = updateMessageQueue(queue, { type: 'remove', id: 'B' });
  assert.equal(removed.editingId, null);
  assert.equal(nextQueuedMessage(removed)?.id, 'C');
  const cleared = updateMessageQueue(queue, { type: 'clear' });
  assert.deepEqual(cleared, emptyMessageQueue);
  assert.equal(nextQueuedMessage(cleared), undefined);
});

test('an edit cannot move its hold past the original entry', () => {
  const queue = updateMessageQueue(queuedMessages(), { type: 'edit', id: 'B' });
  assert.equal(updateMessageQueue(queue, { type: 'edit', id: 'D' }), queue);
  assert.equal(updateMessageQueue(queue, { type: 'save', id: 'D', text: 'Changed' }), queue);
  assert.equal(updateMessageQueue(queuedMessages(), { type: 'edit', id: 'missing' }).editingId, null);
});

export type QueuedMessage = { id: string; text: string };

export type MessageQueue = {
  messages: QueuedMessage[];
  editingId: string | null;
};

export type MessageQueueAction =
  | { type: 'enqueue'; message: QueuedMessage }
  | { type: 'edit'; id: string }
  | { type: 'save'; id: string; text: string }
  | { type: 'cancelEdit' }
  | { type: 'remove'; id: string }
  | { type: 'clear' };

export const emptyMessageQueue: MessageQueue = { messages: [], editingId: null };

export function nextQueuedMessage(queue: MessageQueue): QueuedMessage | undefined {
  const first = queue.messages[0];
  return first?.id === queue.editingId ? undefined : first;
}

export function updateMessageQueue(queue: MessageQueue, action: MessageQueueAction): MessageQueue {
  switch (action.type) {
    case 'enqueue':
      return { ...queue, messages: [...queue.messages, action.message] };
    case 'edit':
      if (queue.editingId || !queue.messages.some((message) => message.id === action.id)) return queue;
      return { ...queue, editingId: action.id };
    case 'save':
      if (queue.editingId !== action.id || !action.text.trim()) return queue;
      return {
        messages: queue.messages.map((message) => message.id === action.id
          ? { ...message, text: action.text.trim() } : message),
        editingId: null,
      };
    case 'cancelEdit':
      return { ...queue, editingId: null };
    case 'remove':
      return {
        messages: queue.messages.filter((message) => message.id !== action.id),
        editingId: queue.editingId === action.id ? null : queue.editingId,
      };
    case 'clear':
      return emptyMessageQueue;
  }
}

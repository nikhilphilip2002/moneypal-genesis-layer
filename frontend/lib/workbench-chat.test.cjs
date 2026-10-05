const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

function loadComponent(filename, react = React, modules = {}) {
  const exports = {};
  const compiled = ts.transpileModule(readFileSync(filename, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  vm.runInNewContext(compiled, {
    exports,
    require: (name) => {
      if (modules[name]) return modules[name];
      if (name === 'react') return react;
      if (name === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
      if (name === '@/lib/workbench-ui') return { SECTION_GAP: 'mt-4', SOURCE_BADGE: '' };
      if (name === '@/lib/workbench-cancellation') return { visibleTraceSteps: (updates) => updates };
      if (name.startsWith('@/components/ui/')) {
        const Component = ({ children }) => children;
        const Button = ({ children, disabled, 'aria-label': label }) =>
          React.createElement('button', { disabled, 'aria-label': label }, children);
        return { default: Component, Badge: Component, Button };
      }
      return require(name);
    },
  }, { filename });
  return exports.default;
}

test('queued messages show edit, remove, clear, and the hold from the edited entry', () => {
  const QueuedMessages = loadComponent(`${__dirname}/../components/workbench/QueuedMessages.tsx`);
  const queue = {
    messages: ['B', 'C', 'D'].map((text) => ({ id: text, text })), editingId: 'C',
  };
  const markup = renderToStaticMarkup(React.createElement(QueuedMessages, { queue, onChange() {} }));

  assert.doesNotMatch(markup, /\d+ queued|>\d+\.</);
  assert.equal(markup.match(/bg-muted/g)?.length, 3);
  assert.equal(markup.match(/rounded-br-md/g)?.length, 3);
  assert.match(markup, /Clear queue/);
  assert.ok(markup.indexOf('Clear queue') < markup.indexOf('<ul'));
  assert.match(markup, /absolute inset-0 size-full resize-none/);
  assert.doesNotMatch(markup, /min-h-20|resize-y|focus-visible:ring/);
  assert.match(markup, /Edit queued message 1/);
  assert.match(markup, /Remove queued message 3/);
  assert.ok(markup.indexOf('Remove queued message 1') > markup.indexOf('bg-muted'));
  assert.doesNotMatch(markup, /min-w-\[/);
  assert.match(markup, /group relative max-w-\[88%\]/);
  assert.match(markup, /absolute left-full top-2\.5/);
  assert.match(markup, /py-2\.5 text-right/);
  assert.match(markup, /p-0 text-right/);
  assert.doesNotMatch(markup, /justify-end pr-\[4\.25rem\]/);
  assert.match(markup, /opacity-0 group-hover:opacity-100/);
  assert.doesNotMatch(markup, />Save<|>Cancel</);
  assert.doesNotMatch(markup, /Enter to save|Esc to cancel|queued-message-edit-shortcuts/);
  assert.equal(markup.match(/border border-border\/50 bg-muted/g)?.length, 3);
  assert.match(markup, /flex justify-end py-2 text-right/);
  assert.equal(markup.match(/Waiting for edit/g)?.length, 2);
  assert.equal(renderToStaticMarkup(React.createElement(QueuedMessages, {
    queue: { messages: [], editingId: null }, onChange() {},
  })), '');
});

test('autocomplete keeps stable unique keys for borrowers sharing a name', () => {
  const results = [
    { kind: 'borrower', value: 'SHEELA', label: 'SHEELA', detail: 'Customer 101 · Account ending 1234' },
    { kind: 'borrower', value: 'SHEELA', label: 'SHEELA', detail: 'Customer 202 · Account ending 5678' },
  ];
  function suggestionKeys(suggestions) {
    const states = [
      'loans for SHE', [], [], { key: 'borrower\u0000SHE', results: suggestions }, 0, true, 288,
    ];
    let stateIndex = 0;
    const Composer = loadComponent(`${__dirname}/../components/workbench/Composer.tsx`, {
      ...React,
      useState: () => [states[stateIndex++], () => {}],
      useRef: () => ({ current: null }),
      useEffect: () => {},
      useMemo: (compute) => compute(),
    }, {
      '@/lib/api': {},
      '@/components/workbench/WorkbenchWorkspace': { WORKSPACE_TOOLS: [] },
    });
    const tree = Composer({ pinned: null, externalSourcesEnabled: false });
    const list = tree.props.children[0];
    assert.equal(list.props.children.length, 2);
    return list.props.children.map((item) => item.key);
  }
  const keys = suggestionKeys(results);
  assert.equal(new Set(keys).size, 2);
  assert.deepEqual(suggestionKeys([...results].reverse()), [...keys].reverse());
});

test('queued message edits save with Enter and cancel with Escape', () => {
  const QueuedMessages = loadComponent(`${__dirname}/../components/workbench/QueuedMessages.tsx`, {
    ...React, useState: () => ['Revised question', () => {}],
  });
  const actions = [];
  const tree = QueuedMessages({
    queue: { messages: [{ id: 'C', text: 'Original question' }], editingId: 'C' },
    onChange: (action) => actions.push(JSON.parse(JSON.stringify(action))),
  });
  function findTextarea(element) {
    if (element?.type === 'textarea') return element;
    return React.Children.toArray(element?.props?.children)
      .map(findTextarea).find(Boolean);
  }
  const textarea = findTextarea(tree);
  let prevented = 0;
  const keydown = (key, shiftKey = false, isComposing = false) => textarea.props.onKeyDown({
    key, shiftKey, nativeEvent: { isComposing }, preventDefault: () => { prevented += 1; },
  });

  keydown('Enter', true);
  keydown('Enter', false, true);
  assert.deepEqual(actions, []);
  assert.equal(prevented, 0);
  keydown('Enter');
  keydown('Escape');
  assert.deepEqual(actions, [
    { type: 'save', id: 'C', text: 'Revised question' },
    { type: 'cancelEdit' },
  ]);
  assert.equal(prevented, 2);
});

test('active trace streams inline and completed trace starts collapsed', () => {
  const ExecutionTrace = loadComponent(`${__dirname}/../components/workbench/ExecutionTrace.tsx`);
  const updates = [{ id: 'model', kind: 'model', status: 'running', label: 'Thinking', elapsed_ms: 10, reasoning: 'Checking the result' }];
  const active = renderToStaticMarkup(React.createElement(ExecutionTrace, { updates, active: true }));
  const complete = renderToStaticMarkup(React.createElement(ExecutionTrace, { updates, active: false }));

  assert.match(active, /Checking the result/);
  assert.match(active, /lucide-chevron-right/);
  assert.match(active, /border-l-2/);
  assert.doesNotMatch(active, /rounded-xl border border-border\/60 bg-muted\/15/);
  assert.doesNotMatch(complete, /lucide-circle-check|lucide-circle-alert/);
  assert.doesNotMatch(complete, /Checking the result/);
});

test('active trace shows prompt progress in the header and the model label once inside the trace', () => {
  const ExecutionTrace = loadComponent(`${__dirname}/../components/workbench/ExecutionTrace.tsx`);
  const step = {
    id: 'model', kind: 'model', status: 'running', label: 'Model deciding next action',
    elapsed_ms: 10, prompt_progress_percent: 42,
  };
  const starting = renderToStaticMarkup(React.createElement(ExecutionTrace, {
    updates: [{ ...step, prompt_progress_percent: 0 }], active: true,
  }));
  const processing = renderToStaticMarkup(React.createElement(ExecutionTrace, { updates: [step], active: true }));
  const generating = renderToStaticMarkup(React.createElement(ExecutionTrace, {
    updates: [{ ...step, prompt_progress_percent: undefined }], active: true,
  }));

  assert.match(starting, /Prompt Processing 0%/);
  assert.match(processing, /Prompt Processing 42%/);
  assert.equal(processing.match(/Prompt Processing 42%/g)?.length, 1);
  assert.equal(processing.match(/Model deciding next action/g)?.length, 1);
  assert.equal(generating.match(/Model deciding next action/g)?.length, 1);
  assert.doesNotMatch(generating, /Prompt Processing/);
});

test('compaction takes the active header until model prompt processing resumes', () => {
  const ExecutionTrace = loadComponent(`${__dirname}/../components/workbench/ExecutionTrace.tsx`);
  const model = {
    id: 'model-1', kind: 'model', status: 'running',
    label: 'Model deciding next action', elapsed_ms: 10, prompt_progress_percent: 0,
  };
  const compacting = renderToStaticMarkup(React.createElement(ExecutionTrace, {
    updates: [model, {
      id: 'compaction-1', kind: 'status', status: 'running',
      label: 'Compacting conversation…', elapsed_ms: 20,
    }], active: true,
  }));
  const resumed = renderToStaticMarkup(React.createElement(ExecutionTrace, {
    updates: [{ ...model, prompt_progress_percent: 42 }, {
      id: 'compaction-1', kind: 'status', status: 'complete',
      label: 'Conversation compacted', elapsed_ms: 30,
    }], active: true,
  }));

  assert.match(compacting, /<span>Compacting conversation…<\/span>/);
  assert.doesNotMatch(compacting, /Prompt Processing 0%/);
  assert.match(resumed, /<span>Prompt Processing 42%<\/span>/);
  assert.match(resumed, /Conversation compacted/);
});

test('model trace shows its start time in IST instead of elapsed duration', () => {
  const ExecutionTrace = loadComponent(`${__dirname}/../components/workbench/ExecutionTrace.tsx`);
  const step = {
    id: 'model-1', kind: 'model', status: 'running', label: 'Model deciding next action',
    elapsed_ms: 82, started_at: '2026-09-27T12:22:33+00:00',
  };
  const active = renderToStaticMarkup(React.createElement(ExecutionTrace, {
    updates: [step], active: true, startedAt: Date.now() - 2000,
  }));
  const complete = renderToStaticMarkup(React.createElement(ExecutionTrace, {
    updates: [{ ...step, status: 'complete', duration_ms: 250 }], active: true,
  }));

  assert.match(active, /Model deciding next action/);
  assert.match(active, /at 05:52:33 pm IST/);
  assert.doesNotMatch(active, /at 82 ms/);
  assert.match(complete, /at 05:52:33 pm IST/);
  assert.doesNotMatch(complete, /250 ms/);
  assert.doesNotMatch(complete, /at 82 ms/);
});

test('Workbench SQL disclosure omits generated-query boilerplate', () => {
  const LineagePanel = loadComponent(`${__dirname}/../components/nlq/LineagePanel.tsx`);
  const lineage = {
    sql: 'SELECT 1',
    display_sql: 'SELECT 1',
    unverified: true,
    requires_signoff: [],
    warnings: ['Visualization derived from query sample:q1 using none.'],
  };
  const markup = renderToStaticMarkup(React.createElement(LineagePanel, { lineage, plain: true }));

  assert.match(markup, /View SQL/);
  assert.doesNotMatch(markup, /Generated query|Visualization derived|rounded-xl border/);
});

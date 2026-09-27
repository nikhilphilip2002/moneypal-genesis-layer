const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

function loadComponent(filename) {
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
      if (name === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
      if (name === '@/lib/workbench-ui') return { SECTION_GAP: 'mt-4', SOURCE_BADGE: '' };
      if (name === '@/lib/workbench-cancellation') return { visibleTraceSteps: (updates) => updates };
      if (name.startsWith('@/components/ui/')) {
        const Component = ({ children }) => children;
        return { default: Component, Badge: Component, Button: Component };
      }
      return require(name);
    },
  }, { filename });
  return exports.default;
}

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

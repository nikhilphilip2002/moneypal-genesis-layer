const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function renderChart(chart, props = {}) {
  const { startAsTable = false, ...chartProps } = props;
  let firstStateCall = true;
  const rendered = { bars: [], lines: [], areas: [], charts: [], legends: [], tooltips: [] };
  const recharts = new Proxy({}, {
    get: (_, name) => (props) => {
      if (name === 'Bar') rendered.bars.push(props);
      if (name === 'Line') rendered.lines.push(props);
      if (name === 'Area') rendered.areas.push(props);
      if (['BarChart', 'LineChart', 'AreaChart'].includes(name)) rendered.charts.push(props);
      if (name === 'Legend') rendered.legends.push(props);
      if (name === 'Tooltip') rendered.tooltips.push(props);
      return props.children ?? null;
    },
  });
  const cache = new Map();
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename);
    const exports = {};
    cache.set(filename, exports);
    const compiled = ts.transpileModule(readFileSync(filename, 'utf8'), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
      },
    }).outputText;
    vm.runInNewContext(compiled, {
      exports,
      process,
      require: (name) => {
        if (name === 'recharts') return recharts;
        if (name === 'react' && startAsTable) {
          return {
            ...React,
            useState: (initial) => {
              if (firstStateCall) {
                firstStateCall = false;
                return [true, () => {}];
              }
              return React.useState(initial);
            },
          };
        }
        if (name === '@/components/ui/button') {
          return { Button: ({ children, className, variant }) => React.createElement('button', { className, 'data-variant': variant }, children) };
        }
        if (name === '@/components/ui/table') {
          return Object.fromEntries(Object.entries({
            Table: 'table', TableHeader: 'thead', TableBody: 'tbody',
            TableRow: 'tr', TableHead: 'th', TableCell: 'td',
          }).map(([component, tag]) => [component, ({ children, className }) => React.createElement(tag, { className }, children)]));
        }
        if (name.startsWith('@/components/ui/')) {
          return new Proxy({}, {
            get: (_, component) => (props) => component === 'Dialog' ? null : props.children,
          });
        }
        if (name === './chartTheme') return load(`${__dirname}/../components/nlq/chartTheme.ts`);
        if (name.startsWith('@/lib/')) return load(`${__dirname}/${name.slice(6)}.ts`);
        return require(name);
      },
    }, { filename });
    return exports;
  }
  const ChartRenderer = load(`${__dirname}/../components/nlq/ChartRenderer.tsx`).default;
  rendered.markup = renderToStaticMarkup(React.createElement(ChartRenderer, { chart, hideHeader: true, ...chartProps }));
  return rendered;
}

const groupedChart = {
  chart_type: 'grouped_bar',
  title: 'Weekly collections',
  x: { field: 'week_number', label: 'Week', unit: 'count' },
  series_by: { field: 'scheme_code', label: 'Scheme', unit: 'text' },
  series: [{ field: 'total_collected', label: 'Collected', unit: 'inr' }],
  rows: [
    { week_number: 31, scheme_code: 'MSME', total_collected: 11 },
    { week_number: 31, scheme_code: 'Personal', total_collected: 8 },
    { week_number: 32, scheme_code: 'MSME', total_collected: 15 },
  ],
};

test('plain chart renders values without result cards or generated summary', () => {
  const chart = {
    ...groupedChart,
    chart_type: 'kpi',
    series: [{ field: 'total_collected', label: 'Collected', unit: 'inr' }],
    rows: [{ total_collected: 19 }],
    summary: 'Heatmap derived from query example:q1.',
  };
  const { markup } = renderChart(chart, { plain: true, hideSummary: true });

  assert.match(markup, /Collected/);
  assert.match(markup, /justify-end/);
  assert.doesNotMatch(markup, /justify-start/);
  assert.equal((markup.match(/data-variant="ghost"/g) ?? []).length, 2);
  assert.equal((markup.match(/border border-border bg-transparent shadow-none/g) ?? []).length, 2);
  assert.doesNotMatch(markup, /What this shows|Heatmap derived from query|rounded-2xl border/);
});

test('Workbench KPI table keeps numeric columns left aligned', () => {
  const chart = {
    chart_type: 'kpi',
    title: 'Portfolio',
    columns: [{ name: 'balance', label: 'Balance', unit: 'count' }],
    series: [{ field: 'balance', label: 'Balance', unit: 'count' }],
    rows: [{ balance: 42 }],
    summary: '',
  };
  const { markup } = renderChart(chart, { plain: true, startAsTable: true });

  assert.match(markup, /<th[^>]*>Balance<\/th>/);
  assert.match(markup, /<td[^>]*>42<\/td>/);
  assert.doesNotMatch(markup, /text-right/);
  assert.match(markup, /justify-end/);
});

test('Workbench non-KPI chart controls also align right', () => {
  const { markup } = renderChart(groupedChart, { plain: true });

  assert.match(markup, /justify-end/);
  assert.doesNotMatch(markup, /justify-start/);
});

test('Workbench table uses the shadcn table with a subtle border and muted header', () => {
  const chart = {
    chart_type: 'table',
    title: 'Accounts',
    columns: [
      { name: 'account', label: 'Account', unit: 'text' },
      { name: 'balance', label: 'Balance', unit: 'count' },
    ],
    rows: [{ account: 'A001', balance: 42 }],
    summary: '',
  };
  const { markup } = renderChart(chart, { plain: true, hideSummary: true });

  assert.match(markup, /Account/);
  assert.match(markup, /A001/);
  assert.match(markup, /42/);
  assert.match(markup, /overflow-x-auto rounded-md border border-border\/70/);
  assert.match(markup, /<thead class="bg-muted\/70">/);
  assert.match(markup, /<th class="border-r border-border\/70 last:border-r-0">Account<\/th>/);
  assert.match(markup, /<td class="border-r border-border\/70 last:border-r-0">A001<\/td>/);
  assert.doesNotMatch(markup, /bg-muted\/80|odd:bg-muted/);
});

test('grouped bars render one series per group against shared categories', () => {
  const rendered = renderChart(groupedChart);

  assert.deepEqual(rendered.bars.map((bar) => bar.dataKey), ['MSME', 'Personal']);
  assert.deepEqual(JSON.parse(JSON.stringify(rendered.charts[0].data)), [
    { week_number: 31, MSME: 11, Personal: 8 },
    { week_number: 32, MSME: 15 },
  ]);
  assert.equal(rendered.charts[0].layout, 'horizontal');
  assert.equal(rendered.legends.length, 1);
  assert.notEqual(rendered.bars[0].fill, rendered.bars[1].fill);
  assert.ok(rendered.bars.every((bar) => bar.stackId === undefined));
});

test('stacked bars use the same grouped series with a shared stack', () => {
  const rendered = renderChart({ ...groupedChart, chart_type: 'stacked_bar' });

  assert.deepEqual(rendered.bars.map((bar) => bar.dataKey), ['MSME', 'Personal']);
  assert.ok(rendered.bars.every((bar) => bar.stackId === 'stack'));
});

test('grouped bars render numeric measures as side-by-side series', () => {
  const chart = {
    ...groupedChart,
    series_by: null,
    series: [
      { field: 'disbursed', label: 'Disbursed', unit: 'inr' },
      { field: 'collected', label: 'Collected', unit: 'inr' },
    ],
    rows: [
      { week_number: 31, disbursed: 168920000, collected: 4800000 },
      { week_number: 32, disbursed: 250463000, collected: 10500000 },
    ],
  };
  const rendered = renderChart(chart);

  assert.equal(rendered.charts[0].data, chart.rows);
  assert.deepEqual(rendered.bars.map((bar) => bar.dataKey), ['disbursed', 'collected']);
  assert.deepEqual(rendered.bars.map((bar) => bar.name), ['Disbursed', 'Collected']);
  assert.equal(rendered.charts[0].layout, 'horizontal');
  assert.equal(rendered.legends.length, 1);
  assert.ok(rendered.bars.every((bar) => bar.stackId === undefined));
});

test('mixed-unit scheme bars plot rupees alone and keep receipt counts in the tooltip and table', () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({
    scheme: `Scheme ${index + 1}`,
    receipt_count: index === 0 ? 42 : index + 1,
    total_collected: (12 - index) * 10_000_000,
  }));
  const chart = {
    chart_type: 'grouped_bar', title: 'Collections by scheme', subtitle: null,
    x: { field: 'scheme', label: 'Scheme', unit: 'text' }, series_by: null,
    series: [
      { field: 'receipt_count', label: 'Receipt Event Count', unit: 'count' },
      { field: 'total_collected', label: 'Total Collected INR', unit: 'inr' },
    ],
    columns: [
      { name: 'scheme', label: 'Scheme', unit: 'text' },
      { name: 'receipt_count', label: 'Receipt Event Count', unit: 'count' },
      { name: 'total_collected', label: 'Total Collected INR', unit: 'inr' },
    ],
    rows,
  };
  const rendered = renderChart(chart);
  const table = renderChart(chart, { startAsTable: true });
  const tooltip = renderToStaticMarkup(React.cloneElement(rendered.tooltips[0].content, {
    active: true,
    label: rows[0].scheme,
    payload: [{ dataKey: 'total_collected', name: 'Total Collected INR',
      value: rows[0].total_collected, payload: rows[0] }],
  }));

  assert.deepEqual(rendered.bars.map((bar) => bar.dataKey), ['total_collected']);
  assert.equal(rendered.bars[0].minPointSize, 0);
  assert.equal(rendered.charts[0].layout, 'vertical');
  assert.equal(rendered.charts[0].data.length, 10);
  assert.equal(rendered.charts[0].data[0].scheme, 'Scheme 1');
  assert.equal(rendered.legends.length, 0);
  assert.match(rendered.markup, /Showing the top 10 of 12 categories/);
  assert.match(tooltip, /Receipt Event Count/);
  assert.match(tooltip, /42/);
  assert.match(table.markup, /Scheme 12/);
  assert.deepEqual(renderChart({ ...chart, rows: rows.slice(0, 1) }).bars.map((bar) => bar.dataKey), [
    'total_collected',
  ]);
});

test('ordinary bars preserve their rows and compact single-series layout', () => {
  const chart = {
    ...groupedChart,
    chart_type: 'bar',
    series_by: null,
    rows: [
      { week_number: 31, total_collected: 19 },
      { week_number: 32, total_collected: 15 },
    ],
  };
  const rendered = renderChart(chart);

  assert.equal(rendered.charts[0].data, chart.rows);
  assert.deepEqual(rendered.bars.map((bar) => bar.dataKey), ['total_collected']);
  assert.equal(rendered.charts[0].layout, 'vertical');
  assert.equal(rendered.legends.length, 0);
});

for (const chartType of ['grouped_bar', 'stacked_bar', 'line', 'area', 'stacked_area']) {
  for (const groupCount of [8, 9, 10]) {
    test(`${chartType} preserves all values when rendering ${groupCount} groups`, () => {
      const rows = [31, 32].flatMap((week) => Array.from({ length: groupCount }, (_, index) => ({
        week_number: week,
        scheme_code: `Scheme ${index + 1}`,
        total_collected: (index + 1) * (week - 30),
      })));
      const rendered = renderChart({ ...groupedChart, chart_type: chartType, rows });
      const marks = [...rendered.bars, ...rendered.lines, ...rendered.areas];
      const expectedFields = Array.from(
        { length: groupCount > 8 ? 7 : 8 }, (_, index) => `Scheme ${index + 1}`,
      );
      if (groupCount > 8) expectedFields.push('Other');

      assert.deepEqual(marks.map((mark) => mark.dataKey), expectedFields);
      assert.deepEqual(marks.map((mark) => mark.name), expectedFields);
      assert.equal(rendered.legends.length, 1);
      for (const row of rendered.charts[0].data) {
        const expectedTotal = rows.filter((source) => source.week_number === row.week_number)
          .reduce((sum, source) => sum + source.total_collected, 0);
        const renderedTotal = marks.reduce((sum, mark) => sum + row[mark.dataKey], 0);
        assert.equal(renderedTotal, expectedTotal);
        if (groupCount > 8) {
          const expectedOther = rows.filter((source) => source.week_number === row.week_number)
            .slice(7).reduce((sum, source) => sum + source.total_collected, 0);
          assert.equal(row.Other, expectedOther);
        }
      }
    });
  }
}

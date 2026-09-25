const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function renderChart(chart) {
  const rendered = { bars: [], lines: [], areas: [], charts: [], legends: [] };
  const recharts = new Proxy({}, {
    get: (_, name) => (props) => {
      if (name === 'Bar') rendered.bars.push(props);
      if (name === 'Line') rendered.lines.push(props);
      if (name === 'Area') rendered.areas.push(props);
      if (['BarChart', 'LineChart', 'AreaChart'].includes(name)) rendered.charts.push(props);
      if (name === 'Legend') rendered.legends.push(props);
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
  renderToStaticMarkup(React.createElement(ChartRenderer, { chart, hideHeader: true }));
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

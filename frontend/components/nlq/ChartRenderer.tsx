'use client';

import { useMemo, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, Pie, PieChart,
  ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import type { ChartSpec, ColumnSpec, SeriesSpec } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  MAX_SERIES, SEQUENTIAL_BINS, divergingColor, formatTick, formatValue, heatColor, heatInk, ink,
  seriesColor, useChartMode,
} from './chartTheme';
import { cn } from '@/lib/utils';

// One renderer, switching on chart_type. The backend chose the type deterministically from
// the result shape — this component never second-guesses it, so the same question always
// looks the same.
//
// Every form can be flipped to its table view. That is not only a convenience: three of the
// light-mode palette slots sit below 3:1 contrast, and the dataviz relief rule requires a
// table or direct labels wherever that is true.

type Props = {
  chart: ChartSpec;
  onDrilldown?: (spec: NonNullable<ChartSpec['drilldown']>) => void;
};

export default function ChartRenderer({ chart, onDrilldown }: Props) {
  const [asTable, setAsTable] = useState(false);
  const mode = useChartMode();
  const showTable = asTable || chart.chart_type === 'table';

  return (
    <div className="w-full">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground">{chart.title}</h3>
          {chart.subtitle && (
            <p className="truncate text-xs text-muted-foreground">{chart.subtitle}</p>
          )}
        </div>
        {chart.chart_type !== 'table' && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setAsTable((v) => !v)}
            className="h-7 shrink-0 text-xs font-normal text-muted-foreground hover:text-foreground"
          >
            {asTable ? 'View chart' : 'View table'}
          </Button>
        )}
      </div>

      {chart.rows.length === 0 ? (
        <EmptyState summary={chart.summary} />
      ) : showTable ? (
        <TableView chart={chart} />
      ) : (
        <ChartBody chart={chart} mode={mode} onDrilldown={onDrilldown} />
      )}

      {chart.summary && (
        <p className="mt-3 text-sm leading-relaxed text-foreground/90">{chart.summary}</p>
      )}
    </div>
  );
}

function ChartBody({
  chart, mode, onDrilldown,
}: Props & { mode: 'light' | 'dark' }) {
  switch (chart.chart_type) {
    case 'kpi':
      return <KpiTiles chart={chart} />;
    case 'line':
    case 'area':
    case 'stacked_area':
      return <TimeView chart={chart} mode={mode} />;
    case 'bar':
    case 'ranking':
    case 'grouped_bar':
    case 'stacked_bar':
      return <BarView chart={chart} mode={mode} onDrilldown={onDrilldown} />;
    case 'donut':
      return <DonutView chart={chart} mode={mode} />;
    case 'variance':
      return <VarianceView chart={chart} mode={mode} />;
    case 'dumbbell':
      return <DumbbellView chart={chart} mode={mode} />;
    case 'scatter':
      return <ScatterView chart={chart} mode={mode} />;
    case 'heatmap':
      return <HeatmapView chart={chart} mode={mode} />;
    case 'small_multiples':
      return <SmallMultiplesView chart={chart} mode={mode} />;
    case 'table':
      return <TableView chart={chart} />;
    default:
      // A chart_type the backend knows and this renderer does not is a bug, not a
      // preference. It used to fall through to a table silently, which is how `heatmap`
      // spent its whole life rendering as a spreadsheet.
      if (process.env.NODE_ENV !== 'production') {
        console.error(`ChartRenderer: no view for chart_type "${chart.chart_type}"`);
      }
      return <TableView chart={chart} />;
  }
}

// ─── Long → wide ───
// Rows arrive one per (x, category) pair. Every multi-series form needs them pivoted, and
// `series_by` names the column to pivot on so this never has to be inferred from the data.

type Wide = { rows: Record<string, unknown>[]; series: SeriesSpec[]; folded: number };

function usePivot(chart: ChartSpec): Wide {
  return useMemo(() => {
    const splitKey = chart.series_by?.field;
    const xKey = chart.x?.field ?? 'x';
    const base = chart.series[0];
    if (!splitKey || !base) return { rows: chart.rows, series: chart.series, folded: 0 };

    const order: string[] = [];
    for (const row of chart.rows) {
      const name = String(row[splitKey] ?? '—');
      if (!order.includes(name)) order.push(name);
    }
    // Colour is an identity channel for eight values at most. The ninth is not a new hue.
    const kept = order.slice(0, MAX_SERIES);
    const foldedNames = new Set(order.slice(MAX_SERIES));

    const byX = new Map<string, Record<string, unknown>>();
    for (const row of chart.rows) {
      const x = String(row[xKey] ?? '');
      if (!byX.has(x)) byX.set(x, { [xKey]: row[xKey] });
      const bucket = byX.get(x)!;
      const name = String(row[splitKey] ?? '—');
      const key = foldedNames.has(name) ? 'Other' : name;
      const value = row[base.field];
      if (typeof value === 'number') {
        bucket[key] = ((bucket[key] as number) ?? 0) + value;
      } else if (!(key in bucket)) {
        bucket[key] = value;
      }
    }

    const names = foldedNames.size ? [...kept, 'Other'] : kept;
    return {
      rows: [...byX.values()],
      series: names.map((name) => ({ field: name, label: name, unit: base.unit })),
      folded: foldedNames.size,
    };
  }, [chart]);
}

// ─── KPI ───
// A hero number, not a chart. No plot means no hover layer is owed.

function KpiTiles({ chart }: { chart: ChartSpec }) {
  const row = chart.rows[0] ?? {};
  return (
    <div className="flex flex-wrap gap-4">
      {chart.series.map((series) => (
        <Card key={series.field} className="min-w-[10rem] p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            {series.label}
          </div>
          <div className="mt-1 text-3xl font-semibold tabular-nums text-foreground">
            {formatValue(row[series.field], series.unit)}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ─── Line / area / stacked area ───
// One component: the three differ only in whether the space under the curve is filled and
// whether the fills stack. The backend decides that from the metric's grain — filling under
// a stock like PAR 30 would claim that three months of it sum to something.

function TimeView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const { rows, series, folded } = usePivot(chart);
  const unit = series[0]?.unit ?? 'count';
  const xKey = chart.x?.field ?? 'x';
  const filled = chart.chart_type !== 'line';
  const stacked = chart.chart_type === 'stacked_area';

  // A single series gets a dotted mean line. It is data, not chrome — the one dashed
  // element on the plot, so it cannot be mistaken for a gridline.
  const mean = useMemo(() => {
    if (series.length !== 1) return null;
    const values = rows
      .map((row) => row[series[0].field])
      .filter((v): v is number => typeof v === 'number');
    if (values.length < 3) return null;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }, [rows, series]);

  const Chart = filled ? AreaChart : LineChart;

  return (
    <>
      <ResponsiveContainer width="100%" height={280}>
        <Chart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid stroke={palette.grid} strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: palette.secondary, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: palette.grid }}
          />
          <YAxis
            tick={{ fill: palette.secondary, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => formatTick(v, unit)}
            width={64}
          />
          <Tooltip content={<ChartTooltip chart={chart} />} cursor={{ stroke: palette.muted }} />
          {series.length > 1 && (
            <Legend wrapperStyle={{ fontSize: 12, color: palette.secondary }} />
          )}
          {mean !== null && (
            <ReferenceLine
              y={mean}
              stroke={palette.muted}
              strokeDasharray="4 4"
              strokeWidth={1}
              label={{
                value: `avg ${formatTick(mean, unit)}`,
                position: 'insideTopRight',
                fill: palette.muted,
                fontSize: 11,
              }}
            />
          )}
          {series.slice(0, MAX_SERIES).map((item, index) =>
            filled ? (
              <Area
                key={item.field}
                type="monotone"
                dataKey={item.field}
                name={item.label}
                stackId={stacked ? 'stack' : undefined}
                // Stacked bands butt against each other, so the "stroke" is a 2px band of
                // the surface colour separating them — a gap, not a border drawn around
                // each shape. A lone band keeps its own hue as the line above a faint wash.
                stroke={stacked ? palette.surface : seriesColor(index, mode)}
                strokeWidth={2}
                fill={seriesColor(index, mode)}
                fillOpacity={stacked ? 0.9 : 0.14}
                activeDot={{ r: 5, stroke: palette.surface, strokeWidth: 2 }}
                connectNulls={false}
              />
            ) : (
              <Line
                key={item.field}
                type="monotone"
                dataKey={item.field}
                name={item.label}
                stroke={seriesColor(index, mode)}
                strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, stroke: palette.surface, strokeWidth: 2 }}
                // A gap in the data must read as a gap, not as a line drawn straight
                // through months where nothing was recorded.
                connectNulls={false}
              />
            ),
          )}
        </Chart>
      </ResponsiveContainer>
      <FoldedNote folded={folded} />
    </>
  );
}

function FoldedNote({ folded }: { folded: number }) {
  if (folded <= 0) return null;
  return (
    <p className="mt-1 text-xs text-muted-foreground">
      {folded} smaller categories grouped as “Other” — switch to the table for the full list.
    </p>
  );
}

// ─── Bar / ranking ───

function BarView({
  chart, mode, onDrilldown,
}: Props & { mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const unit = chart.series[0]?.unit ?? 'count';
  const xKey = chart.x?.field ?? 'x';

  // Past MAX_SERIES categories, fold the tail into "Other" rather than inventing hues.
  const { rows, folded } = useMemo(() => {
    if (chart.chart_type !== 'ranking' || chart.rows.length <= MAX_SERIES) {
      return { rows: chart.rows, folded: 0 };
    }
    const head = chart.rows.slice(0, MAX_SERIES);
    const tail = chart.rows.slice(MAX_SERIES);
    const field = chart.series[0]?.field ?? '';
    const total = tail.reduce(
      (sum, row) => sum + (typeof row[field] === 'number' ? (row[field] as number) : 0), 0,
    );
    return { rows: [...head, { [xKey]: `Other (${tail.length})`, [field]: total }], folded: tail.length };
  }, [chart, xKey]);

  const single = chart.series.length === 1;
  // A lone vertical column expands to fill the plot and makes a simple result look much
  // more dramatic than it is. Short category comparisons are also easier to scan as a
  // labelled list, so keep one-to-six single-series results compact and horizontal.
  const compactCategories = single && rows.length <= 6;
  const horizontal = chart.chart_type === 'ranking' || compactCategories;
  const height = horizontal
    ? Math.max(compactCategories ? 112 : 220, rows.length * 42 + 36)
    : 280;

  return (
    <>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          accessibilityLayer
          data={rows}
          layout={horizontal ? 'vertical' : 'horizontal'}
          margin={{ top: 8, right: horizontal && single ? 88 : 24, bottom: 4, left: 8 }}
          barCategoryGap="22%"
        >
          <CartesianGrid stroke={palette.grid} vertical={horizontal} horizontal={!horizontal} />
          {horizontal ? (
            <>
              <XAxis
                type="number"
                tick={{ fill: palette.secondary, fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => formatTick(v, unit)}
              />
              <YAxis
                type="category"
                dataKey={xKey}
                tick={{ fill: palette.secondary, fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={150}
              />
            </>
          ) : (
            <>
              <XAxis
                dataKey={xKey}
                tick={{ fill: palette.secondary, fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: palette.grid }}
                interval={0}
                angle={rows.length > 6 ? -30 : 0}
                textAnchor={rows.length > 6 ? 'end' : 'middle'}
                height={rows.length > 6 ? 62 : 30}
              />
              <YAxis
                tick={{ fill: palette.secondary, fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => formatTick(v, unit)}
                width={64}
              />
            </>
          )}
          <Tooltip content={<ChartTooltip chart={chart} />} cursor={{ fill: palette.grid }} />
          {chart.series.length > 1 && (
            <Legend wrapperStyle={{ fontSize: 12, color: palette.secondary }} />
          )}
          {chart.series.slice(0, MAX_SERIES).map((series, seriesIndex) => (
            <Bar
              key={series.field}
              dataKey={series.field}
              name={series.label}
              maxBarSize={compactCategories ? 28 : 44}
              stackId={chart.chart_type === 'stacked_bar' ? 'stack' : undefined}
              radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
              cursor={onDrilldown && chart.drilldown ? 'pointer' : undefined}
              onClick={() => chart.drilldown && onDrilldown?.(chart.drilldown)}
            >
              {/* One series: the bars are one entity split by category, so they take a
                  single hue — varying colour there would imply an identity that is not
                  in the data. */}
              {single &&
                rows.map((_, rowIndex) => (
                  <Cell key={rowIndex} fill={seriesColor(0, mode)} />
                ))}
              {!single && <Cell fill={seriesColor(seriesIndex, mode)} />}
              {single && horizontal && (
                <LabelList
                  dataKey={series.field}
                  position="right"
                  formatter={(value: unknown) => formatValue(value, series.unit)}
                  fill={palette.primary}
                  fontSize={12}
                  fontWeight={600}
                />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      <FoldedNote folded={folded} />
    </>
  );
}

// ─── Donut ───
// Part-to-whole at a glance, never for comparing close values — which is why the backend
// only picks this when the question asked for a mix and there are six slices or fewer.

function DonutView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const field = chart.series[0]?.field ?? '';
  const unit = chart.series[0]?.unit ?? 'count';
  const labelKey = chart.x?.field ?? 'x';

  const { data, total } = useMemo(() => {
    const items = chart.rows.map((row) => ({
      name: String(row[labelKey] ?? '—'),
      value: typeof row[field] === 'number' ? (row[field] as number) : 0,
    }));
    return { data: items, total: items.reduce((sum, item) => sum + item.value, 0) };
  }, [chart, field, labelKey]);

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <ResponsiveContainer width="100%" height={260} className="max-w-[320px]">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="58%"
            outerRadius="88%"
            paddingAngle={1.5}
            // The gap between slices is the surface showing through, not a stroke drawn
            // around each one.
            stroke={palette.surface}
            strokeWidth={2}
          >
            {data.map((_, index) => (
              <Cell key={index} fill={seriesColor(index, mode)} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip chart={chart} total={total} />} />
        </PieChart>
      </ResponsiveContainer>
      {/* Direct labels, not a colour-only legend: every slice carries its name, its value
          and its share, so identity never rests on hue alone. */}
      <ul className="w-full min-w-0 flex-1 space-y-1.5">
        {data.map((item, index) => (
          <li key={item.name} className="flex items-center gap-2 text-sm">
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-[2px]"
              style={{ background: seriesColor(index, mode) }}
            />
            <span className="min-w-0 flex-1 truncate text-foreground">{item.name}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {formatValue(item.value, unit)}
            </span>
            <span className="w-12 shrink-0 text-right tabular-nums font-medium text-foreground">
              {total ? `${((item.value / total) * 100).toFixed(1)}%` : '—'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Variance ───
// Change against a baseline is polarity, so it takes the diverging pair and a zero rule.
// Grey at zero: the midpoint has to read as "nothing happened".

function VarianceView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const field = chart.series[0]?.field ?? 'delta';
  const unit = chart.series[0]?.unit ?? 'count';
  const xKey = chart.x?.field ?? 'x';

  if (chart.rows.length === 1) {
    return <SingleVarianceView chart={chart} mode={mode} />;
  }

  // Long category names go horizontal; time never does — twelve months read left to right
  // or they stop being a timeline.
  const horizontal = !chart.x?.grain && chart.rows.length > 8;

  return (
    <ResponsiveContainer
      width="100%"
      height={horizontal ? Math.max(220, chart.rows.length * 34) : 280}
    >
      <BarChart
        data={chart.rows}
        layout={horizontal ? 'vertical' : 'horizontal'}
        margin={{ top: 8, right: 24, bottom: 4, left: 8 }}
        barCategoryGap="22%"
      >
        <CartesianGrid stroke={palette.grid} vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis
              type="number"
              tick={{ fill: palette.secondary, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => formatTick(v, unit)}
            />
            <YAxis
              type="category"
              dataKey={xKey}
              tick={{ fill: palette.secondary, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={150}
            />
          </>
        ) : (
          <>
            <XAxis
              dataKey={xKey}
              tick={{ fill: palette.secondary, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              interval={0}
              angle={chart.rows.length > 6 ? -30 : 0}
              textAnchor={chart.rows.length > 6 ? 'end' : 'middle'}
              height={chart.rows.length > 6 ? 62 : 30}
            />
            <YAxis
              tick={{ fill: palette.secondary, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => formatTick(v, unit)}
              width={64}
            />
          </>
        )}
        <Tooltip content={<ChartTooltip chart={chart} />} cursor={{ fill: palette.grid }} />
        <ReferenceLine
          {...(horizontal ? { x: 0 } : { y: 0 })}
          stroke={palette.secondary}
          strokeWidth={1}
        />
        <Bar dataKey={field} name="Change" radius={2}>
          {chart.rows.map((row, index) => (
            <Cell
              key={index}
              fill={divergingColor(typeof row[field] === 'number' ? (row[field] as number) : 0, mode)}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function SingleVarianceView({
  chart, mode,
}: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const row = chart.rows[0] ?? {};
  const unit = chart.series[0]?.unit ?? 'count';
  const previous = typeof row.previous === 'number' ? row.previous : null;
  const current = typeof row.current === 'number' ? row.current : null;
  const delta = typeof row.delta === 'number' ? row.delta : null;
  const deltaPct = typeof row.delta_pct === 'number' ? row.delta_pct : null;
  const previousLabel = chart.columns.find((column) => column.name === 'previous')?.label ?? 'Previous';
  const currentLabel = chart.columns.find((column) => column.name === 'current')?.label ?? 'Current';
  const max = Math.max(Math.abs(previous ?? 0), Math.abs(current ?? 0), 1);
  const widthOf = (value: number | null) => value === null ? 0 : Math.abs(value) / max * 100;
  const changeColor = divergingColor(delta ?? 0, mode);
  const changeText = delta === null
    ? 'No comparison available'
    : `${delta > 0 ? '+' : ''}${formatValue(delta, unit)}`;

  return (
    <div
      className="rounded-lg bg-muted/30 p-4"
      role="img"
      aria-label={`${previousLabel}: ${formatValue(previous, unit)}; ${currentLabel}: ${formatValue(current, unit)}; change: ${changeText}`}
    >
      <div className="space-y-4">
        {[
          { label: previousLabel, value: previous, color: seriesColor(0, mode) },
          { label: currentLabel, value: current, color: seriesColor(1, mode) },
        ].map((item) => (
          <div key={item.label} className="grid grid-cols-[minmax(7rem,12rem)_1fr_auto] items-center gap-3">
            <span className="truncate text-xs text-muted-foreground" title={item.label}>
              {item.label}
            </span>
            <div className="h-3 overflow-hidden rounded-sm bg-muted">
              {item.value !== null && (
                <div
                  className="h-full min-w-0 rounded-sm"
                  style={{ width: `${widthOf(item.value)}%`, background: item.color }}
                />
              )}
            </div>
            <span className="min-w-20 text-right text-sm font-semibold tabular-nums text-foreground">
              {formatValue(item.value, unit)}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-border/60 pt-3">
        <span className="text-xs text-muted-foreground">Change</span>
        <Badge
          variant="outline"
          className="border-transparent font-semibold tabular-nums"
          style={{ color: changeColor, backgroundColor: `${changeColor}18` }}
        >
          {changeText}
          {deltaPct !== null && ` · ${deltaPct > 0 ? '+' : ''}${deltaPct.toFixed(1)}% relative`}
        </Badge>
      </div>
    </div>
  );
}

// ─── Dumbbell ───
// Before and after per item. Recharts has no dumbbell, and forcing one out of a scatter
// costs more than drawing it: two dots and the track between them is the whole mark.

function DumbbellView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const [before, after] = chart.series;
  const unit = after?.unit ?? 'count';
  const labelKey = chart.x?.field ?? 'x';

  const { items, min, span } = useMemo(() => {
    const values: number[] = [];
    const list = chart.rows.map((row) => {
      const from = typeof row[before?.field] === 'number' ? (row[before.field] as number) : null;
      const to = typeof row[after?.field] === 'number' ? (row[after.field] as number) : null;
      if (from !== null) values.push(from);
      if (to !== null) values.push(to);
      return { name: String(row[labelKey] ?? '—'), from, to };
    });
    const lo = Math.min(0, ...values);
    const hi = Math.max(...values, 0);
    return { items: list, min: lo, span: hi - lo || 1 };
  }, [chart, before, after, labelKey]);

  const at = (value: number) => ((value - min) / span) * 100;

  return (
    <div className="space-y-1">
      <div className="mb-2 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: seriesColor(0, mode) }} />
          {before?.label}
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: seriesColor(1, mode) }} />
          {after?.label}
        </span>
      </div>
      {items.map((item) => (
        <div key={item.name} className="group flex items-center gap-3 py-1.5">
          <span className="w-32 shrink-0 truncate text-xs text-muted-foreground" title={item.name}>
            {item.name}
          </span>
          {/* The row is the hit target, so it clears 24px without a pinpoint dot. */}
          <div className="relative h-6 min-w-0 flex-1">
            <div
              className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2"
              style={{ background: palette.grid }}
            />
            {item.from !== null && item.to !== null && (
              <div
                className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded-full"
                style={{
                  left: `${Math.min(at(item.from), at(item.to))}%`,
                  width: `${Math.abs(at(item.to) - at(item.from))}%`,
                  background: palette.muted,
                }}
              />
            )}
            {item.from !== null && (
              <span
                className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ background: seriesColor(0, mode), boxShadow: `0 0 0 2px ${palette.surface}` }}
                title={`${before?.label}: ${formatValue(item.from, unit)}`}
              />
            )}
            {item.to !== null && (
              <span
                className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ background: seriesColor(1, mode), boxShadow: `0 0 0 2px ${palette.surface}` }}
                title={`${after?.label}: ${formatValue(item.to, unit)}`}
              />
            )}
          </div>
          <span className="w-24 shrink-0 text-right text-xs tabular-nums text-foreground">
            {item.to !== null ? formatValue(item.to, unit) : '—'}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Scatter ───
// Two metrics, one point per category. Genuinely independent axes — there is no shared x
// for a second y-scale to be aligned against, so none of the dual-axis dishonesty applies.

function ScatterView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const [xMetric, yMetric] = chart.series;
  const labelKey = chart.x?.field ?? 'x';

  const data = useMemo(
    () => chart.rows.map((row) => ({ ...row, __label: String(row[labelKey] ?? '—') })),
    [chart, labelKey],
  );

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 12, right: 20, bottom: 28, left: 8 }}>
        <CartesianGrid stroke={palette.grid} />
        <XAxis
          type="number"
          dataKey={xMetric?.field}
          name={xMetric?.label}
          tick={{ fill: palette.secondary, fontSize: 12 }}
          tickLine={false}
          axisLine={{ stroke: palette.grid }}
          tickFormatter={(v) => formatTick(v, xMetric?.unit ?? 'count')}
          label={{
            value: xMetric?.label, position: 'insideBottom', offset: -16,
            fill: palette.secondary, fontSize: 12,
          }}
        />
        <YAxis
          type="number"
          dataKey={yMetric?.field}
          name={yMetric?.label}
          tick={{ fill: palette.secondary, fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => formatTick(v, yMetric?.unit ?? 'count')}
          width={64}
          label={{
            value: yMetric?.label, angle: -90, position: 'insideLeft',
            fill: palette.secondary, fontSize: 12,
          }}
        />
        {/* ~16px marks: comfortably above the 8px marker floor, and the hit area is the
            mark. One point per category — never the dense case that would need a
            nearest-point layer. */}
        <ZAxis range={[200, 200]} />
        <Tooltip
          content={<ChartTooltip chart={chart} labelKey="__label" />}
          cursor={{ strokeDasharray: '3 3', stroke: palette.muted }}
        />
        <Scatter
          data={data}
          fill={seriesColor(0, mode)}
          stroke={palette.surface}
          strokeWidth={2}
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

// ─── Heatmap ───
// A grid, not a plot — CSS handles it better than an SVG chart library would, and the cell
// is its own hit target. Magnitude is sequential: one hue, light→dark, five bins.

function HeatmapView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const field = chart.series[0]?.field ?? '';
  const unit = chart.series[0]?.unit ?? 'count';
  const rowKey = chart.x?.field ?? 'x';
  const colKey = chart.series_by?.field ?? '';

  const { rowNames, colNames, cells, max } = useMemo(() => {
    const rowsOrder: string[] = [];
    const colsOrder: string[] = [];
    const grid = new Map<string, number>();
    let peak = 0;
    for (const row of chart.rows) {
      const r = String(row[rowKey] ?? '—');
      const c = String(row[colKey] ?? '—');
      if (!rowsOrder.includes(r)) rowsOrder.push(r);
      if (!colsOrder.includes(c)) colsOrder.push(c);
      const value = typeof row[field] === 'number' ? (row[field] as number) : 0;
      grid.set(`${r} ${c}`, value);
      if (value > peak) peak = value;
    }
    return { rowNames: rowsOrder, colNames: colsOrder, cells: grid, max: peak };
  }, [chart, rowKey, colKey, field]);

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-background p-1 text-left font-normal text-muted-foreground">
                {chart.x?.label}
              </th>
              {colNames.map((name) => (
                <th key={name} className="p-1 text-center font-normal text-muted-foreground">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowNames.map((rowName) => (
              <tr key={rowName}>
                <th className="sticky left-0 z-10 max-w-[9rem] truncate bg-background p-1 text-left font-normal text-muted-foreground">
                  {rowName}
                </th>
                {colNames.map((colName) => {
                  const value = cells.get(`${rowName} ${colName}`);
                  const has = typeof value === 'number';
                  return (
                    <td
                      key={colName}
                      // The value is in the cell, so the grid is readable without hover
                      // and without relying on colour to carry magnitude alone.
                      className="min-w-[3.5rem] rounded-[3px] p-1.5 text-center tabular-nums"
                      style={{
                        background: has ? heatColor(value, max, mode) : 'transparent',
                        color: has ? heatInk(value, max, mode) : palette.muted,
                        outline: has ? 'none' : `1px dashed ${palette.grid}`,
                      }}
                      title={`${rowName} · ${colName}: ${has ? formatValue(value, unit) : 'no data'}`}
                    >
                      {has ? formatTick(value, unit) : '—'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>0</span>
        {Array.from({ length: SEQUENTIAL_BINS }, (_, bin) => (
          <span
            key={bin}
            aria-hidden
            className="h-2.5 w-6 rounded-[2px]"
            style={{ background: heatColor((bin / (SEQUENTIAL_BINS - 1)) * max, max, mode) }}
          />
        ))}
        <span>{formatTick(max, unit)}</span>
      </div>
    </div>
  );
}

// ─── Small multiples ───
// Sixteen branches on one time axis is a hairball; stacking them answers a question about
// the total that nobody asked. One panel per category, on a shared y-scale so the panels
// are comparable — which is the entire point of the form.

function SmallMultiplesView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const field = chart.series[0]?.field ?? '';
  const unit = chart.series[0]?.unit ?? 'count';
  const xKey = chart.x?.field ?? 'x';
  const splitKey = chart.series_by?.field ?? '';

  const { panels, domain } = useMemo(() => {
    const byName = new Map<string, Record<string, unknown>[]>();
    let peak = 0;
    for (const row of chart.rows) {
      const name = String(row[splitKey] ?? '—');
      if (!byName.has(name)) byName.set(name, []);
      byName.get(name)!.push(row);
      const value = typeof row[field] === 'number' ? (row[field] as number) : 0;
      if (value > peak) peak = value;
    }
    const list = [...byName.entries()].sort(
      (a, b) =>
        b[1].reduce((s, r) => s + (Number(r[field]) || 0), 0) -
        a[1].reduce((s, r) => s + (Number(r[field]) || 0), 0),
    );
    return { panels: list, domain: [0, peak || 1] as [number, number] };
  }, [chart, splitKey, field]);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
        {panels.map(([name, rows]) => (
          <div key={name} className="min-w-0">
            <div className="truncate text-xs font-medium text-foreground" title={name}>
              {name}
            </div>
            <ResponsiveContainer width="100%" height={72}>
              <LineChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
                <XAxis dataKey={xKey} hide />
                {/* Shared domain across every panel — panels on independent scales look
                    comparable and are not. */}
                <YAxis domain={domain} hide />
                <Tooltip content={<ChartTooltip chart={chart} />} cursor={{ stroke: palette.muted }} />
                <Line
                  type="monotone"
                  dataKey={field}
                  name={name}
                  stroke={seriesColor(0, mode)}
                  strokeWidth={1.5}
                  dot={false}
                  activeDot={{ r: 4, stroke: palette.surface, strokeWidth: 2 }}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {panels.length} panels on a shared scale, largest first · {formatTick(domain[1], unit)} full height
      </p>
    </div>
  );
}

// ─── Tooltip ───

function ChartTooltip({ chart, active, payload, label, total, labelKey }: any) {
  if (!active || !payload?.length) return null;
  // After a pivot the dataKeys are category names, so they are not in chart.series. The
  // metric's unit is the same for every one of them either way.
  const fallbackUnit = chart.series[0]?.unit ?? 'count';
  const heading = labelKey ? payload[0]?.payload?.[labelKey] ?? label : label;

  return (
    <div
      className={cn(
        'rounded-xl border border-border px-3 py-2 text-xs shadow-md',
        'bg-popover/85 backdrop-blur-[20px] [backdrop-filter:saturate(180%)_blur(20px)]',
        '[-webkit-backdrop-filter:saturate(180%)_blur(20px)]',
      )}
    >
      {heading != null && heading !== '' && (
        <div className="mb-1 font-medium text-foreground">{String(heading)}</div>
      )}
      {payload.map((entry: any, index: number) => {
        const series = chart.series.find((s: any) => s.field === entry.dataKey);
        const unit = series?.unit ?? fallbackUnit;
        const share =
          typeof total === 'number' && total > 0 && typeof entry.value === 'number'
            ? ` · ${((entry.value / total) * 100).toFixed(1)}%`
            : '';
        return (
          <div key={`${entry.dataKey}-${index}`} className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: entry.color ?? entry.payload?.fill }}
            />
            <span className="text-muted-foreground">{series?.label ?? entry.name}</span>
            <span className="ml-auto font-medium tabular-nums text-foreground">
              {formatValue(entry.value, unit)}
              {share}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Table ───

function TableView({ chart }: { chart: ChartSpec }) {
  return (
    <div className="max-h-[26rem] overflow-auto rounded-xl border border-border">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-muted/60 backdrop-blur">
          <TableRow>
            {chart.columns.map((column) => (
              <TableHead key={column.name} className={cn(isNumeric(column) && 'text-right')}>
                {column.label}
                {column.masked && (
                  <Badge
                    variant="outline"
                    className="ml-1 px-1.5 py-0 text-[10px] font-normal uppercase text-amber-700 dark:text-amber-400"
                  >
                    masked
                  </Badge>
                )}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {chart.rows.map((row, index) => (
            <TableRow key={index}>
              {chart.columns.map((column) => (
                <TableCell
                  key={column.name}
                  className={cn(
                    'text-foreground',
                    isNumeric(column) && 'text-right tabular-nums',
                    column.name === 'delta' && deltaTone(row[column.name]),
                  )}
                >
                  {formatValue(row[column.name], column.unit)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

const isNumeric = (column: ColumnSpec) =>
  ['inr', 'percent', 'count', 'days', 'ratio'].includes(column.unit);

// Direction is carried by an arrow in the value as well as by tone, so the sign is never
// communicated by colour alone.
function deltaTone(value: unknown): string {
  if (typeof value !== 'number' || value === 0) return '';
  return value > 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400';
}

function EmptyState({ summary }: { summary: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-6 text-center">
      <p className="text-sm text-muted-foreground">{summary || 'No rows matched this question.'}</p>
    </div>
  );
}

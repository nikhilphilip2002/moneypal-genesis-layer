'use client';

import { useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import type { ChartSpec, ColumnSpec } from '@/lib/api';
import { MAX_SERIES, formatTick, formatValue, ink, seriesColor, useChartMode } from './chartTheme';
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
  const showTable = asTable || chart.chart_type === 'table' || chart.chart_type === 'variance';

  return (
    <div className="w-full">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground">{chart.title}</h3>
          {chart.subtitle && (
            <p className="truncate text-xs text-muted-foreground">{chart.subtitle}</p>
          )}
        </div>
        {chart.chart_type !== 'table' && chart.chart_type !== 'variance' && (
          <button
            type="button"
            onClick={() => setAsTable((v) => !v)}
            className="shrink-0 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
          >
            {asTable ? 'Chart' : 'Table'}
          </button>
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
      return <LineView chart={chart} mode={mode} />;
    case 'bar':
    case 'ranking':
    case 'grouped_bar':
    case 'stacked_bar':
      return <BarView chart={chart} mode={mode} onDrilldown={onDrilldown} />;
    default:
      return <TableView chart={chart} />;
  }
}

// ─── KPI ───
// A hero number, not a chart. No plot means no hover layer is owed.

function KpiTiles({ chart }: { chart: ChartSpec }) {
  const row = chart.rows[0] ?? {};
  return (
    <div className="flex flex-wrap gap-4">
      {chart.series.map((series) => (
        <div key={series.field} className="min-w-[10rem] rounded-lg border border-border p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            {series.label}
          </div>
          <div className="mt-1 text-3xl font-semibold tabular-nums text-foreground">
            {formatValue(row[series.field], series.unit)}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Line ───

function LineView({ chart, mode }: { chart: ChartSpec; mode: 'light' | 'dark' }) {
  const palette = ink(mode);
  const unit = chart.series[0]?.unit ?? 'count';
  const xKey = chart.x?.field ?? 'x';

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chart.rows} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
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
        {chart.series.length > 1 && (
          <Legend wrapperStyle={{ fontSize: 12, color: palette.secondary }} />
        )}
        {chart.series.slice(0, MAX_SERIES).map((series, index) => (
          <Line
            key={series.field}
            type="monotone"
            dataKey={series.field}
            name={series.label}
            stroke={seriesColor(index, mode)}
            strokeWidth={2}
            dot={{ r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, stroke: palette.surface, strokeWidth: 2 }}
            // A gap in the data must read as a gap, not as a line drawn straight through
            // months where nothing was recorded.
            connectNulls={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
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
  const horizontal = chart.chart_type === 'ranking';

  return (
    <>
      <ResponsiveContainer width="100%" height={horizontal ? Math.max(220, rows.length * 34) : 280}>
        <BarChart
          data={rows}
          layout={horizontal ? 'vertical' : 'horizontal'}
          margin={{ top: 8, right: 24, bottom: 4, left: horizontal ? 8 : 8 }}
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
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      {folded > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          {folded} smaller categories grouped as “Other” — switch to the table for the full list.
        </p>
      )}
    </>
  );
}

// ─── Tooltip ───

function ChartTooltip({ chart, active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium text-foreground">{label}</div>
      {payload.map((entry: any) => {
        const series = chart.series.find((s: any) => s.field === entry.dataKey);
        return (
          <div key={entry.dataKey} className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: entry.color }}
            />
            <span className="text-muted-foreground">{series?.label ?? entry.name}</span>
            <span className="ml-auto font-medium tabular-nums text-foreground">
              {formatValue(entry.value, series?.unit ?? 'count')}
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
    <div className="max-h-[26rem] overflow-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-muted/60 backdrop-blur">
          <tr>
            {chart.columns.map((column) => (
              <th
                key={column.name}
                className={cn(
                  'px-3 py-2 text-left font-medium text-muted-foreground',
                  isNumeric(column) && 'text-right',
                )}
              >
                {column.label}
                {column.masked && (
                  <span className="ml-1 text-[10px] uppercase text-amber-600">masked</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chart.rows.map((row, index) => (
            <tr key={index} className="border-t border-border/60">
              {chart.columns.map((column) => (
                <td
                  key={column.name}
                  className={cn(
                    'px-3 py-2 text-foreground',
                    isNumeric(column) && 'text-right tabular-nums',
                    column.name === 'delta' && deltaTone(row[column.name]),
                  )}
                >
                  {formatValue(row[column.name], column.unit)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
    <div className="rounded-lg border border-dashed border-border p-6 text-center">
      <p className="text-sm text-muted-foreground">{summary || 'No rows matched this question.'}</p>
    </div>
  );
}

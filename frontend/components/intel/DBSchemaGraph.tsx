'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import dynamic from 'next/dynamic';
import { useTheme } from 'next-themes';
import {
  AlertTriangle,
  Award,
  Building2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  CreditCard,
  Database,
  GitBranch,
  LayoutGrid,
  Link2,
  Maximize2,
  Minimize2,
  Move,
  Network,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  Table2,
  UserRound,
  Users,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';

import { admin } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[420px] items-center justify-center text-xs text-muted-foreground">
      <Network className="mr-2 h-4 w-4 animate-spin text-primary" />
      Loading the portfolio graph…
    </div>
  ),
});

type GraphLevel = 'portfolio' | 'product' | 'branch' | 'scheme' | 'agent' | 'customer';
type WeightBy = 'borrowers' | 'outstanding' | 'accounts';
type DisplayMode = 'graph' | 'cards' | 'table';

interface Metrics {
  account_count?: number;
  active_account_count?: number;
  borrower_count?: number;
  sanctioned_amount?: number;
  disbursed_amount?: number;
  principal_outstanding?: number;
  total_overdue?: number;
  par30_ratio?: number;
  npa_ratio?: number;
  risk_coverage_pct?: number;
  loan_data_as_of?: string | null;
  active?: boolean;
  loan_status?: string;
  dpd_days?: number;
  is_par30?: boolean;
  is_npa?: boolean;
}

interface GraphNode {
  id: string;
  type: GraphLevel | 'account' | 'related_agent';
  code: string;
  label: string;
  metrics?: Metrics;
  rank?: number;
  is_leader?: boolean;
  weight_value?: number;
  account_count?: number;
  is_selected_path?: boolean;
  product_code?: string;
  product_name?: string;
  branch_code?: string;
  scheme_code?: string;
  scheme_name?: string;
  agent_code?: string;
}

interface PathItem {
  level: GraphLevel;
  code: string;
  label: string;
}

interface Coverage {
  snapshot_date?: string | null;
  snapshot_data_as_of?: string | null;
  entity_num: string;
  entity_basis: string;
  excluded_entity_note: string;
  effective_branch_basis: string;
  branch_basis_note: string;
  source_schema: string;
  source_views: string[];
}

interface GraphPayload {
  version: number;
  level: GraphLevel;
  current: GraphNode;
  nodes: GraphNode[];
  edges: Array<{ source: string; target: string; label: string }>;
  path: PathItem[];
  kpis: Metrics;
  children_total: number;
  visible_children: number;
  limit: number;
  offset: number;
  weight_by: WeightBy;
  month?: string | null;
  coverage: Coverage;
}

interface Selection {
  level: GraphLevel;
  product_code?: string;
  branch_code?: string;
  scheme_code?: string;
  agent_code?: string;
  customer_id?: string;
}

interface SearchResult {
  type: 'agent' | 'customer';
  code: string;
  label: string;
}

const PAGE_SIZE = 20;

const levelLabel: Record<string, string> = {
  portfolio: 'Loan Book',
  product: 'Product',
  branch: 'Branch',
  scheme: 'Scheme',
  agent: 'Agent',
  customer: 'Customer',
  account: 'Loan Account',
  related_agent: 'Linked Agent',
};

const levelTone: Record<string, string> = {
  portfolio: 'border-violet-500/50 bg-violet-500/10',
  product: 'border-indigo-500/50 bg-indigo-500/10',
  branch: 'border-blue-500/50 bg-blue-500/10',
  scheme: 'border-cyan-500/50 bg-cyan-500/10',
  agent: 'border-teal-500/50 bg-teal-500/10',
  customer: 'border-emerald-500/50 bg-emerald-500/10',
  account: 'border-amber-500/50 bg-amber-500/10',
  related_agent: 'border-sky-500/50 bg-sky-500/10',
};

/** Canvas fills for the force graph; one hue per tier so a drill-down reads at a glance. */
const levelColor: Record<string, string> = {
  portfolio: '#7c3aed',
  product: '#4f46e5',
  branch: '#2563eb',
  scheme: '#0891b2',
  agent: '#0d9488',
  customer: '#059669',
  account: '#d97706',
  related_agent: '#0284c7',
};

/** The tier a node of each type drills into, used for the canvas legend. */
const childLevelOf: Record<GraphLevel, string> = {
  portfolio: 'product',
  product: 'branch',
  branch: 'scheme',
  scheme: 'agent',
  agent: 'customer',
  customer: 'account',
};

function formatMoney(raw?: number): string {
  const value = Number(raw || 0);
  const abs = Math.abs(value);
  if (abs >= 10_000_000) return `₹${(value / 10_000_000).toFixed(abs >= 1_000_000_000 ? 1 : 2)} Cr`;
  if (abs >= 100_000) return `₹${(value / 100_000).toFixed(abs >= 10_000_000 ? 1 : 2)} L`;
  if (abs >= 1_000) return `₹${(value / 1_000).toFixed(abs >= 100_000 ? 1 : 2)} K`;
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function formatCount(value?: number): string {
  return Number(value || 0).toLocaleString('en-IN');
}

function nodeWeight(node: GraphNode, weight: WeightBy): number {
  if (node.type === 'related_agent') return Number(node.account_count || 0);
  if (node.type === 'account') {
    return Number(weight === 'outstanding' ? node.metrics?.principal_outstanding : 1);
  }
  if (weight === 'outstanding') return Number(node.metrics?.principal_outstanding || 0);
  if (weight === 'accounts') return Number(node.metrics?.account_count || 0);
  return Number(node.metrics?.borrower_count || 0);
}

function weightText(node: GraphNode, weight: WeightBy): string {
  const value = nodeWeight(node, weight);
  if (weight === 'outstanding') return formatMoney(value);
  return `${formatCount(value)} ${weight === 'accounts' ? 'accounts' : 'customers'}`;
}

function NodeIcon({ type }: { type: GraphNode['type'] }) {
  if (type === 'portfolio') return <Award className="h-4 w-4" />;
  if (type === 'branch') return <Building2 className="h-4 w-4" />;
  if (type === 'agent' || type === 'related_agent') return <UserRound className="h-4 w-4" />;
  if (type === 'customer') return <Users className="h-4 w-4" />;
  if (type === 'account') return <CreditCard className="h-4 w-4" />;
  return <GitBranch className="h-4 w-4" />;
}

function KpiCard({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/70 p-3">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}{label}
      </div>
      <div className="mt-1.5 font-mono text-base font-bold tracking-tight text-foreground">{value}</div>
    </div>
  );
}

export default function DBSchemaGraph({ contained = false }: { contained?: boolean }) {
  const { theme } = useTheme();
  const graphRef = useRef<any>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const [mounted, setMounted] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState<GraphPayload | null>(null);
  const [selection, setSelection] = useState<Selection>({ level: 'portfolio' });
  const [weightBy, setWeightBy] = useState<WeightBy>('borrowers');
  const [displayMode, setDisplayMode] = useState<DisplayMode>('graph');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 520 });
  const [month, setMonth] = useState('');
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);

  const isDark = theme === 'dark';

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (contained) setExpanded(false);
  }, [contained]);

  const loadGraph = useCallback(async (
    nextSelection: Selection,
    nextOffset = 0,
    nextWeight: WeightBy = weightBy,
    nextMonth: string = month,
  ) => {
    setLoading(true);
    setError('');
    try {
      const response = await admin.dbSchema({
        ...nextSelection,
        weight_by: nextWeight,
        month: nextMonth || undefined,
        limit: PAGE_SIZE,
        offset: nextOffset,
      }) as GraphPayload;
      if (response?.version !== 2 || !response.current || !Array.isArray(response.nodes)) {
        throw new Error('The Information Graph API is still on the legacy Silver contract. Deploy the Gold backend and frontend together.');
      }
      setData(response);
      setSelection(nextSelection);
      setSelectedNode(response.current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load the Gold portfolio graph.');
    } finally {
      setLoading(false);
    }
  }, [month, weightBy]);

  useEffect(() => {
    void loadGraph({ level: 'portfolio' }, 0, 'borrowers', '');
    // The initial request must run once; subsequent requests are driven by navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (search.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = window.setTimeout(() => {
      admin.dbSchemaSearch(search.trim())
        .then((response) => setSearchResults(response.results as SearchResult[]))
        .catch(() => setSearchResults([]));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [search]);

  const children = useMemo(
    () => data?.nodes.filter((node) => node.id !== data.current.id) || [],
    [data],
  );
  const maxWeight = Math.max(1, ...children.map((node) => nodeWeight(node, weightBy)));

  // The force graph mutates whatever objects it is handed, so hand it fresh copies on
  // every payload and keep the API nodes immutable.
  const forceGraphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    return {
      nodes: data.nodes.map((node) => {
        const isRoot = node.id === data.current.id;
        const share = Math.sqrt(nodeWeight(node, weightBy) / maxWeight) || 0;
        return {
          ...node,
          color: levelColor[node.type] || '#64748b',
          size: isRoot ? 26 : 9 + Math.round(share * 13),
        };
      }),
      links: data.edges.map((edge) => ({ ...edge })),
    };
  }, [data, weightBy, maxWeight]);

  const linksByNode = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const edge of data?.edges || []) {
      if (!map.has(edge.source)) map.set(edge.source, new Set());
      if (!map.has(edge.target)) map.set(edge.target, new Set());
      map.get(edge.source)!.add(edge.target);
      map.get(edge.target)!.add(edge.source);
    }
    return map;
  }, [data]);

  // Size the canvas to its container; the force graph needs explicit pixel dimensions.
  useEffect(() => {
    if (displayMode !== 'graph') return;
    const resize = () => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      setDimensions({ width: Math.max(360, rect.width), height: Math.max(380, rect.height) });
    };
    resize();
    const timer = window.setTimeout(resize, 120);
    window.addEventListener('resize', resize);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('resize', resize);
    };
  }, [displayMode, expanded, contained, data]);

  useEffect(() => {
    if (displayMode !== 'graph' || forceGraphData.nodes.length === 0) return;
    const timer = window.setTimeout(() => {
      graphRef.current?.d3Force('charge')?.strength(-620);
      graphRef.current?.d3Force('link')?.distance(150);
      graphRef.current?.zoomToFit(500, 90);
    }, 160);
    return () => window.clearTimeout(timer);
  }, [displayMode, forceGraphData, dimensions]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, scale: number) => {
    const size = node.size || 14;
    const isSelected = selectedNode?.id === node.id;
    const isHovered = hoverNode?.id === node.id;
    const isDimmed = Boolean(hoverNode && hoverNode.id !== node.id && !linksByNode.get(hoverNode.id)?.has(node.id));

    if (isSelected || isHovered) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, size + 6 / scale, 0, 2 * Math.PI);
      ctx.fillStyle = isDark ? 'rgba(124, 58, 237, 0.28)' : 'rgba(79, 70, 229, 0.22)';
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, size + (isHovered ? 2 : 0), 0, 2 * Math.PI);
    ctx.fillStyle = isDimmed ? (isDark ? '#1e293b' : '#e2e8f0') : node.color;
    ctx.fill();
    ctx.strokeStyle = isSelected
      ? (isDark ? '#ffffff' : '#0f172a')
      : isDark ? 'rgba(255,255,255,0.32)' : 'rgba(15,23,42,0.22)';
    ctx.lineWidth = (isSelected ? 3 : 1.5) / scale;
    ctx.stroke();

    if (isDimmed) return;

    // Keep labels near a constant on-screen size so they stay legible at any zoom.
    const label = String(node.label || '');
    const fontSize = Math.min((isSelected || isHovered ? 13 : 11) / scale, 34);
    ctx.font = `${isSelected || isHovered ? 700 : 500} ${fontSize}px Inter, system-ui, sans-serif`;
    const textWidth = ctx.measureText(label).width;
    const textY = node.y + size + 5;

    ctx.fillStyle = isDark ? 'rgba(15,23,42,0.88)' : 'rgba(255,255,255,0.92)';
    ctx.beginPath();
    ctx.roundRect(node.x - textWidth / 2 - 6, textY - 3, textWidth + 12, fontSize * 1.2 + 6, 4);
    ctx.fill();
    ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.1)';
    ctx.lineWidth = 1 / scale;
    ctx.stroke();

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = isDark ? '#f8fafc' : '#0f172a';
    ctx.fillText(label, node.x, textY);

    const weight = weightText(node as GraphNode, weightBy);
    ctx.font = `500 ${fontSize * 0.85}px Inter, system-ui, sans-serif`;
    ctx.fillStyle = isDark ? '#94a3b8' : '#475569';
    ctx.fillText(weight, node.x, textY + fontSize * 1.35);
  }, [selectedNode, hoverNode, linksByNode, isDark, weightBy]);

  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D, scale: number) => {
    const start = link.source;
    const end = link.target;
    if (!start?.x || !end?.x) return;

    const focus = hoverNode || selectedNode;
    const isFocused = Boolean(focus && (start.id === focus.id || end.id === focus.id));
    const isDimmed = Boolean(focus) && !isFocused;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = isFocused
      ? (isDark ? 'rgba(168,85,247,0.95)' : 'rgba(124,58,237,0.9)')
      : `rgba(${isDark ? '148,163,184' : '100,116,139'}, ${isDimmed ? 0.09 : 0.4})`;
    ctx.lineWidth = isFocused ? 2.5 : 1.4;
    ctx.stroke();

    if (isDimmed || (scale <= 0.75 && !isFocused)) return;
    const label = String(link.label || '');
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    ctx.font = `500 ${Math.max(8, 10 / Math.max(scale, 0.6))}px Inter, sans-serif`;
    const width = ctx.measureText(label).width;
    ctx.fillStyle = isDark ? 'rgba(15,23,42,0.85)' : 'rgba(241,245,249,0.9)';
    ctx.fillRect(midX - width / 2 - 3, midY - 6, width + 6, 12);
    ctx.fillStyle = isDark ? '#cbd5e1' : '#334155';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, midX, midY);
  }, [hoverNode, selectedNode, isDark]);

  const paintPointerArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, (node.size || 14) + 12, 0, 2 * Math.PI);
    ctx.fill();
  }, []);

  const zoomBy = (factor: number) => graphRef.current?.zoom((graphRef.current?.zoom() || 1) * factor, 300);

  const navigateNode = (node: GraphNode) => {
    setSelectedNode(node);
    if (node.type === 'account') return;
    if (node.type === 'related_agent') {
      setWeightBy('outstanding');
      void loadGraph({ level: 'agent', agent_code: node.code }, 0, 'outstanding');
      return;
    }
    const next: Selection = { ...selection, level: node.type as GraphLevel };
    if (node.type === 'product') {
      Object.assign(next, { product_code: node.code, branch_code: undefined, scheme_code: undefined, agent_code: undefined, customer_id: undefined });
    } else if (node.type === 'branch') {
      Object.assign(next, { branch_code: node.code, scheme_code: undefined, agent_code: undefined, customer_id: undefined });
    } else if (node.type === 'scheme') {
      Object.assign(next, { scheme_code: node.code, agent_code: undefined, customer_id: undefined });
    } else if (node.type === 'agent') {
      Object.assign(next, { agent_code: node.code, customer_id: undefined });
      setWeightBy('outstanding');
    } else if (node.type === 'customer') {
      Object.assign(next, { customer_id: node.code });
    } else if (node.type === 'portfolio') {
      Object.keys(next).forEach((key) => { if (key !== 'level') delete next[key as keyof Selection]; });
    }
    void loadGraph(next, 0, node.type === 'agent' ? 'outstanding' : weightBy);
  };

  const navigatePath = (item: PathItem) => {
    if (item.level === 'portfolio') {
      void loadGraph({ level: 'portfolio' }, 0);
      return;
    }
    const next: Selection = { level: item.level };
    for (const pathItem of data?.path || []) {
      if (pathItem.level === 'product') next.product_code = pathItem.code;
      if (pathItem.level === 'branch') next.branch_code = pathItem.code;
      if (pathItem.level === 'scheme') next.scheme_code = pathItem.code;
      if (pathItem.level === 'agent') next.agent_code = pathItem.code;
      if (pathItem.level === 'customer') next.customer_id = pathItem.code;
      if (pathItem.level === item.level) break;
    }
    if (item.level === 'agent') setWeightBy('outstanding');
    void loadGraph(next, 0, item.level === 'agent' ? 'outstanding' : weightBy);
  };

  const chooseSearch = (result: SearchResult) => {
    setSearch('');
    setSearchResults([]);
    if (result.type === 'agent') {
      setWeightBy('outstanding');
      void loadGraph({ level: 'agent', agent_code: result.code }, 0, 'outstanding');
    }
    else void loadGraph({ level: 'customer', customer_id: result.code }, 0);
  };

  const changeWeight = (next: WeightBy) => {
    setWeightBy(next);
    void loadGraph(selection, 0, next);
  };

  const changeMonth = (next: string) => {
    setMonth(next);
    void loadGraph(selection, 0, weightBy, next);
  };

  const inspector = selectedNode || data?.current;
  const inspectorMetrics = inspector?.metrics || {};
  const pageStart = (data?.offset || 0) + 1;
  const pageEnd = Math.min((data?.offset || 0) + PAGE_SIZE, data?.children_total || 0);

  const content = (
    <div className={`${expanded ? (contained ? 'absolute inset-0 z-30' : 'fixed inset-0 z-[9999]') : 'h-full min-h-[620px]'} flex w-full flex-col overflow-hidden bg-background`}>
      <div className="shrink-0 border-b border-border/70 px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Network className="h-5 w-5 text-primary" />
              <h2 className="font-headline text-lg font-semibold">GICC Portfolio Information Graph</h2>
              <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
                Gold governed views
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Loan Book → Product → Branch → Scheme → Agent → Customer → Loan Account
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search agent or customer" className="h-9 w-[230px] pl-8 text-xs" />
              {search && <button type="button" onClick={() => { setSearch(''); setSearchResults([]); }} className="absolute right-2.5 top-2.5"><X className="h-3.5 w-3.5" /></button>}
              {searchResults.length > 0 && (
                <div className="absolute right-0 top-10 z-50 max-h-72 w-[320px] overflow-auto rounded-xl border bg-card p-1 shadow-xl">
                  {searchResults.map((result) => (
                    <button key={`${result.type}:${result.code}`} type="button" onClick={() => chooseSearch(result)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-muted">
                      <NodeIcon type={result.type} />
                      <span className="min-w-0 flex-1 truncate text-xs font-medium">{result.label}</span>
                      <Badge variant="outline" className="text-[9px] uppercase">{result.type}</Badge>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Button variant="outline" size="sm" onClick={() => void loadGraph(selection, data?.offset || 0)} disabled={loading}>
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />Refresh
            </Button>
            {!contained && (
              <Button variant="outline" size="sm" onClick={() => setExpanded((value) => !value)}>
                {expanded ? <Minimize2 className="mr-1.5 h-3.5 w-3.5" /> : <Maximize2 className="mr-1.5 h-3.5 w-3.5" />}
                {expanded ? 'Exit' : 'Expand'}
              </Button>
            )}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1 overflow-x-auto">
            {(data?.path || [{ level: 'portfolio', code: '1', label: 'GICC Loan Book' } as PathItem]).map((item, index) => (
              <div key={`${item.level}:${item.code}`} className="flex shrink-0 items-center gap-1">
                {index > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                <button type="button" onClick={() => navigatePath(item)} className={`rounded-lg border px-2.5 py-1.5 text-xs transition-colors hover:bg-muted ${item.level === data?.level ? 'border-primary bg-primary/10 font-semibold text-primary' : 'border-border/70 text-muted-foreground'}`}>
                  {item.label}
                </button>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 rounded-lg border bg-background px-2 py-1 text-[10px] font-semibold uppercase text-muted-foreground">
              Origination month
              <input type="month" value={month} onChange={(event) => changeMonth(event.target.value)} className="bg-transparent text-xs font-medium normal-case text-foreground outline-none" />
              {month && <button type="button" onClick={() => changeMonth('')} title="Clear month"><X className="h-3 w-3" /></button>}
            </label>
            <div className="flex rounded-lg border bg-muted/30 p-0.5">
              {(['borrowers', 'outstanding', 'accounts'] as WeightBy[]).map((weight) => (
                <button key={weight} type="button" disabled={weight === 'borrowers' && (data?.level === 'agent' || data?.level === 'customer')} onClick={() => changeWeight(weight)} className={`rounded-md px-2.5 py-1 text-[10px] font-semibold capitalize disabled:cursor-not-allowed disabled:opacity-35 ${weightBy === weight ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'}`} title={weight === 'borrowers' && (data?.level === 'agent' || data?.level === 'customer') ? 'Every child represents one customer; use outstanding or accounts.' : undefined}>
                  {weight === 'borrowers' ? 'Customers' : weight}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border bg-muted/30 p-0.5">
              <button type="button" onClick={() => setDisplayMode('graph')} className={`rounded-md p-1.5 ${displayMode === 'graph' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`} title="Node graph"><Network className="h-3.5 w-3.5" /></button>
              <button type="button" onClick={() => setDisplayMode('cards')} className={`rounded-md p-1.5 ${displayMode === 'cards' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`} title="Ranked cards"><LayoutGrid className="h-3.5 w-3.5" /></button>
              <button type="button" onClick={() => setDisplayMode('table')} className={`rounded-md p-1.5 ${displayMode === 'table' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`} title="Table"><Table2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        </div>
      </div>

      {error ? (
        <div className="m-4 flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"><AlertTriangle className="h-4 w-4" />{error}</div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden p-3 lg:grid-cols-[310px_minmax(0,1fr)]">
          <aside className="flex min-h-0 flex-col overflow-hidden rounded-2xl border bg-card">
            <div className={`border-b border-border/70 p-4 ${levelTone[inspector?.type || 'portfolio']}`}>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground"><NodeIcon type={inspector?.type || 'portfolio'} />{levelLabel[inspector?.type || 'portfolio']}</div>
              <h3 className="mt-1.5 truncate text-base font-bold" title={inspector?.label}>{inspector?.label || 'Loading…'}</h3>
              {inspector?.code && <div className="mt-1 font-mono text-[10px] text-muted-foreground">Code: {inspector.code}</div>}
            </div>
            <div className="grid grid-cols-2 gap-2 border-b p-3">
              <KpiCard label="Outstanding" value={formatMoney(inspectorMetrics.principal_outstanding)} icon={<CircleDollarSign className="h-3 w-3" />} />
              <KpiCard label="Customers" value={formatCount(inspectorMetrics.borrower_count)} icon={<Users className="h-3 w-3" />} />
              <KpiCard label="Active loans" value={formatCount(inspectorMetrics.active_account_count)} icon={<CreditCard className="h-3 w-3" />} />
              <KpiCard label="Total overdue" value={formatMoney(inspectorMetrics.total_overdue)} icon={<ShieldAlert className="h-3 w-3" />} />
              <KpiCard label="PAR 30" value={`${Number(inspectorMetrics.par30_ratio || 0).toFixed(2)}%`} icon={<AlertTriangle className="h-3 w-3" />} />
              <KpiCard label="NPA ratio" value={`${Number(inspectorMetrics.npa_ratio || 0).toFixed(2)}%`} icon={<ShieldAlert className="h-3 w-3" />} />
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 text-xs">
              <div className="flex justify-between gap-3 rounded-lg bg-muted/40 p-2"><span className="text-muted-foreground">Sanctioned</span><strong>{formatMoney(inspectorMetrics.sanctioned_amount)}</strong></div>
              <div className="flex justify-between gap-3 rounded-lg bg-muted/40 p-2"><span className="text-muted-foreground">Disbursed</span><strong>{formatMoney(inspectorMetrics.disbursed_amount)}</strong></div>
              <div className="flex justify-between gap-3 rounded-lg bg-muted/40 p-2"><span className="text-muted-foreground">Risk coverage</span><strong>{Number(inspectorMetrics.risk_coverage_pct || 0).toFixed(1)}%</strong></div>
              {inspector?.type === 'account' && (
                <>
                  <div className="flex justify-between gap-3 rounded-lg bg-muted/40 p-2"><span className="text-muted-foreground">Product</span><strong>{inspector.product_name || inspector.product_code || '—'}</strong></div>
                  <div className="flex justify-between gap-3 rounded-lg bg-muted/40 p-2"><span className="text-muted-foreground">Scheme</span><strong>{inspector.scheme_name || inspector.scheme_code || '—'}</strong></div>
                  <div className="flex justify-between gap-3 rounded-lg bg-muted/40 p-2"><span className="text-muted-foreground">Agent code</span><strong>{inspector.agent_code || '—'}</strong></div>
                </>
              )}
              <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-[10px] leading-relaxed text-muted-foreground">
                <div className="mb-1 flex items-center gap-1 font-semibold uppercase text-amber-700 dark:text-amber-300"><Database className="h-3 w-3" />Data basis</div>
                Latest risk snapshot: <strong>{data?.coverage.snapshot_date || 'Unavailable'}</strong><br />
                Branch: {data?.coverage.effective_branch_basis}<br />
                {data?.coverage.branch_basis_note}
              </div>
            </div>
          </aside>

          <main className="relative min-h-0 overflow-hidden rounded-2xl border bg-muted/10">
            {loading && <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/65 backdrop-blur-[1px]"><RefreshCw className="h-5 w-5 animate-spin text-primary" /></div>}
            <div className="flex h-full min-h-[480px] flex-col">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div>
                  <h3 className="text-sm font-semibold">{data?.level === 'customer' ? 'Accounts and linked agents' : `Ranked ${levelLabel[children[0]?.type || 'product']} nodes`}</h3>
                  <p className="text-[10px] text-muted-foreground">
                    {month ? `Loans originated in ${month}; risk remains as at ${data?.coverage.snapshot_date || 'latest snapshot'}.` : `Current Gold portfolio as at ${data?.coverage.snapshot_date || 'latest available snapshot'}.`}
                  </p>
                </div>
                <Badge variant="outline" className="text-[10px]">{data?.children_total || 0} records</Badge>
              </div>

              {displayMode === 'graph' ? (
                <div ref={canvasRef} className="relative min-h-0 flex-1 overflow-hidden">
                  <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-[210px] rounded-xl border bg-background/85 p-2.5 shadow-sm backdrop-blur-md">
                    <span className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                      <Move className="h-2.5 w-2.5" />Drag, zoom, click to drill down
                    </span>
                    <div className="mt-1.5 space-y-1 text-[10px]">
                      {[data?.current.type || 'portfolio', ...new Set(children.map((node) => node.type))].map((type) => (
                        <div key={type} className="flex items-center gap-1.5">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: levelColor[type] }} />
                          <span className="font-medium text-foreground/80">{levelLabel[type]}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="absolute right-3 top-3 z-10 flex items-center gap-1 rounded-xl border bg-background/85 p-1 shadow-sm backdrop-blur-md">
                    <Button variant="ghost" size="sm" onClick={() => zoomBy(1.3)} title="Zoom in" className="h-7 w-7 rounded-lg p-0"><ZoomIn className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="sm" onClick={() => zoomBy(1 / 1.3)} title="Zoom out" className="h-7 w-7 rounded-lg p-0"><ZoomOut className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="sm" onClick={() => graphRef.current?.zoomToFit(400, 90)} title="Fit to view" className="h-7 w-7 rounded-lg p-0"><RotateCcw className="h-3.5 w-3.5" /></Button>
                  </div>

                  {mounted && forceGraphData.nodes.length > 0 && (
                    <ForceGraph2D
                      ref={graphRef}
                      width={dimensions.width}
                      height={dimensions.height}
                      graphData={forceGraphData}
                      backgroundColor={isDark ? '#090d16' : '#fafafa'}
                      nodeCanvasObject={paintNode}
                      nodePointerAreaPaint={paintPointerArea}
                      linkCanvasObject={paintLink}
                      onNodeClick={(node: any) => navigateNode(node as GraphNode)}
                      onNodeHover={(node: any) => setHoverNode((node as GraphNode) || null)}
                      enableNodeDrag
                      minZoom={0.15}
                      maxZoom={4}
                      cooldownTicks={200}
                      d3AlphaDecay={0.02}
                      d3VelocityDecay={0.22}
                      onEngineStop={() => graphRef.current?.zoomToFit(400, 90)}
                    />
                  )}

                  <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 rounded-xl border bg-background/85 px-3 py-1.5 text-[11px] shadow-sm backdrop-blur-md">
                    <Badge variant="outline" className="text-[10px] font-semibold uppercase">{levelLabel[data?.level || 'portfolio']} tier</Badge>
                    <span className="font-mono text-muted-foreground">{forceGraphData.nodes.length} nodes · {forceGraphData.links.length} edges</span>
                    <span className="hidden text-muted-foreground sm:inline">
                      · click a {levelLabel[childLevelOf[data?.level || 'portfolio']]?.toLowerCase() || 'node'} to go deeper
                    </span>
                  </div>

                  {!loading && forceGraphData.nodes.length === 0 && (
                    <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
                      <Network className="mb-2 h-7 w-7 opacity-40" />No governed relationships were found for this selection.
                    </div>
                  )}
                </div>
              ) : (
              <div className="min-h-0 flex-1 overflow-auto p-4">
                {displayMode === 'cards' ? (
                  <div className="grid min-w-0 gap-5 xl:grid-cols-[240px_36px_minmax(0,1fr)]">
                    <button type="button" onClick={() => data?.current && setSelectedNode(data.current)} className={`h-fit rounded-2xl border-2 p-4 text-left shadow-sm transition hover:-translate-y-0.5 ${levelTone[data?.current.type || 'portfolio']}`}>
                      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground"><NodeIcon type={data?.current.type || 'portfolio'} />Current {levelLabel[data?.current.type || 'portfolio']}</div>
                      <div className="mt-2 text-base font-bold">{data?.current.label}</div>
                      <div className="mt-3 text-xl font-black text-primary">{weightText(data?.current || { id: '', type: 'portfolio', code: '', label: '' }, weightBy)}</div>
                    </button>
                    <div className="hidden items-start justify-center pt-12 xl:flex"><ChevronRight className="h-7 w-7 text-muted-foreground/50" /></div>
                    <div className="grid content-start gap-2 sm:grid-cols-2 2xl:grid-cols-3">
                      {children.map((node) => {
                        const progress = Math.max(4, Math.round(nodeWeight(node, weightBy) / maxWeight * 100));
                        return (
                          <button key={node.id} type="button" onClick={() => navigateNode(node)} className={`group relative overflow-hidden rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-md ${levelTone[node.type] || ''}`}>
                            <div className="absolute inset-x-0 bottom-0 h-1 bg-muted"><div className="h-full bg-primary/70 transition-all" style={{ width: `${progress}%` }} /></div>
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase text-muted-foreground"><NodeIcon type={node.type} />{levelLabel[node.type]}</div>
                                <div className="mt-1 truncate text-sm font-semibold" title={node.label}>{node.label}</div>
                                <div className="mt-0.5 font-mono text-[9px] text-muted-foreground">{node.code}</div>
                              </div>
                              {node.rank && <span className="font-mono text-xs font-bold text-muted-foreground">#{node.rank}</span>}
                            </div>
                            <div className="mt-2 text-base font-black text-foreground">{weightText(node, weightBy)}</div>
                            {node.metrics && <div className="mt-1 text-[10px] text-muted-foreground">{formatCount(node.metrics.account_count)} loans · {formatMoney(node.metrics.principal_outstanding)}</div>}
                            {node.is_leader && <Badge className="mt-2 bg-primary text-[9px]">{weightBy === 'borrowers' ? 'Most customers' : weightBy === 'accounts' ? 'Most accounts' : 'Highest outstanding'}</Badge>}
                            {node.type === 'related_agent' && node.is_selected_path && <Badge variant="secondary" className="mt-2 text-[9px]">Selected path</Badge>}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border bg-card">
                    <table className="w-full min-w-[760px] border-collapse text-left text-xs">
                      <thead className="sticky top-0 bg-muted text-[10px] uppercase text-muted-foreground">
                        <tr><th className="p-3">Rank</th><th className="p-3">Name</th><th className="p-3">Code</th><th className="p-3 text-right">Customers</th><th className="p-3 text-right">Accounts</th><th className="p-3 text-right">Outstanding</th><th className="p-3 text-right">Sanctioned</th></tr>
                      </thead>
                      <tbody className="divide-y">
                        {children.map((node) => (
                          <tr key={node.id} onClick={() => navigateNode(node)} className="cursor-pointer hover:bg-muted/40">
                            <td className="p-3 font-mono">{node.rank || '—'}</td><td className="p-3 font-semibold">{node.label}</td><td className="p-3 font-mono text-muted-foreground">{node.code}</td>
                            <td className="p-3 text-right font-mono">{formatCount(node.metrics?.borrower_count)}</td><td className="p-3 text-right font-mono">{formatCount(node.metrics?.account_count || node.account_count)}</td>
                            <td className="p-3 text-right font-mono font-semibold">{formatMoney(node.metrics?.principal_outstanding)}</td><td className="p-3 text-right font-mono">{formatMoney(node.metrics?.sanctioned_amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {!loading && children.length === 0 && <div className="flex min-h-64 flex-col items-center justify-center text-center text-sm text-muted-foreground"><Network className="mb-2 h-7 w-7 opacity-40" />No governed relationships were found for this selection.</div>}
              </div>
              )}

              {(data?.children_total || 0) > PAGE_SIZE && (
                <div className="flex items-center justify-between border-t px-4 py-2 text-xs">
                  <span className="text-muted-foreground">Showing {pageStart}–{pageEnd} of {data?.children_total}</span>
                  <div className="flex gap-1">
                    <Button variant="outline" size="sm" disabled={(data?.offset || 0) === 0 || loading} onClick={() => void loadGraph(selection, Math.max(0, (data?.offset || 0) - PAGE_SIZE))}><ChevronLeft className="mr-1 h-3.5 w-3.5" />Previous</Button>
                    <Button variant="outline" size="sm" disabled={pageEnd >= (data?.children_total || 0) || loading} onClick={() => void loadGraph(selection, (data?.offset || 0) + PAGE_SIZE)}>Next<ChevronRight className="ml-1 h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              )}
            </div>
          </main>
        </div>
      )}

      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t px-4 py-2 text-[10px] text-muted-foreground">
        <div className="flex items-center gap-1.5"><Database className="h-3 w-3" />Entity {data?.coverage.entity_num || '1'} · {data?.coverage.source_views.join(' · ')}</div>
        <div className="flex items-center gap-1.5"><Link2 className="h-3 w-3" />Customer counts are distinct within each node; shared customers are not added to portfolio totals twice.</div>
      </div>
    </div>
  );

  if (expanded && mounted && !contained) return createPortal(content, document.body);
  return content;
}

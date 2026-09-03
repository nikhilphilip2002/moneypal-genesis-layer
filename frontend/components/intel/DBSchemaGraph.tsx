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
  Clock,
  CreditCard,
  Database,
  GitBranch,
  LayoutGrid,
  Link2,
  Maximize2,
  Minimize2,
  Move,
  Network,
  PanelRightClose,
  PanelRightOpen,
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
import Customer360Dialog from '@/components/intel/Customer360Dialog';
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

type GraphLevel = 'portfolio' | 'product' | 'branch' | 'scheme' | 'agent' | 'tenure' | 'loan_size' | 'customer';
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
  tenure_band?: string;
  loan_size_bucket?: string;
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
  tenure: 'Tenure',
  loan_size: 'Loan Size',
  customer: 'Customer',
  account: 'Loan Account',
  related_agent: 'Linked Agent',
};

/**
 * True pastel chart color tokens (chart-1 through chart-10) using shadcn variable naming scheme.
 * High brightness (L: 85%–90%) and reduced saturation (S: 45%–65%) for soft, milky pastel aesthetics.
 */
const chartColorsDark: Record<string, string> = {
  'chart-1': '#b8a9e8', // Pastel Lavender / Mauve
  'chart-2': '#a0c4f2', // Pastel Sky Blue
  'chart-3': '#8ecde8', // Pastel Ice Aqua
  'chart-4': '#98e4d4', // Pastel Mint
  'chart-5': '#a3dfb6', // Pastel Pistachio
  'chart-6': '#a4e2ec', // Pastel Powder Blue
  'chart-7': '#bec7f4', // Pastel Lilac
  'chart-8': '#f5be98', // Pastel Peach (soft apricot, never neon orange)
  'chart-9': '#f3dc8e', // Pastel Buttercream
  'chart-10': '#f0a8cb', // Pastel Blush Pink
};

const chartColorsLight: Record<string, string> = {
  'chart-1': '#dcd6f7', // Pastel Lavender / Mauve
  'chart-2': '#c7dcf7', // Pastel Sky Blue
  'chart-3': '#c2e9f4', // Pastel Ice Aqua
  'chart-4': '#c5ede5', // Pastel Mint
  'chart-5': '#cdeac7', // Pastel Pistachio
  'chart-6': '#c6e3f2', // Pastel Powder Blue
  'chart-7': '#d8d3f6', // Pastel Lilac
  'chart-8': '#fad8c3', // Pastel Peach Cream (soft and milky, never orange)
  'chart-9': '#f7e9be', // Pastel Buttercream
  'chart-10': '#f5d0de', // Pastel Blush Pink
};

/** Mapping from graph entity level to shadcn chart variable name */
const levelToChartVariable: Record<string, keyof typeof chartColorsDark> = {
  portfolio: 'chart-1',
  product: 'chart-2',
  branch: 'chart-3',
  scheme: 'chart-4',
  agent: 'chart-5',
  tenure: 'chart-6',
  loan_size: 'chart-7',
  customer: 'chart-8',
  account: 'chart-9',
  related_agent: 'chart-10',
};

function getNodeColor(type: string, isDark: boolean): string {
  const chartVar = levelToChartVariable[type] || 'chart-1';
  const palette = isDark ? chartColorsDark : chartColorsLight;
  return palette[chartVar] || (isDark ? '#64748b' : '#475569');
}

/** The tier a node of each type drills into, used for the canvas legend. */
const childLevelOf: Record<GraphLevel, string> = {
  portfolio: 'product',
  product: 'branch',
  branch: 'scheme',
  scheme: 'agent',
  agent: 'scheme',
  tenure: 'loan_size',
  loan_size: 'customer',
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

const textMeasureCache = new Map<string, number>();

function getCachedTextWidth(ctx: CanvasRenderingContext2D, text: string, font: string): number {
  const key = `${font}:${text}`;
  let width = textMeasureCache.get(key);
  if (width === undefined) {
    ctx.font = font;
    width = ctx.measureText(text).width;
    if (textMeasureCache.size > 1500) textMeasureCache.clear();
    textMeasureCache.set(key, width);
  }
  return width;
}

function weightText(node: GraphNode, weight: WeightBy): string {
  const value = nodeWeight(node, weight);
  if (weight === 'outstanding') return formatMoney(value);
  return `${formatCount(value)} ${weight === 'accounts' ? 'accounts' : 'customers'}`;
}

/** Branch and scheme names run long; an untrimmed label chip swallows its neighbours. */
function shortLabel(label: string, max = 24): string {
  const text = String(label || '');
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

/**
 * A d3-compatible collision force. force-graph bundles d3-force internally but does not
 * re-export it, so this keeps the graph free of a new dependency. The naive pairwise
 * sweep is fine at one page of children (≤ 21 nodes).
 */
function collisionForce(radiusOf: (node: any) => number) {
  let nodes: any[] = [];
  const force = (alpha: number) => {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = (b.x || 0) - (a.x || 0);
        const dy = (b.y || 0) - (a.y || 0);
        const minimum = radiusOf(a) + radiusOf(b);
        const distance = Math.sqrt(dx * dx + dy * dy) || 0.001;
        if (distance >= minimum) continue;
        const push = ((minimum - distance) / distance) * alpha * 0.6;
        const shiftX = dx * push;
        const shiftY = dy * push;
        a.vx = (a.vx || 0) - shiftX;
        a.vy = (a.vy || 0) - shiftY;
        b.vx = (b.vx || 0) + shiftX;
        b.vy = (b.vy || 0) + shiftY;
      }
    }
  };
  force.initialize = (next: any[]) => { nodes = next; };
  return force;
}

function NodeIcon({ type }: { type: GraphNode['type'] }) {
  if (type === 'portfolio') return <Award className="h-4 w-4" />;
  if (type === 'branch') return <Building2 className="h-4 w-4" />;
  if (type === 'agent' || type === 'related_agent') return <UserRound className="h-4 w-4" />;
  if (type === 'tenure') return <Clock className="h-4 w-4" />;
  if (type === 'loan_size') return <CircleDollarSign className="h-4 w-4" />;
  if (type === 'customer') return <Users className="h-4 w-4" />;
  if (type === 'account') return <CreditCard className="h-4 w-4" />;
  return <GitBranch className="h-4 w-4" />;
}

function MetricStat({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="flex flex-col py-0.5">
      <div className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-1 font-mono text-sm font-semibold tracking-tight text-foreground">
        {value}
      </div>
    </div>
  );
}

export default function DBSchemaGraph({ contained = false }: { contained?: boolean }) {
  // forcedTheme wins over the stored theme, so a stale `dark` in localStorage must not
  // paint a near-black canvas inside the light app shell.
  const { resolvedTheme, forcedTheme } = useTheme();
  const graphRef = useRef<any>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const fittedForRef = useRef<string>('');

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
  const [customerModalId, setCustomerModalId] = useState<string | null>(null);
  const [customerModalOpen, setCustomerModalOpen] = useState(false);
  const [showInspector, setShowInspector] = useState(true);

  const isDark = (forcedTheme ?? resolvedTheme) === 'dark';

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (contained) setExpanded(false);
  }, [contained]);

  const clientCacheRef = useRef<Map<string, GraphPayload>>(new Map());

  const loadGraph = useCallback(async (
    nextSelection: Selection,
    nextOffset = 0,
    nextWeight: WeightBy = weightBy,
    nextMonth: string = month,
    forceRefresh = false,
  ) => {
    const cacheKey = `${nextSelection.level}:${nextSelection.product_code || ''}:${nextSelection.branch_code || ''}:${nextSelection.scheme_code || ''}:${nextSelection.agent_code || ''}:${nextSelection.tenure_band || ''}:${nextSelection.loan_size_bucket || ''}:${nextSelection.customer_id || ''}:${nextWeight}:${nextMonth}:${nextOffset}`;

    if (!forceRefresh) {
      const cached = clientCacheRef.current.get(cacheKey);
      if (cached) {
        setData(cached);
        setSelection(nextSelection);
        setSelectedNode(cached.current);
        setLoading(false);
        setError('');
        return;
      }
    }

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
      clientCacheRef.current.set(cacheKey, response);
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
          isRoot,
          color: getNodeColor(node.type, isDark),
          size: isRoot ? 24 : 9 + Math.round(share * 12),
          formattedWeight: weightText(node as GraphNode, weightBy),
        };
      }),
      links: data.edges.map((edge) => ({ ...edge })),
    };
  }, [data, weightBy, maxWeight, isDark]);

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

  // The force graph needs explicit pixel dimensions and must track its container exactly:
  // the Workbench resizes this panel without ever firing a window resize.
  useEffect(() => {
    if (displayMode !== 'graph') return;
    const element = canvasRef.current;
    if (!element) return;
    const resize = () => {
      const rect = element.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return;
      setDimensions({ width: Math.round(rect.width), height: Math.round(rect.height) });
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, [displayMode]);

  // Spread the layout with the page size: 20 children at a fixed link distance collapse
  // into an unreadable knot of overlapping label chips.
  useEffect(() => {
    if (displayMode !== 'graph' || forceGraphData.nodes.length === 0) return;
    // ForceGraph2D is a dynamic import, so the ref can still be empty on the render that
    // first has data. Retry briefly rather than silently shipping the default layout.
    let attempts = 0;
    const apply = () => {
      const graph = graphRef.current;
      if (!graph?.d3Force) {
        attempts += 1;
        if (attempts < 20) timer = window.setTimeout(apply, 80);
        return;
      }
      const count = forceGraphData.nodes.length;
      graph.d3Force('charge')?.strength(-(360 + count * 26));
      graph.d3Force('link')?.distance(Math.min(320, 120 + count * 9));
      graph.d3Force('collide', collisionForce((node) => (node.size || 14) + 34));
      graph.d3ReheatSimulation?.();
    };
    let timer = window.setTimeout(apply, 0);
    return () => window.clearTimeout(timer);
  }, [displayMode, forceGraphData]);

  // Auto-fit once per payload only. Re-fitting on every engine stop yanked the view back
  // whenever the user dragged a node or zoomed in.
  useEffect(() => {
    fittedForRef.current = '';
  }, [data?.current?.id, displayMode]);

  const fitOnce = useCallback(() => {
    const key = `${data?.current?.id || ''}:${displayMode}`;
    if (fittedForRef.current === key) return;
    fittedForRef.current = key;
    graphRef.current?.zoomToFit(400, 70);
  }, [data?.current?.id, displayMode]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, scale: number) => {
    const size = node.size || 14;
    const isSelected = selectedNode?.id === node.id;
    const isHovered = hoverNode?.id === node.id;
    const isDimmed = Boolean(hoverNode && hoverNode.id !== node.id && !linksByNode.get(hoverNode.id)?.has(node.id));

    if (isSelected || isHovered) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, size + 5 / scale, 0, 2 * Math.PI);
      ctx.fillStyle = isDark ? 'rgba(148, 163, 184, 0.22)' : 'rgba(71, 85, 105, 0.16)';
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, size + (isHovered ? 1.5 : 0), 0, 2 * Math.PI);
    ctx.fillStyle = isDimmed ? (isDark ? '#1e293b' : '#cbd5e1') : node.color;
    ctx.fill();
    ctx.strokeStyle = isSelected
      ? (isDark ? '#f8fafc' : '#0f172a')
      : isDark ? 'rgba(255,255,255,0.22)' : 'rgba(15,23,42,0.22)';
    ctx.lineWidth = (isSelected ? 2.5 : 1.2) / scale;
    ctx.stroke();

    if (isDimmed) return;

    // Keep labels near a constant on-screen size, but cap them hard: an uncapped
    // 11px/scale label at a fitted zoom grows wider than the gap between two nodes.
    const isSpecial = isSelected || isHovered || node.isRoot;
    const fontSize = Math.min((isSpecial ? 13 : 11) / scale, 15);
    // Below this zoom the chips collide no matter how they are drawn; only the node
    // under the cursor and the node being inspected keep their label.
    if (scale < 0.55 && !isSpecial) return;

    const label = shortLabel(node.label, isSpecial ? 34 : 22);
    const font = `${isSpecial ? 700 : 500} ${fontSize}px Inter, system-ui, sans-serif`;
    const textWidth = getCachedTextWidth(ctx, label, font);
    const showWeight = isSpecial || scale > 1;
    const boxHeight = fontSize * (showWeight ? 2.4 : 1.2) + 6;
    const textY = node.y + size + 5;

    ctx.fillStyle = isDark ? 'rgba(15,23,42,0.88)' : 'rgba(255,255,255,0.92)';
    ctx.beginPath();
    ctx.roundRect(node.x - textWidth / 2 - 6, textY - 3, textWidth + 12, boxHeight, 4);
    ctx.fill();
    ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.1)';
    ctx.lineWidth = 1 / scale;
    ctx.stroke();

    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = isDark ? '#f8fafc' : '#0f172a';
    ctx.fillText(label, node.x, textY);

    if (!showWeight) return;
    ctx.font = `500 ${fontSize * 0.85}px Inter, system-ui, sans-serif`;
    ctx.fillStyle = isDark ? '#94a3b8' : '#475569';
    ctx.fillText(node.formattedWeight || weightText(node as GraphNode, weightBy), node.x, textY + fontSize * 1.3);
  }, [selectedNode, hoverNode, linksByNode, isDark, weightBy]);

  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D, scale: number) => {
    const start = link.source;
    const end = link.target;
    // A node parked at exactly x = 0 is falsy; guard on null, not truthiness, or its
    // edges silently vanish.
    if (start?.x == null || start?.y == null || end?.x == null || end?.y == null) return;

    const focus = hoverNode || selectedNode;
    const isFocused = Boolean(focus && (start.id === focus.id || end.id === focus.id));
    const isDimmed = Boolean(focus) && !isFocused;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);

    // Consistent dark gray edges for both dark and light modes
    const baseEdgeColor = isDark
      ? (isDimmed ? 'rgba(51, 65, 85, 0.3)' : 'rgba(71, 85, 105, 0.85)')   // Dark gray slate-600/700
      : (isDimmed ? 'rgba(71, 85, 105, 0.2)' : 'rgba(51, 65, 85, 0.75)');  // Dark gray slate-700
    const focusedEdgeColor = isDark
      ? 'rgba(203, 213, 225, 0.95)'  // Slate-300 contrast highlight
      : 'rgba(15, 23, 42, 0.95)';     // Slate-900 contrast highlight

    ctx.strokeStyle = isFocused ? focusedEdgeColor : baseEdgeColor;
    ctx.lineWidth = isFocused ? 2 : 1.3;
    ctx.stroke();

    if (isDimmed || (!isFocused && scale <= 0.85)) return;
    const label = String(link.label || '');
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    const linkFont = `500 ${Math.max(8, 10 / Math.max(scale, 0.6))}px Inter, sans-serif`;
    const width = getCachedTextWidth(ctx, label, linkFont);
    ctx.fillStyle = isDark ? 'rgba(15,23,42,0.92)' : 'rgba(248,250,252,0.94)';
    ctx.fillRect(midX - width / 2 - 3, midY - 6, width + 6, 12);
    ctx.font = linkFont;
    ctx.fillStyle = isDark ? '#94a3b8' : '#475569';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, midX, midY);
  }, [hoverNode, selectedNode, isDark]);

  // The hit area has to cover the label chip too — the label is what people aim at —
  // but stay tight enough that neighbouring nodes do not steal each other's clicks.
  const paintPointerArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    const size = (node.size || 14) + 4;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fill();
    const labelWidth = Math.max(70, Math.min(190, shortLabel(node.label, 22).length * 7 + 16));
    ctx.fillRect(node.x - labelWidth / 2, node.y + size, labelWidth, 22);
  }, []);

  const zoomBy = (factor: number) => graphRef.current?.zoom((graphRef.current?.zoom() || 1) * factor, 300);

  const navigateNode = (node: GraphNode) => {
    setSelectedNode(node);
    if (node.type === 'account') return;
    if (node.type === 'customer') {
      setCustomerModalId(node.code);
      setCustomerModalOpen(true);
      return;
    }
    // Clicking the node you are already on should inspect it, not refetch the same level
    // and throw away the current page.
    if (node.id === data?.current.id) return;
    if (node.type === 'related_agent') {
      setWeightBy('outstanding');
      void loadGraph({ level: 'agent', agent_code: node.code }, 0, 'outstanding');
      return;
    }
    const next: Selection = { ...selection, level: node.type as GraphLevel };
    if (node.type === 'product') {
      Object.assign(next, {
        product_code: node.code, branch_code: undefined, scheme_code: undefined,
        agent_code: undefined, tenure_band: undefined, loan_size_bucket: undefined, customer_id: undefined,
      });
    } else if (node.type === 'branch') {
      Object.assign(next, {
        branch_code: node.code, scheme_code: undefined,
        agent_code: undefined, tenure_band: undefined, loan_size_bucket: undefined, customer_id: undefined,
      });
    } else if (node.type === 'scheme') {
      Object.assign(next, {
        scheme_code: node.code,
        tenure_band: undefined, loan_size_bucket: undefined, customer_id: undefined,
      });
    } else if (node.type === 'agent') {
      Object.assign(next, {
        agent_code: node.code,
        tenure_band: undefined, loan_size_bucket: undefined, customer_id: undefined,
      });
      setWeightBy('outstanding');
    } else if (node.type === 'tenure') {
      Object.assign(next, {
        tenure_band: node.code,
        loan_size_bucket: undefined, customer_id: undefined,
      });
    } else if (node.type === 'loan_size') {
      Object.assign(next, {
        loan_size_bucket: node.code,
        customer_id: undefined,
      });
    } else if (node.type === 'portfolio') {
      Object.keys(next).forEach((key) => { if (key !== 'level') delete next[key as keyof Selection]; });
    }
    void loadGraph(next, 0, (node.type === 'agent' || node.type === 'loan_size') ? 'outstanding' : weightBy);
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
      if (pathItem.level === 'tenure') next.tenure_band = pathItem.code;
      if (pathItem.level === 'loan_size') next.loan_size_bucket = pathItem.code;
      if (pathItem.level === 'customer') next.customer_id = pathItem.code;
      if (pathItem.level === item.level) break;
    }
    if (item.level === 'agent' || item.level === 'loan_size') setWeightBy('outstanding');
    void loadGraph(next, 0, (item.level === 'agent' || item.level === 'loan_size') ? 'outstanding' : weightBy);
  };

  const chooseSearch = (result: SearchResult) => {
    setSearch('');
    setSearchResults([]);
    if (result.type === 'agent') {
      setWeightBy('outstanding');
      void loadGraph({ level: 'agent', agent_code: result.code }, 0, 'outstanding');
    } else {
      setCustomerModalId(result.code);
      setCustomerModalOpen(true);
    }
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
    <div className={`${expanded ? (contained ? 'absolute inset-0 z-30' : 'fixed inset-0 z-[9999]') : 'h-full min-h-[640px]'} flex w-full flex-col overflow-hidden bg-background`}>
      {/* ── 1. Unified Control Header (Single row, 48px) ── */}
      <header className={`shrink-0 flex items-center justify-between border-b border-border/40 px-3.5 h-12 bg-background/95 gap-3 ${contained ? 'pr-12' : ''}`}>
        {/* Left: Navigation path / Breadcrumbs */}
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="flex items-center gap-1.5 shrink-0 pr-2.5 border-r border-border/40 text-foreground">
            <Network className="h-4 w-4 text-primary shrink-0" />
            <span className="font-semibold text-xs tracking-tight hidden sm:inline">Info Graph</span>
            <Badge variant="outline" className="text-[9px] uppercase px-1 py-0 h-4 font-semibold border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hidden md:inline-flex">
              Gold
            </Badge>
          </div>

          <nav className="flex items-center gap-0.5 overflow-x-auto min-w-0 text-xs scrollbar-none py-0.5">
            {(data?.path || [{ level: 'portfolio', code: '1', label: 'GICC Loan Book' } as PathItem]).map((item, index) => (
              <div key={`${item.level}:${item.code}`} className="flex shrink-0 items-center gap-0.5">
                {index > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground/40 shrink-0" />}
                <button
                  type="button"
                  onClick={() => navigatePath(item)}
                  className={`px-2 py-1 rounded text-xs transition-colors truncate max-w-[150px] ${
                    item.level === data?.level
                      ? 'font-semibold text-foreground bg-muted/60'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
                  }`}
                  title={item.label}
                >
                  {item.label}
                </button>
              </div>
            ))}
          </nav>
        </div>

        {/* Right: Studio Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search agent / customer…"
              className="h-8 w-[160px] md:w-[210px] pl-8 pr-7 text-xs bg-muted/20 border-border/50 rounded-md focus-visible:ring-1"
            />
            {search && (
              <button
                type="button"
                onClick={() => { setSearch(''); setSearchResults([]); }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            )}
            {searchResults.length > 0 && (
              <div className="absolute right-0 top-full mt-1 z-50 max-h-72 w-[300px] overflow-auto rounded-lg border border-border/50 bg-popover/98 p-1 shadow-xl backdrop-blur-md">
                {searchResults.map((result) => (
                  <button
                    key={`${result.type}:${result.code}`}
                    type="button"
                    onClick={() => chooseSearch(result)}
                    className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left hover:bg-muted/70 text-xs"
                  >
                    <NodeIcon type={result.type} />
                    <span className="min-w-0 flex-1 truncate font-medium">{result.label}</span>
                    <Badge variant="outline" className="text-[9px] uppercase">{result.type}</Badge>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Month picker */}
          <div className="hidden lg:flex items-center gap-1 rounded-md border border-border/50 bg-muted/20 px-2 h-8 text-[11px] text-muted-foreground">
            <span>Month:</span>
            <input
              type="month"
              value={month}
              onChange={(event) => changeMonth(event.target.value)}
              className="bg-transparent text-xs font-medium text-foreground outline-none cursor-pointer"
            />
            {month && (
              <button type="button" onClick={() => changeMonth('')} title="Clear month" className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          {/* Metric weighting segmented toggle */}
          <div className="hidden sm:flex items-center rounded-md border border-border/50 bg-muted/20 p-0.5 h-8">
            {(['borrowers', 'outstanding', 'accounts'] as WeightBy[]).map((weight) => (
              <button
                key={weight}
                type="button"
                disabled={weight === 'borrowers' && (data?.level === 'agent' || data?.level === 'customer')}
                onClick={() => changeWeight(weight)}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-35 ${
                  weightBy === weight
                    ? 'bg-background text-foreground shadow-xs font-semibold'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                title={weight === 'borrowers' && (data?.level === 'agent' || data?.level === 'customer') ? 'Every child represents one customer; use outstanding or accounts.' : undefined}
              >
                {weight === 'borrowers' ? 'Customers' : weight === 'outstanding' ? 'Outstanding' : 'Loans'}
              </button>
            ))}
          </div>

          {/* View mode toggle */}
          <div className="flex items-center rounded-md border border-border/50 bg-muted/20 p-0.5 h-8">
            <button
              type="button"
              onClick={() => setDisplayMode('graph')}
              className={`p-1 rounded transition-colors ${displayMode === 'graph' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'}`}
              title="Force-directed Graph"
            >
              <Network className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setDisplayMode('cards')}
              className={`p-1 rounded transition-colors ${displayMode === 'cards' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'}`}
              title="Ranked List"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setDisplayMode('table')}
              className={`p-1 rounded transition-colors ${displayMode === 'table' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'}`}
              title="Data Table"
            >
              <Table2 className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Quick action buttons */}
          <div className="flex items-center gap-0.5 pl-1.5 border-l border-border/40">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => void loadGraph(selection, data?.offset || 0, weightBy, month, true)}
              disabled={loading}
              title="Refresh graph"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className={`h-8 w-8 ${showInspector ? 'text-foreground bg-muted/50' : 'text-muted-foreground hover:text-foreground'}`}
              onClick={() => setShowInspector(!showInspector)}
              title={showInspector ? "Hide Inspector" : "Show Inspector"}
            >
              {showInspector ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
            </Button>

            {!contained && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={() => setExpanded((value) => !value)}
                title={expanded ? "Exit Fullscreen" : "Fullscreen"}
              >
                {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* ── 2. Error Display (if any) ── */}
      {error && (
        <div className="m-3 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ── 3. Main Workspace Area (Center Canvas + Docked Right Inspector) ── */}
      {!error && (
        <div className="flex-1 min-h-0 flex overflow-hidden relative">
          {/* Main Visual Workspace */}
          <main className="flex-1 min-w-0 flex flex-col min-h-0 relative bg-background">
            {loading && (
              <div className="absolute inset-0 z-30 flex items-center justify-center bg-background/50 backdrop-blur-[1px]">
                <RefreshCw className="h-5 w-5 animate-spin text-primary" />
              </div>
            )}

            {displayMode === 'graph' ? (
              <div ref={canvasRef} className="relative flex-1 min-h-0 overflow-hidden">
                {/* Minimal Top-Left Legend: Clean horizontal tags */}
                <div className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-2 rounded-md border border-border/40 bg-background/80 px-2.5 py-1 backdrop-blur-md text-[10px]">
                  <span className="font-semibold uppercase tracking-wider text-muted-foreground">Legend:</span>
                  {[...new Set([data?.current.type || 'portfolio', ...children.map((n) => n.type)])].map((type) => (
                    <div key={type} className="flex items-center gap-1 shrink-0">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: getNodeColor(type, isDark) }}
                      />
                      <span className="text-foreground/80 font-medium">{levelLabel[type]}</span>
                    </div>
                  ))}
                </div>

                {/* Minimal Top-Right Zoom Controls */}
                <div className="absolute right-3 top-3 z-10 flex items-center gap-0.5 rounded-md border border-border/40 bg-background/80 p-0.5 backdrop-blur-md">
                  <Button variant="ghost" size="icon" onClick={() => zoomBy(1.3)} title="Zoom in" className="h-6 w-6 p-0 rounded">
                    <ZoomIn className="h-3 w-3" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => zoomBy(1 / 1.3)} title="Zoom out" className="h-6 w-6 p-0 rounded">
                    <ZoomOut className="h-3 w-3" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => graphRef.current?.zoomToFit(400, 70)} title="Fit to view" className="h-6 w-6 p-0 rounded">
                    <RotateCcw className="h-3 w-3" />
                  </Button>
                </div>

                {/* ForceGraph2D Canvas */}
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
                    warmupTicks={60}
                    cooldownTicks={80}
                    cooldownTime={2500}
                    d3AlphaDecay={0.04}
                    d3VelocityDecay={0.3}
                    onEngineStop={fitOnce}
                  />
                )}

                {!loading && forceGraphData.nodes.length === 0 && (
                  <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
                    <Network className="mb-2 h-7 w-7 opacity-40" />
                    No governed relationships were found for this selection.
                  </div>
                )}
              </div>
            ) : displayMode === 'cards' ? (
              /* Clean Ranked List View */
              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
                <div className="max-w-4xl mx-auto space-y-3">
                  <div className="flex items-center justify-between py-1 px-1 text-xs text-muted-foreground">
                    <span>Ranked {levelLabel[children[0]?.type || 'product']} entities by {weightBy === 'borrowers' ? 'customer count' : weightBy === 'outstanding' ? 'outstanding volume' : 'loan accounts'}</span>
                    <span className="font-mono">{data?.children_total || 0} total records</span>
                  </div>

                  <div className="divide-y divide-border/30 rounded-lg border border-border/40 overflow-hidden bg-background">
                    {children.map((node) => (
                      <div
                        key={node.id}
                        onClick={() => navigateNode(node)}
                        className={`group flex items-center justify-between p-3 text-left transition-colors hover:bg-muted/40 cursor-pointer text-xs ${
                          selectedNode?.id === node.id ? 'bg-muted/50' : ''
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="font-mono text-[11px] font-semibold text-muted-foreground/70 w-6 text-right shrink-0">
                            #{node.rank || '—'}
                          </span>
                          <span
                            className="h-2 w-2 rounded-full shrink-0"
                            style={{ backgroundColor: getNodeColor(node.type, isDark) }}
                          />
                          <div className="min-w-0 truncate">
                            <div className="truncate font-medium text-foreground group-hover:text-primary transition-colors">
                              {node.label}
                            </div>
                            <div className="font-mono text-[10px] text-muted-foreground flex items-center gap-2 mt-0.5">
                              <span>{node.code}</span>
                              {node.metrics && (
                                <>
                                  <span>·</span>
                                  <span>{formatCount(node.metrics.account_count)} loans</span>
                                  <span>·</span>
                                  <span>{formatMoney(node.metrics.principal_outstanding)}</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 shrink-0 ml-4">
                          {node.is_leader && (
                            <Badge variant="secondary" className="text-[9px] font-medium hidden sm:inline-flex">
                              {weightBy === 'borrowers' ? 'Top Borrowers' : weightBy === 'accounts' ? 'Top Loans' : 'Top Outstanding'}
                            </Badge>
                          )}
                          <span className="font-mono font-semibold text-xs text-foreground">
                            {weightText(node, weightBy)}
                          </span>
                          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-foreground transition-colors" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Clean Table View */
              <div className="flex-1 min-h-0 overflow-auto">
                <table className="w-full min-w-[760px] border-collapse text-left text-xs">
                  <thead className="sticky top-0 bg-muted/80 backdrop-blur-xs text-[10px] uppercase text-muted-foreground border-b border-border/40 z-10">
                    <tr>
                      <th className="p-2.5 font-medium w-14">Rank</th>
                      <th className="p-2.5 font-medium">Name</th>
                      <th className="p-2.5 font-medium">Code</th>
                      <th className="p-2.5 text-right font-medium">Customers</th>
                      <th className="p-2.5 text-right font-medium">Accounts</th>
                      <th className="p-2.5 text-right font-medium">Outstanding</th>
                      <th className="p-2.5 text-right font-medium">Sanctioned</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30">
                    {children.map((node) => (
                      <tr
                        key={node.id}
                        onClick={() => navigateNode(node)}
                        className={`cursor-pointer hover:bg-muted/40 transition-colors ${
                          selectedNode?.id === node.id ? 'bg-muted/50' : ''
                        }`}
                      >
                        <td className="p-2.5 font-mono text-muted-foreground">#{node.rank || '—'}</td>
                        <td className="p-2.5 font-medium text-foreground">{node.label}</td>
                        <td className="p-2.5 font-mono text-muted-foreground">{node.code}</td>
                        <td className="p-2.5 text-right font-mono">{formatCount(node.metrics?.borrower_count)}</td>
                        <td className="p-2.5 text-right font-mono">{formatCount(node.metrics?.account_count || node.account_count)}</td>
                        <td className="p-2.5 text-right font-mono font-medium text-foreground">{formatMoney(node.metrics?.principal_outstanding)}</td>
                        <td className="p-2.5 text-right font-mono">{formatMoney(node.metrics?.sanctioned_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Structured Bottom Status Bar (h-8) */}
            <footer className="shrink-0 h-8 flex items-center justify-between border-t border-border/40 px-3 bg-background/95 text-[11px] text-muted-foreground select-none">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground">{levelLabel[data?.level || 'portfolio']} Tier</span>
                <span>·</span>
                <span>{data?.children_total || 0} records</span>
                <span>·</span>
                <span className="hidden md:inline text-muted-foreground/70">Snapshot: {data?.coverage.snapshot_date || 'Latest'}</span>
              </div>

              <div className="flex items-center gap-3">
                <span className="hidden xl:inline text-muted-foreground/60">
                  {displayMode === 'graph' ? 'Click node to inspect/drill · Scroll to zoom' : 'Click row to inspect'}
                </span>
                {(data?.children_total || 0) > PAGE_SIZE && (
                  <div className="flex items-center gap-1 pl-2 border-l border-border/40">
                    <span className="font-mono text-[10px]">{data?.offset ? `${pageStart}–${pageEnd}` : pageEnd} of {data?.children_total}</span>
                    <button
                      type="button"
                      onClick={() => void loadGraph(selection, Math.max(0, (data?.offset || 0) - PAGE_SIZE))}
                      disabled={(data?.offset || 0) === 0 || loading}
                      className="p-1 rounded hover:bg-muted disabled:opacity-30"
                      title="Previous page"
                    >
                      <ChevronLeft className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void loadGraph(selection, (data?.offset || 0) + PAGE_SIZE)}
                      disabled={pageEnd >= (data?.children_total || 0) || loading}
                      className="p-1 rounded hover:bg-muted disabled:opacity-30"
                      title="Next page"
                    >
                      <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
            </footer>
          </main>

          {/* ── Docked Right Inspector Panel (310px) ── */}
          {showInspector && (
            <aside className="w-[310px] shrink-0 border-l border-border/40 flex flex-col min-h-0 bg-background overflow-hidden">
              {/* Header */}
              <div className="shrink-0 border-b border-border/40 p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: getNodeColor(inspector?.type || 'portfolio', isDark) }}
                    />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                      {levelLabel[inspector?.type || 'portfolio']}
                    </span>
                  </div>
                  {inspector?.code && (
                    <span className="font-mono text-[10px] text-muted-foreground bg-muted/40 px-1.5 py-0.5 rounded">
                      #{inspector.code}
                    </span>
                  )}
                </div>

                <h3 className="mt-1.5 text-sm font-semibold text-foreground leading-snug break-words" title={inspector?.label}>
                  {inspector?.label || 'Loading…'}
                </h3>

                {/* If selected node is a drillable child, offer a direct drill button */}
                {inspector && inspector.id !== data?.current?.id && inspector.type !== 'account' && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2.5 w-full h-7 text-[11px] font-medium justify-between border-border/60 hover:bg-muted/50 shadow-none"
                    onClick={() => navigateNode(inspector)}
                  >
                    <span>Drill down into {levelLabel[inspector.type]}</span>
                    <ChevronRight className="h-3 w-3 text-muted-foreground" />
                  </Button>
                )}
              </div>

              {/* Inspector Body */}
              <div className="flex-1 min-h-0 overflow-y-auto p-3.5 space-y-4 text-xs scrollbar-thin">
                {/* Core KPIs */}
                <div className="space-y-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 block">
                    Portfolio Metrics
                  </span>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
                    <MetricStat
                      label="Outstanding"
                      value={formatMoney(inspectorMetrics.principal_outstanding)}
                      icon={<CircleDollarSign className="h-3.5 w-3.5 text-muted-foreground/70" />}
                    />
                    <MetricStat
                      label="Customers"
                      value={formatCount(inspectorMetrics.borrower_count)}
                      icon={<Users className="h-3.5 w-3.5 text-muted-foreground/70" />}
                    />
                    <MetricStat
                      label="Active Loans"
                      value={formatCount(inspectorMetrics.active_account_count)}
                      icon={<CreditCard className="h-3.5 w-3.5 text-muted-foreground/70" />}
                    />
                    <MetricStat
                      label="Total Overdue"
                      value={formatMoney(inspectorMetrics.total_overdue)}
                      icon={<ShieldAlert className="h-3.5 w-3.5 text-muted-foreground/70" />}
                    />
                    <MetricStat
                      label="PAR 30 Ratio"
                      value={`${Number(inspectorMetrics.par30_ratio || 0).toFixed(2)}%`}
                      icon={<AlertTriangle className="h-3.5 w-3.5 text-muted-foreground/70" />}
                    />
                    <MetricStat
                      label="NPA Ratio"
                      value={`${Number(inspectorMetrics.npa_ratio || 0).toFixed(2)}%`}
                      icon={<ShieldAlert className="h-3.5 w-3.5 text-muted-foreground/70" />}
                    />
                  </div>
                </div>

                {/* Financial Details */}
                <div className="pt-3 border-t border-border/30 space-y-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 block">
                    Financial Summary
                  </span>
                  <div className="space-y-1 divide-y divide-border/20 text-xs">
                    <div className="flex items-center justify-between py-1">
                      <span className="text-muted-foreground">Sanctioned</span>
                      <span className="font-mono font-medium text-foreground">{formatMoney(inspectorMetrics.sanctioned_amount)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1">
                      <span className="text-muted-foreground">Disbursed</span>
                      <span className="font-mono font-medium text-foreground">{formatMoney(inspectorMetrics.disbursed_amount)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1">
                      <span className="text-muted-foreground">Risk Coverage</span>
                      <span className="font-mono font-medium text-foreground">{Number(inspectorMetrics.risk_coverage_pct || 0).toFixed(1)}%</span>
                    </div>
                    {inspector?.type === 'account' && (
                      <>
                        <div className="flex items-center justify-between py-1">
                          <span className="text-muted-foreground">Product</span>
                          <span className="font-medium text-foreground truncate ml-2">{inspector.product_name || inspector.product_code || '—'}</span>
                        </div>
                        <div className="flex items-center justify-between py-1">
                          <span className="text-muted-foreground">Scheme</span>
                          <span className="font-medium text-foreground truncate ml-2">{inspector.scheme_name || inspector.scheme_code || '—'}</span>
                        </div>
                        <div className="flex items-center justify-between py-1">
                          <span className="text-muted-foreground">Agent</span>
                          <span className="font-mono font-medium text-foreground">{inspector.agent_code || '—'}</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Customer 360 CTA */}
                {inspector?.type === 'customer' && (
                  <Button
                    className="w-full text-xs gap-1.5 font-medium shadow-none"
                    size="sm"
                    onClick={() => {
                      setCustomerModalId(inspector.code);
                      setCustomerModalOpen(true);
                    }}
                  >
                    <Users className="h-3.5 w-3.5" />
                    Customer 360 & Ledger
                  </Button>
                )}

                {/* Governance Info */}
                <div className="pt-3 border-t border-border/30 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 block mb-1">
                    Governance
                  </span>
                  <div className="space-y-1">
                    <div>Snapshot: <span className="font-mono font-medium text-foreground">{data?.coverage.snapshot_date || 'Unavailable'}</span></div>
                    <div>Basis: <span className="text-foreground/90">{data?.coverage.effective_branch_basis}</span></div>
                    <p className="text-[10px] text-muted-foreground/70 mt-1">{data?.coverage.branch_basis_note}</p>
                  </div>
                </div>
              </div>
            </aside>
          )}
        </div>
      )}
    </div>
  );

  return (
    <>
      {expanded && mounted && !contained ? createPortal(content, document.body) : content}
      <Customer360Dialog
        customerId={customerModalId}
        open={customerModalOpen}
        onOpenChange={setCustomerModalOpen}
      />
    </>
  );
}

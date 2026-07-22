'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { admin } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useTheme } from 'next-themes';
import dynamic from 'next/dynamic';
import {
  User,
  CreditCard,
  ArrowUpRight,
  ArrowDownLeft,
  Calendar,
  Search,
  X,
  Network,
  Maximize2,
  Minimize2,
  RefreshCw,
  Info,
  Link2
} from 'lucide-react';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[480px] items-center justify-center bg-card/30 rounded-2xl border border-border/50">
      <div className="flex items-center gap-2 text-muted-foreground animate-pulse text-xs">
        <Network className="h-4 w-4 animate-spin text-primary" />
        <span>Loading account instance graph...</span>
      </div>
    </div>
  ),
});

interface GraphNode {
  id: string;
  type: 'account' | 'customer' | 'disbursement' | 'repayment' | 'schedule';
  title: string;
  subtitle?: string;
  node_label: string;
  color: string;
  size: number;
  details: Record<string, string>;
  x?: number;
  y?: number;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
  purpose: string;
}

interface SampleAccountItem {
  account_num: string;
  cust_id: string;
  amount: string;
}

interface InstanceGraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selected_account: string;
  sample_accounts: SampleAccountItem[];
  metadata: {
    is_live: boolean;
    schema: string;
    total_nodes: number;
    total_edges: number;
  };
}

export default function DBSchemaGraph() {
  const { theme } = useTheme();
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<InstanceGraphPayload | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 700, height: 480 });

  const isDark = theme === 'dark';

  const loadGraph = useCallback(async (term?: string) => {
    setLoading(true);
    try {
      const res = await admin.dbSchema(term);
      setData(res);
      if (res && res.nodes && res.nodes.length > 0) {
        const center = res.nodes.find((n: GraphNode) => n.type === 'account') || res.nodes[0];
        setSelectedNode(center);
      }
    } catch (err) {
      console.error('Failed to load instance graph:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width,
          height: isExpanded ? window.innerHeight - 200 : 480,
        });
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();
    const timeout = setTimeout(handleResize, 150);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timeout);
    };
  }, [data, isExpanded]);

  useEffect(() => {
    if (graphRef.current && data && data.nodes.length > 0) {
      setTimeout(() => {
        graphRef.current.zoomToFit(400, 60);
      }, 200);
    }
  }, [data]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      loadGraph(searchQuery.trim());
    }
  };

  const selectSampleAccount = (accNum: string) => {
    setSearchQuery(accNum);
    loadGraph(accNum);
  };

  const linksByNode = useMemo(() => {
    const map = new Map<string, Set<string>>();
    if (!data) return map;

    data.edges.forEach((edge) => {
      const src = typeof edge.source === 'object' ? edge.source.id : edge.source;
      const tgt = typeof edge.target === 'object' ? edge.target.id : edge.target;

      if (!map.has(src)) map.set(src, new Set());
      if (!map.has(tgt)) map.set(tgt, new Set());

      map.get(src)!.add(tgt);
      map.get(tgt)!.add(src);
    });
    return map;
  }, [data]);

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const size = node.size || 16;
      const isSelected = selectedNode?.id === node.id;
      const isHovered = hoverNode?.id === node.id;
      const isNeighborOfSelected = selectedNode
        ? linksByNode.get(selectedNode.id)?.has(node.id) || false
        : false;

      let isDimmed = false;
      if (hoverNode && hoverNode.id !== node.id) {
        const isConnected = linksByNode.get(hoverNode.id)?.has(node.id) || false;
        if (!isConnected) isDimmed = true;
      }

      // Minimal node fill
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size + (isHovered ? 2 : 0), 0, 2 * Math.PI);
      
      let fillColor = isDark ? '#1e293b' : '#334155'; // Clean minimal slate
      if (node.type === 'account') fillColor = isDark ? '#0f172a' : '#1e293b';
      else if (node.type === 'customer') fillColor = isDark ? '#020617' : '#0f172a';
      else if (node.type === 'disbursement') fillColor = isDark ? '#334155' : '#475569';
      else if (node.type === 'repayment') fillColor = isDark ? '#475569' : '#64748b';
      else if (node.type === 'schedule') fillColor = isDark ? '#64748b' : '#94a3b8';

      if (isDimmed) fillColor = isDark ? '#0f172a' : '#e2e8f0';

      ctx.fillStyle = fillColor;
      ctx.fill();

      // Minimal subtle border
      ctx.strokeStyle = isSelected
        ? (isDark ? '#f8fafc' : '#0f172a')
        : isHovered || isNeighborOfSelected
        ? (isDark ? '#94a3b8' : '#475569')
        : (isDark ? '#334155' : '#cbd5e1');
      
      ctx.lineWidth = (isSelected ? 2.5 : 1) / globalScale;
      ctx.stroke();

      // Node Label Text
      const baseFontSize = isHovered || isSelected ? 12 : 10;
      const scaledFontSize = Math.min(baseFontSize / Math.max(globalScale * 0.5, 0.4), baseFontSize * 1.5);
      ctx.font = `${isSelected || isHovered ? '600' : '400'} ${scaledFontSize}px Inter, system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      const textY = node.y! + size + 3;
      ctx.fillStyle = isDimmed ? (isDark ? '#334155' : '#94a3b8') : (isDark ? '#f8fafc' : '#0f172a');
      ctx.fillText(node.title, node.x!, textY);
    },
    [selectedNode, hoverNode, linksByNode, isDark]
  );

  const paintLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const start = link.source;
      const end = link.target;

      if (start.x == null || start.y == null || end.x == null || end.y == null) return;

      let isHighlighted = false;
      let isDimmed = hoverNode !== null;

      if (hoverNode) {
        if (start.id === hoverNode.id || end.id === hoverNode.id) {
          isHighlighted = true;
          isDimmed = false;
        }
      } else if (selectedNode) {
        if (start.id === selectedNode.id || end.id === selectedNode.id) {
          isHighlighted = true;
          isDimmed = false;
        }
      } else {
        isDimmed = false;
      }

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);

      let opacity = isDimmed ? 0.05 : 0.25;
      let strokeColor = isDark ? '148, 163, 184' : '100, 116, 139';
      let lineWidth = 1;

      if (isHighlighted) {
        opacity = 0.8;
        strokeColor = isDark ? '248, 250, 252' : '15, 23, 42';
        lineWidth = 2;
      }

      ctx.strokeStyle = `rgba(${strokeColor}, ${opacity})`;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    },
    [hoverNode, selectedNode, isDark]
  );

  const focusNode = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    if (graphRef.current && node.x != null && node.y != null) {
      graphRef.current.centerAt(node.x, node.y, 600);
      graphRef.current.zoom(2.0, 600);
    }
  }, []);

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'customer':
        return <User className="h-4 w-4 text-primary" />;
      case 'account':
        return <CreditCard className="h-4 w-4 text-primary" />;
      case 'disbursement':
        return <ArrowUpRight className="h-4 w-4 text-muted-foreground" />;
      case 'repayment':
        return <ArrowDownLeft className="h-4 w-4 text-muted-foreground" />;
      case 'schedule':
        return <Calendar className="h-4 w-4 text-muted-foreground" />;
      default:
        return <Info className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <div className={`flex flex-col h-full overflow-hidden ${isExpanded ? 'fixed inset-0 z-50 bg-background p-6' : ''}`}>
      {/* Top Search & Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b pb-4 mb-4 gap-3 shrink-0">
        <div>
          <h2 className="text-base font-headline font-semibold tracking-tight md:text-lg flex items-center gap-2">
            <Network className="h-5 w-5 text-primary" /> Data Curiosity Graph
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Search or select a loan account to visualize real connected borrower profiles, payouts, repayments, and schedules.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2 text-muted-foreground" />
              <Input
                placeholder="Search Account # or Cust ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 text-xs pl-8 w-[200px] md:w-[240px] rounded-xl border-border/80"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    loadGraph();
                  }}
                  className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            <Button type="submit" variant="default" size="sm" disabled={loading} className="h-8 rounded-xl text-xs px-3">
              {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : 'Inspect'}
            </Button>
          </form>

          <Button variant="outline" size="sm" onClick={() => setIsExpanded(p => !p)} className="rounded-xl h-8 w-8 p-0 shrink-0">
            {isExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {/* Sample Accounts Quick Select Pills */}
      {data?.sample_accounts && data.sample_accounts.length > 0 && (
        <div className="flex items-center gap-2 mb-3 overflow-x-auto pb-1 shrink-0">
          <span className="text-[10px] uppercase font-semibold text-muted-foreground shrink-0 tracking-wider">
            Quick Accounts:
          </span>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {data.sample_accounts.map((acc) => {
              const isSelected = data.selected_account === acc.account_num;
              return (
                <button
                  key={acc.account_num}
                  type="button"
                  onClick={() => selectSampleAccount(acc.account_num)}
                  className={`text-[11px] font-mono px-2.5 py-1 rounded-lg border transition-all shrink-0 flex items-center gap-1.5 ${
                    isSelected
                      ? 'border-primary bg-primary/10 text-primary font-semibold'
                      : 'border-border/70 hover:bg-muted/50 text-muted-foreground'
                  }`}
                >
                  <span>#{acc.account_num}</span>
                  <span className="text-[9px] opacity-75">({acc.amount})</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="flex flex-col lg:flex-row gap-4 min-h-0 flex-1">
        {/* Force-directed Link Graph Canvas */}
        <div ref={containerRef} className="flex-1 bg-card/20 rounded-2xl border border-border/70 overflow-hidden relative flex flex-col justify-between">
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1 bg-background/80 backdrop-blur-md border rounded-xl p-2.5 max-w-[200px] pointer-events-none shadow-sm">
            <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">Minimal Node Legend</span>
            <div className="space-y-1 mt-1 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-900 dark:bg-slate-100" />
                <span className="font-medium text-foreground/80">Account Master</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-800 dark:bg-slate-300" />
                <span className="font-medium text-foreground/80">Borrower Profile</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-700 dark:bg-slate-400" />
                <span className="font-medium text-foreground/80">Disbursements</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-600 dark:bg-slate-500" />
                <span className="font-medium text-foreground/80">Repayments</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-500 dark:bg-slate-600" />
                <span className="font-medium text-foreground/80">Amortization Schedule</span>
              </div>
            </div>
          </div>

          {data && (
            <ForceGraph2D
              ref={graphRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={{
                nodes: data.nodes.map(n => ({ ...n })),
                links: data.edges.map(e => ({
                  source: e.source,
                  target: e.target,
                  label: e.label
                }))
              }}
              backgroundColor={isDark ? '#090d16' : '#fafafa'}
              nodeCanvasObject={paintNode}
              linkCanvasObject={paintLink}
              onNodeClick={(node) => focusNode(node as GraphNode)}
              onNodeHover={(node) => setHoverNode(node ? (node as GraphNode) : null)}
              cooldownTicks={100}
              onEngineStop={() => {
                graphRef.current?.zoomToFit(300, 60);
              }}
            />
          )}

          {/* Bottom Active Node Count Bar */}
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-xl border border-border/80 text-[11px]">
            <Badge variant="outline" className="font-mono text-[10px]">
              Account #{data?.selected_account}
            </Badge>
            <span className="text-muted-foreground">• {data?.nodes.length || 0} connected nodes</span>
          </div>
        </div>

        {/* Selected Node Record Inspector Panel */}
        <div className="w-full lg:w-[360px] shrink-0 flex flex-col bg-card rounded-2xl border border-border/70 overflow-hidden">
          {selectedNode ? (
            <div className="flex flex-col h-full min-h-0">
              {/* Record Header */}
              <div className="p-4 border-b shrink-0 bg-muted/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getNodeIcon(selectedNode.type)}
                    <div>
                      <h3 className="font-headline font-semibold text-sm tracking-tight">
                        {selectedNode.title}
                      </h3>
                      {selectedNode.subtitle && (
                        <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                          {selectedNode.subtitle}
                        </p>
                      )}
                    </div>
                  </div>

                  <Badge variant="outline" className="text-[9px] uppercase font-mono px-1.5 py-0.5">
                    {selectedNode.node_label}
                  </Badge>
                </div>
              </div>

              {/* Attributes Key-Value Table */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground block mb-2">
                  Record Attributes & Details
                </span>

                {Object.entries(selectedNode.details).map(([key, val]) => (
                  <div key={key} className="p-2.5 rounded-xl border border-border/60 bg-muted/30 flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground font-medium">{key}</span>
                    <span className="font-mono font-semibold text-foreground">{val}</span>
                  </div>
                ))}
              </div>

              {/* Linked Connections Helper */}
              <div className="p-3 bg-muted/40 border-t shrink-0">
                <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground block mb-1">
                  Graph Relational Paths
                </span>
                <div className="space-y-1">
                  {data?.edges
                    .filter((e) => {
                      const src = typeof e.source === 'object' ? e.source.id : e.source;
                      const tgt = typeof e.target === 'object' ? e.target.id : e.target;
                      return src === selectedNode.id || tgt === selectedNode.id;
                    })
                    .map((edge, i) => {
                      const src = typeof edge.source === 'object' ? edge.source.title : edge.source;
                      const tgt = typeof edge.target === 'object' ? edge.target.title : edge.target;
                      return (
                        <div key={i} className="text-[10px] p-2 bg-card rounded-lg border border-border/80 flex items-center justify-between">
                          <span className="font-medium text-foreground/80 flex items-center gap-1">
                            <Link2 className="h-2.5 w-2.5 text-primary" /> {src} ⇄ {tgt}
                          </span>
                          <span className="font-mono text-[9px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                            {edge.label}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full p-6 text-muted-foreground text-center">
              <Network className="h-6 w-6 stroke-1 animate-pulse mb-2 text-muted-foreground/60" />
              <p className="text-xs">Click any node in the curiosity graph to inspect its record details.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

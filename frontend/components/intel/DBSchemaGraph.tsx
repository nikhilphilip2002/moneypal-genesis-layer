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
  Link2,
  Building2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Move
} from 'lucide-react';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[520px] items-center justify-center bg-card/30 rounded-2xl border border-border/50">
      <div className="flex items-center gap-2 text-muted-foreground animate-pulse text-xs">
        <Network className="h-4 w-4 animate-spin text-primary" />
        <span>Loading expanded graph engine...</span>
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
  weight?: number;
}

interface SampleAccountItem {
  account_num: string;
  cust_id: string;
  cust_name: string;
  amount: string;
}

interface InstanceGraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selected_account: string;
  customer_name?: string;
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
  const [dimensions, setDimensions] = useState({ width: 800, height: 520 });

  const isDark = theme === 'dark';

  const loadGraph = useCallback(async (term?: string) => {
    setLoading(true);
    try {
      const res = await admin.dbSchema(term);
      setData(res);
      if (res && res.nodes && res.nodes.length > 0) {
        const custNode = res.nodes.find((n: GraphNode) => n.type === 'customer') || res.nodes[0];
        setSelectedNode(custNode);
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

  // Dynamic dimension calculation for full screen expansion
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width,
          height: isExpanded ? Math.max(650, window.innerHeight - 180) : 520,
        });
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();
    const timeout = setTimeout(handleResize, 100);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timeout);
    };
  }, [data, isExpanded]);

  // Apply strong repulsion & link distance physics so nodes spread out legibly
  const forceGraphData = useMemo(() => {
    return data
      ? {
          nodes: data.nodes.map((n) => ({ ...n, id: n.id })),
          links: data.edges.map((e) => ({
            source: typeof e.source === 'object' ? e.source.id : e.source,
            target: typeof e.target === 'object' ? e.target.id : e.target,
            label: e.label,
            purpose: e.purpose
          })),
        }
      : { nodes: [], links: [] };
  }, [data]);

  useEffect(() => {
    if (!graphRef.current || forceGraphData.nodes.length === 0) return;

    const timer = setTimeout(() => {
      // Strong repulsion to prevent congestion
      const chargeForce = graphRef.current.d3Force('charge');
      if (chargeForce?.strength) {
        chargeForce.strength(-650);
      }

      // Link distance to spread connected nodes comfortably
      const linkForce = graphRef.current.d3Force('link');
      if (linkForce?.distance) {
        linkForce.distance(160);
      }

      graphRef.current.zoomToFit(500, 90);
    }, 150);

    return () => clearTimeout(timer);
  }, [forceGraphData, dimensions]);

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

  const handleZoomIn = () => {
    if (graphRef.current) {
      graphRef.current.zoom(graphRef.current.zoom() * 1.3, 300);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      graphRef.current.zoom(graphRef.current.zoom() / 1.3, 300);
    }
  };

  const handleResetZoom = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 90);
    }
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

  // High-legibility node rendering with background text pills
  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const size = node.size || 20;
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

      // Outer Selection Ring Glow
      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, size + 6 / globalScale, 0, 2 * Math.PI);
        ctx.fillStyle = isDark ? 'rgba(56, 189, 248, 0.25)' : 'rgba(7, 95, 172, 0.25)';
        ctx.fill();
      }

      // Node Body Circle
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size + (isHovered ? 2 : 0), 0, 2 * Math.PI);
      
      let fillColor = node.color || '#075fac';
      if (isDimmed) fillColor = isDark ? '#1e293b' : '#e2e8f0';

      ctx.fillStyle = fillColor;
      ctx.fill();

      // Border outline
      ctx.strokeStyle = isSelected
        ? (isDark ? '#ffffff' : '#000000')
        : isHovered || isNeighborOfSelected
        ? (isDark ? '#e2e8f0' : '#1e293b')
        : (isDark ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.2)');
      
      ctx.lineWidth = (isSelected ? 3 : isHovered ? 2.5 : 1.5) / globalScale;
      ctx.stroke();

      // Text Label Pill Background for Maximum Legibility
      const titleText = String(node.title || '');
      const baseFontSize = isHovered || isSelected ? 13 : 11;
      const scaledFontSize = Math.min(baseFontSize / Math.max(globalScale * 0.5, 0.35), baseFontSize * 1.5);
      
      ctx.font = `${isSelected || isHovered ? '600' : '500'} ${scaledFontSize}px Inter, system-ui, sans-serif`;
      const textWidth = ctx.measureText(titleText).width;
      const textHeight = scaledFontSize * 1.2;
      const textY = node.y! + size + 5;

      if (!isDimmed) {
        // Draw background pill behind text so it never collides with lines
        ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.88)' : 'rgba(255, 255, 255, 0.92)';
        const padX = 6;
        const padY = 3;
        ctx.beginPath();
        ctx.roundRect(
          node.x! - textWidth / 2 - padX,
          textY - padY,
          textWidth + padX * 2,
          textHeight + padY * 2,
          4
        );
        ctx.fill();
        ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
        ctx.lineWidth = 1 / globalScale;
        ctx.stroke();

        // Print Text
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = isDark ? '#f8fafc' : '#0f172a';
        ctx.fillText(titleText, node.x!, textY);
      }
    },
    [selectedNode, hoverNode, linksByNode, isDark]
  );

  const paintLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const start = link.source;
      const end = link.target;

      if (!start || !end || start.x == null || start.y == null || end.x == null || end.y == null) return;

      let isConnectedToHover = false;
      let isDimmed = hoverNode !== null;

      if (hoverNode) {
        if (start.id === hoverNode.id || end.id === hoverNode.id) {
          isConnectedToHover = true;
          isDimmed = false;
        }
      } else if (selectedNode) {
        if (start.id === selectedNode.id || end.id === selectedNode.id) {
          isConnectedToHover = true;
          isDimmed = false;
        }
      } else {
        isDimmed = false;
      }

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y); // CORRECT GEOMETRY: end.x, end.y

      let opacity = isDimmed ? 0.08 : 0.45;
      let strokeColor = isDark ? '148, 163, 184' : '100, 116, 139';
      let lineWidth = 1.5;

      if (isConnectedToHover) {
        opacity = 0.95;
        strokeColor = isDark ? '56, 189, 248' : '7, 95, 172';
        lineWidth = 2.5;
      }

      ctx.strokeStyle = `rgba(${strokeColor}, ${opacity})`;
      ctx.lineWidth = lineWidth;
      ctx.stroke();

      // Draw connection edge label
      if ((globalScale > 0.75 || isConnectedToHover) && !isDimmed) {
        const midX = (start.x + end.x) / 2;
        const midY = (start.y + end.y) / 2;
        const labelText = String(link.label || '');
        ctx.font = `500 ${Math.max(8, 10 / Math.max(globalScale, 0.6))}px Inter, sans-serif`;
        
        ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.85)' : 'rgba(241, 245, 249, 0.9)';
        const lWidth = ctx.measureText(labelText).width;
        ctx.fillRect(midX - lWidth / 2 - 3, midY - 6, lWidth + 6, 12);

        ctx.fillStyle = isDark ? '#cbd5e1' : '#334155';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, midX, midY);
      }
    },
    [hoverNode, selectedNode, isDark]
  );

  const drawNodePointerArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    const size = (node.size || 20) + 12;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
    ctx.fill();
  }, []);

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
        return <Building2 className="h-4 w-4 text-sky-500" />;
      case 'account':
        return <CreditCard className="h-4 w-4 text-primary" />;
      case 'disbursement':
        return <ArrowUpRight className="h-4 w-4 text-orange-500" />;
      case 'repayment':
        return <ArrowDownLeft className="h-4 w-4 text-teal-500" />;
      case 'schedule':
        return <Calendar className="h-4 w-4 text-purple-500" />;
      default:
        return <Info className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <div className={`flex flex-col h-full overflow-hidden ${isExpanded ? 'fixed inset-0 z-50 bg-background p-6' : ''}`}>
      {/* Top Header & Search Control Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b pb-4 mb-4 gap-3 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-headline font-semibold tracking-tight md:text-lg flex items-center gap-2">
              <Network className="h-5 w-5 text-primary" /> Data Curiosity Graph
            </h2>
            {data?.customer_name && (
              <Badge variant="outline" className="text-xs border-primary/30 bg-primary/5 text-primary font-semibold">
                Borrower: {data.customer_name}
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Interactive, movable entity network. Drag nodes to reposition, scroll to zoom, or search customer accounts.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
              <Input
                placeholder="Search Customer Name or Account #..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 text-xs pl-8 w-[220px] md:w-[260px] rounded-xl border-border/80"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    loadGraph();
                  }}
                  className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            <Button type="submit" variant="default" size="sm" disabled={loading} className="h-8 rounded-xl text-xs px-3">
              {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : 'Inspect'}
            </Button>
          </form>

          <Button
            variant={isExpanded ? "default" : "outline"}
            size="sm"
            onClick={() => setIsExpanded(p => !p)}
            className="rounded-xl h-8 text-xs px-3 shrink-0 flex items-center gap-1.5"
          >
            {isExpanded ? (
              <>
                <Minimize2 className="h-3.5 w-3.5" /> Exit Full Screen
              </>
            ) : (
              <>
                <Maximize2 className="h-3.5 w-3.5" /> Expand Canvas
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Quick Select Sample Accounts Pills */}
      {data?.sample_accounts && data.sample_accounts.length > 0 && (
        <div className="flex items-center gap-2 mb-3 overflow-x-auto pb-1 shrink-0">
          <span className="text-[10px] uppercase font-semibold text-muted-foreground shrink-0 tracking-wider">
            Quick Select Borrower:
          </span>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {data.sample_accounts.map((acc) => {
              const isSelected = data.selected_account === acc.account_num;
              return (
                <button
                  key={acc.account_num}
                  type="button"
                  onClick={() => selectSampleAccount(acc.account_num)}
                  className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all shrink-0 flex items-center gap-1.5 ${
                    isSelected
                      ? 'border-primary bg-primary/10 text-primary font-semibold'
                      : 'border-border/70 hover:bg-muted/50 text-muted-foreground'
                  }`}
                >
                  <span className="font-medium">{acc.cust_name}</span>
                  <span className="font-mono text-[9px] opacity-75">(#{acc.account_num})</span>
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
          {/* Top Left Legend */}
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1 bg-background/85 backdrop-blur-md border rounded-xl p-2.5 max-w-[210px] pointer-events-none shadow-sm">
            <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground flex items-center gap-1">
              <Move className="h-2.5 w-2.5" /> Drag & Click Nodes
            </span>
            <div className="space-y-1 mt-1 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#0284c7' }} />
                <span className="font-medium text-foreground/80">Customer / Borrower</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#075fac' }} />
                <span className="font-medium text-foreground/80">Master Loan Account</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#ea580c' }} />
                <span className="font-medium text-foreground/80">Disbursement Payout</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#0f766e' }} />
                <span className="font-medium text-foreground/80">Repayment Credit</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#7c3aed' }} />
                <span className="font-medium text-foreground/80">Amortization Schedule</span>
              </div>
            </div>
          </div>

          {/* Top Right Zoom Controls */}
          <div className="absolute top-3 right-3 z-10 flex items-center gap-1 bg-background/85 backdrop-blur-md border rounded-xl p-1 shadow-sm">
            <Button variant="ghost" size="sm" onClick={handleZoomIn} title="Zoom In" className="h-7 w-7 p-0 rounded-lg">
              <ZoomIn className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleZoomOut} title="Zoom Out" className="h-7 w-7 p-0 rounded-lg">
              <ZoomOut className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleResetZoom} title="Reset View" className="h-7 w-7 p-0 rounded-lg">
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          </div>

          {data && (
            <ForceGraph2D
              ref={graphRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={forceGraphData}
              backgroundColor={isDark ? '#090d16' : '#fafafa'}
              nodeCanvasObject={paintNode}
              linkCanvasObject={paintLink}
              onNodeClick={(node) => focusNode(node as GraphNode)}
              onNodeHover={(node) => setHoverNode(node ? (node as GraphNode) : null)}
              enableNodeDrag={true}
              enableZoomInteraction={true}
              enablePanInteraction={true}
              nodePointerAreaPaint={drawNodePointerArea}
              cooldownTicks={200}
              d3AlphaDecay={0.02}
              d3VelocityDecay={0.2}
              onEngineStop={() => {
                graphRef.current?.zoomToFit(300, 80);
              }}
            />
          )}

          {/* Bottom Active Summary Bar */}
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-background/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-border/80 text-[11px] shadow-sm">
            <Badge variant="outline" className="font-semibold text-[10px]">
              {data?.customer_name}
            </Badge>
            <span className="font-mono text-muted-foreground">• Account #{data?.selected_account}</span>
            <span className="text-muted-foreground">• {data?.nodes.length || 0} moveable nodes</span>
          </div>
        </div>

        {/* Selected Node Record Inspector Panel */}
        <div className="w-full lg:w-[360px] shrink-0 flex flex-col bg-card rounded-2xl border border-border/70 overflow-hidden">
          {selectedNode ? (
            <div className="flex flex-col h-full min-h-0">
              {/* Record Header */}
              <div className="p-4 border-b shrink-0 bg-muted/20" style={{ borderTop: `4px solid ${selectedNode.color}` }}>
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
                  Relational Join Paths ({data?.edges.filter(e => {
                    const src = typeof e.source === 'object' ? e.source.id : e.source;
                    const tgt = typeof e.target === 'object' ? e.target.id : e.target;
                    return src === selectedNode.id || tgt === selectedNode.id;
                  }).length})
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
              <p className="text-xs">Click any node in the graph to inspect record attributes and relational paths.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

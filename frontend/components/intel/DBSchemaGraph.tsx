'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { admin } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useTheme } from 'next-themes';
import dynamic from 'next/dynamic';
import {
  Database,
  Network,
  X,
  Layers,
  Link2,
  Maximize2,
  Minimize2,
  RefreshCw,
  Search,
  Key,
  Info
} from 'lucide-react';

// Dynamically import ForceGraph2D to prevent Next.js SSR canvas crashes
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[450px] items-center justify-center bg-card/30 rounded-2xl border border-border/50">
      <div className="flex items-center gap-2 text-muted-foreground animate-pulse">
        <Network className="h-5 w-5 animate-spin" />
        <span>Loading schema graph engine...</span>
      </div>
    </div>
  ),
});

interface DBColumn {
  name: string;
  type: string;
  meaning: string;
  required: boolean;
  is_pk: boolean;
  is_fk: boolean;
}

interface DBNode {
  id: string;
  name: string;
  title: string;
  label: string;
  purpose: string;
  color: string;
  row_count: number;
  columns: DBColumn[];
  x?: number;
  y?: number;
}

interface DBEdge {
  source: string | DBNode;
  target: string | DBNode;
  source_col: string;
  target_col: string;
  label: string;
  purpose: string;
  weight: number;
}

interface GraphPayload {
  nodes: DBNode[];
  edges: DBEdge[];
  curiosity_score: number;
  metadata: {
    is_live: boolean;
    schema: string;
    total_tables: number;
    total_relations: number;
    total_rows: number;
  };
}

const getNodeRadius = (node: any): number => {
  const rowCount = node.row_count || 1;
  return Math.max(14, Math.min(28, Math.log10(rowCount) * 4.5));
};

export default function DBSchemaGraph() {
  const { theme } = useTheme();
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<GraphPayload | null>(null);
  const [selectedNode, setSelectedNode] = useState<DBNode | null>(null);
  const [hoverNode, setHoverNode] = useState<DBNode | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 700, height: 450 });

  const isDark = theme === 'dark';

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await admin.dbSchema();
      setData(res);
      if (res && res.nodes && res.nodes.length > 0) {
        const master = res.nodes.find((n: DBNode) => n.id === 'genlnacnts') || res.nodes[0];
        setSelectedNode(master);
      }
    } catch (err) {
      console.error('Failed to load DB schema graph:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width,
          height: isExpanded ? window.innerHeight - 220 : 450,
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

  const filteredColumns = useMemo(() => {
    if (!selectedNode) return [];
    if (!searchTerm.trim()) return selectedNode.columns;
    const term = searchTerm.toLowerCase().trim();
    return selectedNode.columns.filter(
      (c) => c.name.toLowerCase().includes(term) || c.meaning.toLowerCase().includes(term)
    );
  }, [selectedNode, searchTerm]);

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
      const size = getNodeRadius(node);
      const isSelected = selectedNode?.id === node.id;
      const isHovered = hoverNode?.id === node.id;
      const isNeighborOfSelected = selectedNode
        ? linksByNode.get(selectedNode.id)?.has(node.id) || false
        : false;

      let isDimmed = false;
      let isConnected = false;

      if (hoverNode && hoverNode.id !== node.id) {
        isConnected = linksByNode.get(hoverNode.id)?.has(node.id) || false;
        if (!isConnected) isDimmed = true;
      } else if (selectedNode && selectedNode.id !== node.id) {
        isConnected = isNeighborOfSelected;
      }

      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size + (isHovered ? 2.5 : 0), 0, 2 * Math.PI);
      
      let baseColor = node.color || '#075fac';
      if (isDimmed) {
        baseColor = isDark ? '#1f2937' : '#e5e7eb';
      }
      ctx.fillStyle = baseColor;
      ctx.fill();

      if (isSelected || isHovered || isNeighborOfSelected) {
        ctx.strokeStyle = isDark ? '#ffffff' : '#0f172a';
        ctx.lineWidth = (isSelected ? 2.5 : 1.5) / globalScale;
        ctx.stroke();
      }

      const baseFontSize = isHovered || isSelected ? 13 : 11;
      const scaledFontSize = Math.min(baseFontSize / Math.max(globalScale * 0.5, 0.4), baseFontSize * 1.8);
      ctx.font = `${isHovered || isSelected ? '600' : '500'} ${scaledFontSize}px Inter, system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.8)' : 'rgba(255, 255, 255, 0.85)';
      ctx.shadowColor = isDark ? '#000000' : '#ffffff';
      ctx.shadowBlur = 3;

      const textY = node.y! + size + 3;
      ctx.fillStyle = isDimmed ? (isDark ? '#4b5563' : '#9ca3af') : (isDark ? '#f8fafc' : '#0f172a');
      ctx.fillText(node.title, node.x!, textY);
      
      ctx.shadowBlur = 0;
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
      let strokeColor = isDark ? '203, 213, 225' : '100, 116, 139';
      let lineWidth = 1.5;

      if (isHighlighted) {
        opacity = 0.85;
        strokeColor = isDark ? '96, 165, 250' : '37, 99, 235';
        lineWidth = 2.5;
      }

      ctx.strokeStyle = `rgba(${strokeColor}, ${opacity})`;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    },
    [hoverNode, selectedNode, isDark]
  );

  const focusNode = useCallback((node: DBNode) => {
    setSelectedNode(node);
    if (graphRef.current && node.x != null && node.y != null) {
      graphRef.current.centerAt(node.x, node.y, 600);
      graphRef.current.zoom(2.0, 600);
    }
  }, []);

  const metadata = data?.metadata;

  return (
    <div className={`flex flex-col h-full overflow-hidden ${isExpanded ? 'fixed inset-0 z-50 bg-background p-6' : ''}`}>
      <div className="flex items-center justify-between border-b pb-4 mb-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-headline font-semibold tracking-tight md:text-lg flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" /> Database Curiosity Graph
            </h2>
            {metadata && (
              <Badge variant={metadata.is_live ? "default" : "secondary"} className="h-4 text-[9px] uppercase">
                {metadata.is_live ? "Live PostgreSQL" : "Offline Sandbox"}
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Explore lending entities and logical relationships for GENLNACNTS, LOANREPAY, LOANSCHEDULE, and GENLNDISB.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading} className="rounded-xl h-8 text-xs">
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIsExpanded(p => !p)} className="rounded-xl h-8 w-8 p-0">
            {isExpanded ? (
              <Minimize2 className="h-3 w-3" />
            ) : (
              <Maximize2 className="h-3 w-3" />
            )}
          </Button>
        </div>
      </div>

      {/* KPI Stats */}
      {metadata && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3 shrink-0">
          <div className="p-3 bg-muted/40 rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Total Ledger Rows</span>
            <span className="text-sm font-bold font-mono tracking-tight mt-0.5">{metadata.total_rows.toLocaleString()}</span>
          </div>
          <div className="p-3 bg-muted/40 rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Entities</span>
            <span className="text-sm font-bold tracking-tight mt-0.5">{metadata.total_tables} tables</span>
          </div>
          <div className="p-3 bg-muted/40 rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Logical Joins</span>
            <span className="text-sm font-bold tracking-tight mt-0.5">{metadata.total_relations} paths</span>
          </div>
          <div className="p-3 bg-muted/40 rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">DB Target Schema</span>
            <span className="text-sm font-bold tracking-tight mt-0.5 flex items-center gap-1 text-primary">
              <Layers className="h-3.5 w-3.5" /> {metadata.schema}
            </span>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="flex flex-col lg:flex-row gap-4 min-h-0 flex-1">
        {/* Force-directed Link Graph Canvas */}
        <div ref={containerRef} className="flex-1 bg-card/20 rounded-2xl border border-border/70 overflow-hidden relative flex flex-col justify-between">
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1 bg-background/80 backdrop-blur-md border rounded-xl p-2.5 max-w-[200px] pointer-events-none">
            <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">Legend</span>
            <div className="space-y-1 mt-1 text-[11px]">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: '#075fac' }} />
                <span className="font-medium text-foreground/80">Master Accounts</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: '#0f766e' }} />
                <span className="font-medium text-foreground/80">Actual Repayments</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: '#7c3aed' }} />
                <span className="font-medium text-foreground/80">Amortization Plan</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: '#ea580c' }} />
                <span className="font-medium text-foreground/80">Disbursements</span>
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
                  value: e.weight
                }))
              }}
              backgroundColor={isDark ? '#090d16' : '#fafafa'}
              nodeCanvasObject={paintNode}
              linkCanvasObject={paintLink}
              onNodeClick={(node) => focusNode(node as DBNode)}
              onNodeHover={(node) => setHoverNode(node ? (node as DBNode) : null)}
              cooldownTicks={100}
              onEngineStop={() => {
                graphRef.current?.zoomToFit(300, 60);
              }}
            />
          )}

          <div className="absolute bottom-3 left-3 z-10 flex gap-2">
            {data?.nodes.map((node) => (
              <Button
                key={node.id}
                variant={selectedNode?.id === node.id ? "default" : "outline"}
                size="sm"
                onClick={() => focusNode(node)}
                className="h-7 text-[11px] rounded-lg px-2.5 border-border/80"
              >
                {node.title}
              </Button>
            ))}
          </div>
        </div>

        {/* Column Details Side Panel */}
        <div className="w-full lg:w-[360px] shrink-0 flex flex-col bg-card rounded-2xl border border-border/70 overflow-hidden">
          {selectedNode ? (
            <div className="flex flex-col h-full min-h-0">
              <div className="p-4 border-b shrink-0" style={{ borderTop: `4px solid ${selectedNode.color}` }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-headline font-semibold text-sm tracking-tight flex items-center gap-1.5">
                      {selectedNode.title}
                    </h3>
                    <span className="text-[9px] font-mono uppercase bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                      bronze.{selectedNode.name}
                    </span>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px] rounded-lg px-2 border-primary/20 bg-primary/5 text-primary">
                    {selectedNode.row_count.toLocaleString()} rows
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">
                  {selectedNode.purpose}
                </p>
              </div>

              {/* Column Search Filter */}
              <div className="px-4 py-2 bg-muted/30 border-b flex items-center gap-2 shrink-0">
                <Search className="h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Filter columns..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="h-7 text-xs border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 px-0"
                />
                {searchTerm && (
                  <Button variant="ghost" size="sm" onClick={() => setSearchTerm('')} className="h-5 w-5 p-0">
                    <X className="h-3 w-3" />
                  </Button>
                )}
              </div>

              {/* Columns List Scrollable Area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
                {filteredColumns.length === 0 ? (
                  <div className="text-center py-6 text-xs text-muted-foreground">
                    No columns match search term.
                  </div>
                ) : (
                  filteredColumns.map((col) => (
                    <div
                      key={col.name}
                      className={`p-2 rounded-xl border flex flex-col gap-1 transition-all ${
                        col.is_pk 
                          ? 'border-amber-500/20 bg-amber-500/[0.02]' 
                          : col.is_fk 
                          ? 'border-primary/20 bg-primary/[0.02]' 
                          : 'border-border/50 bg-card'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] font-semibold text-foreground/90">
                          {col.name}
                        </span>
                        <div className="flex items-center gap-1">
                          {col.is_pk && (
                            <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 text-[8px] font-bold px-1 py-0.5 flex items-center gap-0.5 rounded-md">
                              <Key className="h-2 w-2" /> PK
                            </Badge>
                          )}
                          {col.is_fk && (
                            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-[8px] font-bold px-1 py-0.5 flex items-center gap-0.5 rounded-md">
                              <Link2 className="h-2 w-2" /> FK
                            </Badge>
                          )}
                          <span className="font-mono text-[9px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                            {col.type}
                          </span>
                        </div>
                      </div>
                      <div className="text-[10px] text-muted-foreground flex items-start gap-1">
                        <Info className="h-3 w-3 mt-0.5 shrink-0 text-muted-foreground/75" />
                        <span>{col.meaning || 'No description provided.'}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Joins Helper / Bottom walk-through */}
              <div className="p-3 bg-muted/40 border-t shrink-0">
                <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground block mb-1">
                  Active Relationships / Join Conditions
                </span>
                <div className="space-y-1.5">
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
                        <div key={i} className="text-[9px] p-2 bg-card rounded-lg border border-border/80 flex flex-col gap-0.5">
                          <span className="font-semibold text-foreground/80 flex items-center gap-1">
                            <Link2 className="h-2.5 w-2.5 text-primary" /> {src} ⇄ {tgt}
                          </span>
                          <span className="font-mono bg-muted/50 p-1 rounded text-primary mt-0.5 break-all">
                            {edge.label}
                          </span>
                          <span className="text-muted-foreground/90 mt-0.5 italic">
                            {edge.purpose}
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
              <p className="text-xs">Click a table node in the curiosity graph to inspect columns and join conditions.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

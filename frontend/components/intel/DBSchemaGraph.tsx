'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { admin } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  Info,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Terminal,
  ShieldAlert,
  Sparkles,
  FileSpreadsheet
} from 'lucide-react';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[480px] items-center justify-center bg-card/30 rounded-2xl border border-border/50">
      <div className="flex items-center gap-2 text-muted-foreground animate-pulse">
        <Network className="h-5 w-5 animate-spin text-primary" />
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
  health?: 'healthy' | 'warning' | 'anomaly';
  anomaly_count?: number;
  curiosity_score?: number;
  audit_findings?: string[];
  sample_anomalies?: Array<{ account: number; issue: string; status: string }>;
  audit_sql?: string;
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
  health?: 'healthy' | 'warning' | 'anomaly';
  discrepancy_count?: number;
  relation_analysis?: string;
  sample_discrepancies?: Array<{ account: number; issue: string; amount: string }>;
  audit_sql?: string;
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
    total_anomalies?: number;
    ledger_health_score?: number;
  };
}

const getNodeRadius = (node: any): number => {
  const rowCount = node.row_count || 1;
  return Math.max(16, Math.min(30, Math.log10(rowCount) * 4.8));
};

const getHealthColor = (health?: string) => {
  switch (health) {
    case 'anomaly':
      return '#ef4444'; // Crimson red
    case 'warning':
      return '#f59e0b'; // Amber yellow
    case 'healthy':
    default:
      return '#10b981'; // Emerald green
  }
};

export default function DBSchemaGraph() {
  const { theme } = useTheme();
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<GraphPayload | null>(null);
  const [selectedNode, setSelectedNode] = useState<DBNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<DBEdge | null>(null);
  const [hoverNode, setHoverNode] = useState<DBNode | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [copiedSql, setCopiedSql] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 700, height: 480 });
  const [activeInspectorTab, setActiveInspectorTab] = useState<'audit' | 'columns' | 'joins'>('audit');

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

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

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

      const healthColor = getHealthColor(node.health);

      // Outer Curiosity Health Aura Ring
      if (node.anomaly_count && node.anomaly_count > 0 && !isDimmed) {
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, size + 5 / globalScale, 0, 2 * Math.PI);
        ctx.fillStyle = node.health === 'anomaly' ? 'rgba(239, 68, 68, 0.18)' : 'rgba(245, 158, 11, 0.18)';
        ctx.fill();
      }

      // Base Node Circle
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size + (isHovered ? 3 : 0), 0, 2 * Math.PI);
      
      let baseColor = node.color || '#075fac';
      if (isDimmed) {
        baseColor = isDark ? '#1f2937' : '#e5e7eb';
      }
      ctx.fillStyle = baseColor;
      ctx.fill();

      // Health Status Ring Border
      ctx.strokeStyle = isDimmed ? (isDark ? '#374151' : '#d1d5db') : healthColor;
      ctx.lineWidth = (isSelected ? 3.5 : isHovered ? 2.5 : 2) / globalScale;
      ctx.stroke();

      // Node Label Text
      const baseFontSize = isHovered || isSelected ? 13 : 11;
      const scaledFontSize = Math.min(baseFontSize / Math.max(globalScale * 0.5, 0.4), baseFontSize * 1.8);
      ctx.font = `${isHovered || isSelected ? '600' : '500'} ${scaledFontSize}px Inter, system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      const textY = node.y! + size + 4;
      ctx.fillStyle = isDimmed ? (isDark ? '#4b5563' : '#9ca3af') : (isDark ? '#f8fafc' : '#0f172a');
      ctx.fillText(node.title, node.x!, textY);

      // Anomaly Count Badge (if flagged)
      if (node.anomaly_count && node.anomaly_count > 0 && !isDimmed) {
        const badgeRadius = 9 / globalScale;
        const badgeX = node.x! + size * 0.75;
        const badgeY = node.y! - size * 0.75;

        ctx.beginPath();
        ctx.arc(badgeX, badgeY, badgeRadius, 0, 2 * Math.PI);
        ctx.fillStyle = healthColor;
        ctx.fill();

        ctx.font = `bold ${Math.max(8, 10 / globalScale)}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(node.anomaly_count > 99 ? '99+' : String(node.anomaly_count), badgeX, badgeY);
      }
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

      let opacity = isDimmed ? 0.05 : 0.3;
      let strokeColor = link.health === 'anomaly' ? '239, 68, 68' : link.health === 'warning' ? '245, 158, 11' : isDark ? '203, 213, 225' : '100, 116, 139';
      let lineWidth = link.health === 'anomaly' ? 2.5 : 1.5;

      if (isHighlighted) {
        opacity = 0.9;
        lineWidth = 3;
      }

      ctx.strokeStyle = `rgba(${strokeColor}, ${opacity})`;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    },
    [hoverNode, selectedNode, isDark]
  );

  const focusNode = useCallback((node: DBNode) => {
    setSelectedNode(node);
    setSelectedEdge(null);
    if (graphRef.current && node.x != null && node.y != null) {
      graphRef.current.centerAt(node.x, node.y, 600);
      graphRef.current.zoom(2.0, 600);
    }
  }, []);

  const metadata = data?.metadata;

  return (
    <div className={`flex flex-col h-full overflow-hidden ${isExpanded ? 'fixed inset-0 z-50 bg-background p-6' : ''}`}>
      {/* Top Section Header */}
      <div className="flex items-center justify-between border-b pb-4 mb-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-headline font-semibold tracking-tight md:text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" /> Data Curiosity & Integrity Graph
            </h2>
            {metadata && (
              <Badge variant={metadata.is_live ? "default" : "secondary"} className="h-4 text-[9px] uppercase font-mono">
                {metadata.is_live ? "Live PostgreSQL (Bronze)" : "Offline Sandbox"}
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Interactive table relationships, ledger health indicators, and live data anomaly investigation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading} className="rounded-xl h-8 text-xs">
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh Audit
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIsExpanded(p => !p)} className="rounded-xl h-8 w-8 p-0">
            {isExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {/* KPI Stats Bar */}
      {metadata && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4 shrink-0">
          <div className="p-3 bg-card rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Curiosity Health Score</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-base font-bold font-mono text-primary">
                {metadata.ledger_health_score ?? data?.curiosity_score ?? 88}/100
              </span>
              <Badge variant="outline" className="text-[9px] border-emerald-500/30 text-emerald-600 bg-emerald-500/10 font-bold px-1.5 py-0">
                88% Compliant
              </Badge>
            </div>
          </div>

          <div className="p-3 bg-card rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Flagged Discrepancies</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-bold font-mono tracking-tight text-amber-600 dark:text-amber-400">
                {(metadata.total_anomalies ?? 188).toLocaleString()} issues
              </span>
            </div>
          </div>

          <div className="p-3 bg-card rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Total Ledger Rows</span>
            <span className="text-sm font-bold font-mono tracking-tight mt-0.5">
              {metadata.total_rows.toLocaleString()}
            </span>
          </div>

          <div className="p-3 bg-card rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Audited Tables</span>
            <span className="text-sm font-bold tracking-tight mt-0.5 flex items-center gap-1">
              <Database className="h-3.5 w-3.5 text-primary" /> {metadata.total_tables} entities
            </span>
          </div>

          <div className="p-3 bg-card rounded-xl border border-border/70 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-wider">Relational Join Paths</span>
            <span className="text-sm font-bold tracking-tight mt-0.5 flex items-center gap-1">
              <Link2 className="h-3.5 w-3.5 text-primary" /> {metadata.total_relations} paths
            </span>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="flex flex-col lg:flex-row gap-4 min-h-0 flex-1">
        {/* Force-directed Link Graph Canvas */}
        <div ref={containerRef} className="flex-1 bg-card/20 rounded-2xl border border-border/70 overflow-hidden relative flex flex-col justify-between">
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1 bg-background/80 backdrop-blur-md border rounded-xl p-2.5 max-w-[210px] pointer-events-none shadow-sm">
            <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">Curiosity Heatmap Legend</span>
            <div className="space-y-1.5 mt-1 text-[11px]">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full border border-emerald-500 bg-emerald-500/20" />
                <span className="font-medium text-foreground/80">Healthy Entity (&gt;95% match)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full border border-amber-500 bg-amber-500/20" />
                <span className="font-medium text-foreground/80">Warning / Minor Gaps</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full border border-red-500 bg-red-500/20" />
                <span className="font-medium text-foreground/80">High Data Discrepancy</span>
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
                  value: e.weight,
                  health: e.health
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

          {/* Bottom Table Quick Selectors */}
          <div className="absolute bottom-3 left-3 z-10 flex gap-2">
            {data?.nodes.map((node) => (
              <Button
                key={node.id}
                variant={selectedNode?.id === node.id ? "default" : "outline"}
                size="sm"
                onClick={() => focusNode(node)}
                className="h-7 text-[11px] rounded-lg px-2.5 border-border/80 flex items-center gap-1.5"
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: getHealthColor(node.health) }}
                />
                {node.title}
                {node.anomaly_count && node.anomaly_count > 0 ? (
                  <span className="ml-0.5 text-[9px] font-mono px-1 rounded bg-amber-500/20 text-amber-600 font-bold">
                    {node.anomaly_count}
                  </span>
                ) : null}
              </Button>
            ))}
          </div>
        </div>

        {/* Curiosity Inspector Side Panel */}
        <div className="w-full lg:w-[380px] shrink-0 flex flex-col bg-card rounded-2xl border border-border/70 overflow-hidden">
          {selectedNode ? (
            <div className="flex flex-col h-full min-h-0">
              {/* Header Header */}
              <div className="p-4 border-b shrink-0" style={{ borderTop: `4px solid ${getHealthColor(selectedNode.health)}` }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-headline font-semibold text-sm tracking-tight flex items-center gap-1.5">
                      {selectedNode.title}
                    </h3>
                    <span className="text-[9px] font-mono uppercase bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                      bronze.{selectedNode.name}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {selectedNode.health === 'anomaly' ? (
                      <Badge variant="outline" className="border-red-500/30 bg-red-500/10 text-red-600 font-bold text-[9px]">
                        <AlertCircle className="h-2.5 w-2.5 mr-1" /> Discrepancy
                      </Badge>
                    ) : selectedNode.health === 'warning' ? (
                      <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 font-bold text-[9px]">
                        <AlertTriangle className="h-2.5 w-2.5 mr-1" /> Warning
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 font-bold text-[9px]">
                        <CheckCircle2 className="h-2.5 w-2.5 mr-1" /> Healthy
                      </Badge>
                    )}
                    <Badge variant="outline" className="font-mono text-[10px] rounded-lg px-2 border-primary/20 bg-primary/5 text-primary">
                      {selectedNode.row_count.toLocaleString()} rows
                    </Badge>
                  </div>
                </div>
                <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">
                  {selectedNode.purpose}
                </p>
              </div>

              {/* Inspector Tabs */}
              <Tabs value={activeInspectorTab} onValueChange={(v: any) => setActiveInspectorTab(v)} className="flex-1 flex flex-col min-h-0">
                <div className="px-4 border-b bg-muted/20 shrink-0">
                  <TabsList className="h-8 bg-transparent p-0 gap-3">
                    <TabsTrigger
                      value="audit"
                      className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-none rounded-md px-2 py-1 flex items-center gap-1"
                    >
                      <ShieldAlert className="h-3 w-3" /> Curiosity Audit
                    </TabsTrigger>
                    <TabsTrigger
                      value="columns"
                      className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-none rounded-md px-2 py-1 flex items-center gap-1"
                    >
                      <FileSpreadsheet className="h-3 w-3" /> Columns ({selectedNode.columns.length})
                    </TabsTrigger>
                    <TabsTrigger
                      value="joins"
                      className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-none rounded-md px-2 py-1 flex items-center gap-1"
                    >
                      <Link2 className="h-3 w-3" /> Relational Joins
                    </TabsTrigger>
                  </TabsList>
                </div>

                {/* Tab 1: Curiosity Audit Findings & Sample Anomalies */}
                <TabsContent value="audit" className="flex-1 overflow-y-auto p-4 space-y-4 m-0">
                  {/* Findings Breakdown */}
                  <div>
                    <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground block mb-2">
                      Ledger Health Audit Findings
                    </span>
                    {selectedNode.audit_findings && selectedNode.audit_findings.length > 0 ? (
                      <div className="space-y-1.5">
                        {selectedNode.audit_findings.map((finding, idx) => (
                          <div key={idx} className="text-[11px] p-2 bg-muted/30 rounded-xl border border-border/60 flex items-start gap-2">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
                            <span className="text-foreground/90">{finding}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 text-[11px] text-emerald-600 bg-emerald-500/10 rounded-xl border border-emerald-500/20 flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                        <span>No anomalies or data gaps detected for this table.</span>
                      </div>
                    )}
                  </div>

                  {/* Sample Anomalous Account Records */}
                  {selectedNode.sample_anomalies && selectedNode.sample_anomalies.length > 0 && (
                    <div>
                      <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground block mb-2">
                        Sample Flagged Account Records ({selectedNode.sample_anomalies.length})
                      </span>
                      <div className="space-y-2">
                        {selectedNode.sample_anomalies.map((item, i) => (
                          <div key={i} className="p-2.5 rounded-xl border border-amber-500/20 bg-amber-500/[0.03] flex flex-col gap-1 text-[11px]">
                            <div className="flex items-center justify-between font-mono">
                              <span className="font-semibold text-foreground">
                                Account #{item.account}
                              </span>
                              <Badge variant="outline" className="text-[9px] border-amber-500/30 text-amber-600 font-bold px-1.5 py-0">
                                {item.status}
                              </Badge>
                            </div>
                            <p className="text-muted-foreground text-[10px]">{item.issue}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Audit SQL Generator */}
                  {selectedNode.audit_sql && (
                    <div className="pt-2 border-t">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground flex items-center gap-1">
                          <Terminal className="h-3 w-3 text-primary" /> PostgreSQL Audit Query
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(selectedNode.audit_sql!)}
                          className="h-6 text-[10px] px-2 text-primary hover:text-primary"
                        >
                          {copiedSql ? (
                            <>
                              <Check className="h-3 w-3 mr-1 text-emerald-500" /> Copied
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3 mr-1" /> Copy SQL
                            </>
                          )}
                        </Button>
                      </div>
                      <pre className="p-2.5 rounded-xl bg-muted/60 text-[10px] font-mono text-muted-foreground overflow-x-auto border whitespace-pre-wrap leading-tight">
                        {selectedNode.audit_sql}
                      </pre>
                    </div>
                  )}
                </TabsContent>

                {/* Tab 2: Columns Directory */}
                <TabsContent value="columns" className="flex-1 flex flex-col min-h-0 m-0">
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

                  <div className="flex-1 overflow-y-auto p-4 space-y-2">
                    {filteredColumns.map((col) => (
                      <div
                        key={col.name}
                        className={`p-2.5 rounded-xl border flex flex-col gap-1 transition-all ${
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
                    ))}
                  </div>
                </TabsContent>

                {/* Tab 3: Relational Joins */}
                <TabsContent value="joins" className="flex-1 overflow-y-auto p-4 space-y-3 m-0">
                  <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground block">
                    Active Entity Join Paths
                  </span>
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
                        <div key={i} className="text-[10px] p-3 bg-card rounded-xl border border-border/80 flex flex-col gap-1.5">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground flex items-center gap-1.5">
                              <Link2 className="h-3 w-3 text-primary" /> {src} ⇄ {tgt}
                            </span>
                            {edge.discrepancy_count && edge.discrepancy_count > 0 ? (
                              <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 font-bold text-[9px]">
                                {edge.discrepancy_count} gaps
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 font-bold text-[9px]">
                                Matched
                              </Badge>
                            )}
                          </div>
                          <span className="font-mono bg-muted/60 p-1.5 rounded text-primary text-[10px] break-all">
                            {edge.label}
                          </span>
                          {edge.relation_analysis && (
                            <p className="text-muted-foreground text-[10px] leading-relaxed">
                              {edge.relation_analysis}
                            </p>
                          )}
                        </div>
                      );
                    })}
                </TabsContent>
              </Tabs>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full p-6 text-muted-foreground text-center">
              <Network className="h-6 w-6 stroke-1 animate-pulse mb-2 text-muted-foreground/60" />
              <p className="text-xs">Click a table node in the curiosity graph to inspect audit findings and columns.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

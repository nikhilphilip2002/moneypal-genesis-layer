'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { admin } from '@/lib/api';
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
  Move,
  ChevronRight,
  ShieldCheck,
  UserCheck,
  Award,
  Globe2,
  Building,
  Database,
  TrendingUp,
  DollarSign,
  Users
} from 'lucide-react';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[540px] items-center justify-center bg-card/30 rounded-2xl border border-border/50">
      <div className="flex items-center gap-2 text-muted-foreground animate-pulse text-xs">
        <Network className="h-4 w-4 animate-spin text-primary" />
        <span>Loading Enterprise Curiosity Graph...</span>
      </div>
    </div>
  ),
});

interface GraphNode {
  id: string;
  type: 'executive' | 'zonal' | 'manager' | 'agent' | 'customer' | 'account' | 'disbursement' | 'repayment';
  title: string;
  subtitle?: string;
  node_label: string;
  color: string;
  size: number;
  zonal_id?: string;
  manager_id?: string;
  agent_id?: string;
  customer_id?: string;
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

interface ZonalItem {
  id: string;
  name: string;
  director: string;
  code: string;
}

interface BranchItem {
  id: string;
  code: string;
  name: string;
  display_title: string;
  manager: string;
  cust_count: number;
  acnt_count: number;
  total_vol: number;
  zone_id: string;
}

interface SearchResultItem {
  id: string;
  title: string;
  subtitle: string;
  type: string;
  view_level: 'executive' | 'zonal' | 'manager' | 'agent' | 'customer';
  zonal_id?: string;
  manager_id?: string;
  agent_id?: string;
  customer_id?: string;
}

interface HierarchicalGraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  view_level: 'executive' | 'zonal' | 'manager' | 'agent' | 'customer';
  executive_info: {
    id: string;
    name: string;
    role: string;
    org: string;
  };
  zonals: ZonalItem[];
  selected_zonal?: ZonalItem | null;
  branches: BranchItem[];
  selected_manager?: BranchItem | null;
  selected_agent?: any;
  selected_customer?: any;
  total_database_metrics?: {
    total_customers: number;
    total_accounts: number;
    total_branches: number;
  };
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
  const [data, setData] = useState<HierarchicalGraphPayload | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  
  // Navigation State Across 5 Enterprise Tiers
  const [viewLevel, setViewLevel] = useState<'executive' | 'zonal' | 'manager' | 'agent' | 'customer'>('executive');
  const [selectedZonalId, setSelectedZonalId] = useState<string | null>(null);
  const [selectedManagerId, setSelectedManagerId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  
  // Search & Autocomplete State
  const [searchEntityType, setSearchEntityType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  const [isExpanded, setIsExpanded] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 800, height: 540 });

  const isDark = theme === 'dark';

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const loadGraph = useCallback(async (opts?: {
    level?: 'executive' | 'zonal' | 'manager' | 'agent' | 'customer';
    zonalId?: string;
    managerId?: string;
    agentId?: string;
    custId?: string;
    search?: string;
  }) => {
    setLoading(true);
    try {
      const levelToFetch = opts?.level || viewLevel;
      const zId = opts?.zonalId !== undefined ? opts.zonalId : selectedZonalId;
      const mId = opts?.managerId !== undefined ? opts.managerId : selectedManagerId;
      const agtId = opts?.agentId !== undefined ? opts.agentId : selectedAgentId;
      const cId = opts?.custId !== undefined ? opts.custId : selectedCustomerId;
      const term = opts?.search !== undefined ? opts.search : searchQuery;

      const res = await admin.dbSchema({
        view_level: levelToFetch,
        zonal_id: zId || undefined,
        manager_id: mId || undefined,
        agent_id: agtId || undefined,
        customer_id: cId || undefined,
        search: term || undefined
      });

      setData(res);
      setViewLevel(res.view_level || levelToFetch);

      if (res && res.nodes && res.nodes.length > 0) {
        const primaryNode = res.nodes.find((n: GraphNode) => 
          n.type === 'agent' || n.type === 'customer' || n.type === 'manager' || n.type === 'zonal' || n.type === 'executive'
        ) || res.nodes[0];
        setSelectedNode(primaryNode);
      }
    } catch (err) {
      console.error('Failed to load Enterprise Curiosity Graph:', err);
    } finally {
      setLoading(false);
    }
  }, [viewLevel, selectedZonalId, selectedManagerId, selectedAgentId, selectedCustomerId, searchQuery]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Canvas Dimensions Calculation
  useEffect(() => {
    const handleResize = () => {
      if (isExpanded) {
        setDimensions({
          width: Math.max(600, window.innerWidth - 48),
          height: Math.max(450, window.innerHeight - 170),
        });
      } else if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(400, rect.width),
          height: 540,
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

  // Live Autocomplete Suggestions as user types
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSearchResults([]);
      setIsSearchOpen(false);
      return;
    }

    const timer = setTimeout(() => {
      admin.dbSchemaSearch(searchQuery.trim(), searchEntityType)
        .then((res) => {
          if (res && res.results) {
            setSearchResults(res.results);
            setIsSearchOpen(true);
          }
        })
        .catch(() => setSearchResults([]));
    }, 200);

    return () => clearTimeout(timer);
  }, [searchQuery, searchEntityType]);

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
      const chargeForce = graphRef.current.d3Force('charge');
      if (chargeForce?.strength) {
        chargeForce.strength(-680);
      }
      const linkForce = graphRef.current.d3Force('link');
      if (linkForce?.distance) {
        linkForce.distance(180);
      }
      graphRef.current.zoomToFit(500, 90);
    }, 150);

    return () => clearTimeout(timer);
  }, [forceGraphData, dimensions]);

  // Tier Navigation Handlers
  const navigateToExecutive = () => {
    setViewLevel('executive');
    setSelectedZonalId(null);
    setSelectedManagerId(null);
    setSelectedAgentId(null);
    setSelectedCustomerId(null);
    setSearchQuery('');
    loadGraph({ level: 'executive', zonalId: undefined, managerId: undefined, agentId: undefined, custId: undefined, search: '' });
  };

  const navigateToZonal = (zonalId: string) => {
    setViewLevel('zonal');
    setSelectedZonalId(zonalId);
    setSelectedManagerId(null);
    setSelectedAgentId(null);
    setSelectedCustomerId(null);
    loadGraph({ level: 'zonal', zonalId, managerId: undefined, agentId: undefined, custId: undefined });
  };

  const navigateToManager = (managerId: string) => {
    setViewLevel('manager');
    setSelectedManagerId(managerId);
    setSelectedAgentId(null);
    setSelectedCustomerId(null);
    loadGraph({ level: 'manager', managerId, agentId: undefined, custId: undefined });
  };

  const navigateToAgent = (agentId: string) => {
    setViewLevel('agent');
    setSelectedAgentId(agentId);
    setSelectedCustomerId(null);
    loadGraph({ level: 'agent', agentId, custId: undefined });
  };

  const navigateToCustomer = (custId: string) => {
    setViewLevel('customer');
    setSelectedCustomerId(custId);
    loadGraph({ level: 'customer', custId });
  };

  // EVERY NODE IS 100% CLICKABLE
  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);

    if (node.type === 'zonal' && node.zonal_id) {
      navigateToZonal(node.zonal_id);
    } else if (node.type === 'manager' && node.manager_id) {
      navigateToManager(node.manager_id);
    } else if (node.type === 'agent' && node.agent_id) {
      navigateToAgent(node.agent_id);
    } else if (node.type === 'customer' && node.customer_id) {
      navigateToCustomer(node.customer_id);
    } else if (node.type === 'executive') {
      navigateToExecutive();
    } else if (graphRef.current && node.x != null && node.y != null) {
      graphRef.current.centerAt(node.x, node.y, 500);
      graphRef.current.zoom(2.0, 500);
    }
  };

  const handleSelectSearchResult = (item: SearchResultItem) => {
    setIsSearchOpen(false);
    setSearchQuery('');

    if (item.view_level === 'zonal' && item.zonal_id) {
      navigateToZonal(item.zonal_id);
    } else if (item.view_level === 'manager' && item.manager_id) {
      navigateToManager(item.manager_id);
    } else if (item.view_level === 'agent' && item.agent_id) {
      navigateToAgent(item.agent_id);
    } else if (item.view_level === 'customer' && item.customer_id) {
      navigateToCustomer(item.customer_id);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setIsSearchOpen(false);
      loadGraph({ search: searchQuery.trim() });
    }
  };

  const handleZoomIn = () => {
    if (graphRef.current) graphRef.current.zoom(graphRef.current.zoom() * 1.3, 300);
  };
  const handleZoomOut = () => {
    if (graphRef.current) graphRef.current.zoom(graphRef.current.zoom() / 1.3, 300);
  };
  const handleResetZoom = () => {
    if (graphRef.current) graphRef.current.zoomToFit(400, 90);
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

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, size + 6 / globalScale, 0, 2 * Math.PI);
        ctx.fillStyle = isDark ? 'rgba(124, 58, 237, 0.25)' : 'rgba(79, 70, 229, 0.25)';
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size + (isHovered ? 2 : 0), 0, 2 * Math.PI);
      
      let fillColor = node.color || '#075fac';
      if (isDimmed) fillColor = isDark ? '#1e293b' : '#e2e8f0';

      ctx.fillStyle = fillColor;
      ctx.fill();

      ctx.strokeStyle = isSelected
        ? (isDark ? '#ffffff' : '#000000')
        : isHovered || isNeighborOfSelected
        ? (isDark ? '#e2e8f0' : '#1e293b')
        : (isDark ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.2)');
      
      ctx.lineWidth = (isSelected ? 3 : isHovered ? 2.5 : 1.5) / globalScale;
      ctx.stroke();

      const titleText = String(node.title || '');
      const baseFontSize = isHovered || isSelected ? 13 : 11;
      const scaledFontSize = Math.min(baseFontSize / Math.max(globalScale * 0.5, 0.35), baseFontSize * 1.5);
      
      ctx.font = `${isSelected || isHovered ? '600' : '500'} ${scaledFontSize}px Inter, system-ui, sans-serif`;
      const textWidth = ctx.measureText(titleText).width;
      const textHeight = scaledFontSize * 1.2;
      const textY = node.y! + size + 5;

      if (!isDimmed) {
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
      ctx.lineTo(end.x, end.y);

      let opacity = isDimmed ? 0.08 : 0.45;
      let strokeColor = isDark ? '148, 163, 184' : '100, 116, 139';
      let lineWidth = 1.5;

      if (isConnectedToHover) {
        opacity = 0.95;
        strokeColor = isDark ? '168, 85, 247' : '124, 58, 237';
        lineWidth = 2.5;
      }

      ctx.strokeStyle = `rgba(${strokeColor}, ${opacity})`;
      ctx.lineWidth = lineWidth;
      ctx.stroke();

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
    const size = (node.size || 20) + 16;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
    ctx.fill();

    const titleText = String(node.title || '');
    const labelWidth = Math.max(100, Math.min(260, titleText.length * 9 + 24));
    ctx.fillRect(
      node.x! - labelWidth / 2,
      node.y! + size - 8,
      labelWidth,
      28
    );
  }, []);

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'executive':
        return <Award className="h-4 w-4 text-purple-500" />;
      case 'zonal':
        return <Globe2 className="h-4 w-4 text-violet-500" />;
      case 'manager':
        return <Building className="h-4 w-4 text-indigo-500" />;
      case 'agent':
        return <UserCheck className="h-4 w-4 text-sky-500" />;
      case 'customer':
        return <Building2 className="h-4 w-4 text-teal-500" />;
      case 'account':
        return <CreditCard className="h-4 w-4 text-primary" />;
      case 'disbursement':
        return <ArrowUpRight className="h-4 w-4 text-orange-500" />;
      case 'repayment':
        return <ArrowDownLeft className="h-4 w-4 text-emerald-500" />;
      default:
        return <Info className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const m = data?.total_database_metrics;

  const graphContent = (
    <div className={`flex flex-col ${isExpanded ? 'fixed inset-0 z-[9999] w-screen h-screen bg-background p-6 overflow-hidden' : 'w-full h-full min-h-[580px]'}`}>
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between border-b pb-4 mb-3 gap-3 shrink-0">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-headline font-semibold tracking-tight md:text-lg flex items-center gap-2">
              <Network className="h-5 w-5 text-primary" /> Enterprise Curiosity Graph
            </h2>
            <Badge variant="outline" className="text-xs border-purple-500/30 bg-purple-500/10 text-purple-500 font-semibold uppercase">
              Tier: {viewLevel}
            </Badge>
            {m && (
              <Badge variant="secondary" className="text-xs font-mono font-medium flex items-center gap-1">
                <Database className="h-3 w-3 text-primary" />
                {m.total_customers.toLocaleString()} Borrowers • {m.total_branches} Named Branches
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Querying all 11,347 customers across 16 named branches. Click any Executive, Zone, Branch, Officer, or Borrower node to inspect details on the left.
          </p>
        </div>

        {/* SEARCH WITH ENTITY DROPDOWN & LIVE AUTOCOMPLETE */}
        <div className="flex items-center gap-2 relative flex-wrap">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-1.5 relative">
            <div className="relative">
              <select
                value={searchEntityType}
                onChange={(e) => setSearchEntityType(e.target.value)}
                className="h-8 text-xs px-2 rounded-xl border border-border/80 bg-background text-foreground focus:ring-1 focus:ring-primary cursor-pointer font-medium"
              >
                <option value="all">All Types</option>
                <option value="customer">👤 Customer</option>
                <option value="agent">👔 Officer / Agent</option>
                <option value="manager">🏢 Branch Manager</option>
                <option value="zonal">🌐 Zonal VP</option>
              </select>
            </div>

            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
              <Input
                placeholder="Search name, customer ID, or branch..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  if (searchResults.length > 0) setIsSearchOpen(true);
                }}
                className="h-8 text-xs pl-8 w-[190px] md:w-[260px] rounded-xl border-border/80"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    setIsSearchOpen(false);
                    loadGraph({ search: '' });
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

          {/* Live Autocomplete Dropdown List */}
          {isSearchOpen && searchResults.length > 0 && (
            <div className="absolute top-10 right-[100px] z-50 w-[320px] bg-card rounded-xl border shadow-xl max-h-[300px] overflow-y-auto p-1 text-xs">
              <div className="px-2 py-1 text-[10px] uppercase font-semibold text-muted-foreground border-b flex justify-between">
                <span>Matching Suggestions</span>
                <span>{searchResults.length} items</span>
              </div>
              {searchResults.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleSelectSearchResult(item)}
                  className="w-full text-left p-2 rounded-lg hover:bg-muted/70 flex items-start gap-2 border-b border-border/40 last:border-0"
                >
                  {getNodeIcon(item.type)}
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-foreground truncate">{item.title}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{item.subtitle}</p>
                  </div>
                  <Badge variant="outline" className="text-[9px] uppercase shrink-0">
                    {item.type}
                  </Badge>
                </button>
              ))}
            </div>
          )}

          {/* Full Screen Toggle Button */}
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

      {/* 5-Tier Breadcrumb Navigation Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 bg-muted/40 p-2.5 rounded-xl border shrink-0 text-xs">
        <div className="flex items-center gap-1.5 font-medium overflow-x-auto">
          <button
            onClick={navigateToExecutive}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border transition-all ${
              viewLevel === 'executive'
                ? 'bg-purple-500/15 border-purple-500 text-purple-600 font-semibold dark:text-purple-400'
                : 'border-border/70 hover:bg-muted text-muted-foreground'
            }`}
          >
            <Award className="h-3.5 w-3.5 text-purple-500" />
            MD & CEO: Dr. Vikramaditya Rao
          </button>

          {(viewLevel === 'zonal' || viewLevel === 'manager' || viewLevel === 'agent' || viewLevel === 'customer') && data?.selected_zonal && (
            <>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <button
                onClick={() => navigateToZonal(data.selected_zonal!.id)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border transition-all ${
                  viewLevel === 'zonal'
                    ? 'bg-violet-500/15 border-violet-500 text-violet-600 font-semibold dark:text-violet-400'
                    : 'border-border/70 hover:bg-muted text-muted-foreground'
                }`}
              >
                <Globe2 className="h-3.5 w-3.5 text-violet-500" />
                Zone: {data.selected_zonal.name}
              </button>
            </>
          )}

          {(viewLevel === 'manager' || viewLevel === 'agent' || viewLevel === 'customer') && data?.selected_manager && (
            <>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <button
                onClick={() => navigateToManager(data.selected_manager!.id)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border transition-all ${
                  viewLevel === 'manager'
                    ? 'bg-indigo-500/15 border-indigo-500 text-indigo-600 font-semibold dark:text-indigo-400'
                    : 'border-border/70 hover:bg-muted text-muted-foreground'
                }`}
              >
                <Building className="h-3.5 w-3.5 text-indigo-500" />
                Branch: {data.selected_manager.display_title || data.selected_manager.name}
              </button>
            </>
          )}

          {(viewLevel === 'agent' || viewLevel === 'customer') && data?.selected_agent && (
            <>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <button
                onClick={() => navigateToAgent(data.selected_agent!.id)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border transition-all ${
                  viewLevel === 'agent'
                    ? 'bg-sky-500/15 border-sky-500 text-sky-600 font-semibold dark:text-sky-400'
                    : 'border-border/70 hover:bg-muted text-muted-foreground'
                }`}
              >
                <UserCheck className="h-3.5 w-3.5 text-sky-500" />
                Officer: {data.selected_agent.name}
              </button>
            </>
          )}

          {viewLevel === 'customer' && data?.selected_customer && (
            <>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-teal-500 bg-teal-500/15 text-teal-600 font-semibold dark:text-teal-400">
                <Building2 className="h-3.5 w-3.5 text-teal-500" />
                Customer: {data.selected_customer.cust_name}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Main Workspace Layout (LEFT OVERVIEW INSPECTOR + RIGHT GRAPH CANVAS) */}
      <div className="flex flex-col lg:flex-row gap-4 min-h-0 flex-1">
        
        {/* LEFT-SIDE OVERVIEW INSPECTOR PANEL */}
        <div className="w-full lg:w-[360px] shrink-0 flex flex-col bg-card rounded-2xl border border-border/70 overflow-hidden order-2 lg:order-1">
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

              {/* FEATURED METRIC SUMMARY CARDS FOR OFFICERS / MANAGERS */}
              <div className="p-3 bg-muted/20 border-b shrink-0">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 bg-card rounded-xl border border-border/80 flex flex-col">
                    <span className="text-[9px] uppercase text-muted-foreground font-medium flex items-center gap-1">
                      <Users className="h-2.5 w-2.5 text-sky-500" /> Borrowers
                    </span>
                    <span className="font-mono font-bold text-foreground mt-0.5 text-xs">
                      {selectedNode.details["Total Borrowers"] || selectedNode.details["Serviced Borrowers"] || "1 Borrower"}
                    </span>
                  </div>

                  <div className="p-2 bg-card rounded-xl border border-border/80 flex flex-col">
                    <span className="text-[9px] uppercase text-muted-foreground font-medium flex items-center gap-1">
                      <DollarSign className="h-2.5 w-2.5 text-orange-500" /> Disbursed
                    </span>
                    <span className="font-mono font-bold text-orange-600 dark:text-orange-400 mt-0.5 text-xs truncate">
                      {selectedNode.details["Total Disbursed"] || selectedNode.details["Sanctioned Limit"] || "N/A"}
                    </span>
                  </div>

                  <div className="p-2 bg-card rounded-xl border border-border/80 flex flex-col">
                    <span className="text-[9px] uppercase text-muted-foreground font-medium flex items-center gap-1">
                      <CreditCard className="h-2.5 w-2.5 text-emerald-500" /> Repaid
                    </span>
                    <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 text-xs truncate">
                      {selectedNode.details["Total Repaid"] || selectedNode.details["Repayment Amount"] || "N/A"}
                    </span>
                  </div>

                  <div className="p-2 bg-card rounded-xl border border-border/80 flex flex-col">
                    <span className="text-[9px] uppercase text-muted-foreground font-medium flex items-center gap-1">
                      <TrendingUp className="h-2.5 w-2.5 text-purple-500" /> Efficiency
                    </span>
                    <span className="font-mono font-bold text-purple-600 dark:text-purple-400 mt-0.5 text-xs">
                      {selectedNode.details["Recovery Rate"] || selectedNode.details["Collection Efficiency"] || "Compliant"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Attributes Key-Value Table */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">
                    Record Overview & Details
                  </span>
                  {selectedNode.type === 'zonal' && selectedNode.zonal_id && (
                    <Button variant="ghost" size="sm" onClick={() => navigateToZonal(selectedNode.zonal_id!)} className="h-6 text-[10px] px-2 text-violet-500">
                      View Zone Branches →
                    </Button>
                  )}
                  {selectedNode.type === 'manager' && selectedNode.manager_id && (
                    <Button variant="ghost" size="sm" onClick={() => navigateToManager(selectedNode.manager_id!)} className="h-6 text-[10px] px-2 text-indigo-500">
                      View Branch Officers →
                    </Button>
                  )}
                  {selectedNode.type === 'agent' && selectedNode.agent_id && (
                    <Button variant="ghost" size="sm" onClick={() => navigateToAgent(selectedNode.agent_id!)} className="h-6 text-[10px] px-2 text-sky-500">
                      View Officer Borrowers →
                    </Button>
                  )}
                  {selectedNode.type === 'customer' && selectedNode.customer_id && (
                    <Button variant="ghost" size="sm" onClick={() => navigateToCustomer(selectedNode.customer_id!)} className="h-6 text-[10px] px-2 text-teal-500">
                      View Loan Accounts →
                    </Button>
                  )}
                </div>

                {Object.entries(selectedNode.details).map(([key, val]) => (
                  <div key={key} className="p-2.5 rounded-xl border border-border/60 bg-muted/30 flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground font-medium">{key}</span>
                    <span className="font-mono font-semibold text-foreground">{val}</span>
                  </div>
                ))}
              </div>

              {/* Relational Join Paths Helper */}
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
              <p className="text-xs">Click any node or label to inspect overview details on the left.</p>
            </div>
          )}
        </div>

        {/* RIGHT GRAPH CANVAS */}
        <div ref={containerRef} className="flex-1 bg-card/20 rounded-2xl border border-border/70 overflow-hidden relative flex flex-col justify-between order-1 lg:order-2">
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1 bg-background/85 backdrop-blur-md border rounded-xl p-2.5 max-w-[210px] pointer-events-none shadow-sm">
            <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground flex items-center gap-1">
              <Move className="h-2.5 w-2.5" /> Move & Click Nodes
            </span>
            <div className="space-y-1 mt-1 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#4c1d95' }} />
                <span className="font-medium text-foreground/80">MD & CEO / Executive</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#6d28d9' }} />
                <span className="font-medium text-foreground/80">Zonal VP</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#4338ca' }} />
                <span className="font-medium text-foreground/80">Branch Manager</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#0284c7' }} />
                <span className="font-medium text-foreground/80">Loan Officer / Agent</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#0f766e' }} />
                <span className="font-medium text-foreground/80">Customer / Borrower</span>
              </div>
            </div>
          </div>

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
              onNodeClick={(node) => handleNodeClick(node as GraphNode)}
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

          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-background/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-border/80 text-[11px] shadow-sm">
            <Badge variant="outline" className="font-semibold text-[10px] uppercase">
              {viewLevel} Tier
            </Badge>
            <span className="font-mono text-muted-foreground">• {data?.nodes.length || 0} active nodes</span>
            <span className="text-muted-foreground">• Click any node or label to inspect</span>
          </div>
        </div>

      </div>
    </div>
  );

  if (isExpanded && isMounted) {
    return createPortal(graphContent, document.body);
  }

  return graphContent;
}

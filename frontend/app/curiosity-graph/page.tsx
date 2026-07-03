'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { intel, auth } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { useTheme } from 'next-themes';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    BrainCircuit,
    Network,
    X,
    Clock,
    User,
    Zap,
    Activity,
    Building2,
    Briefcase,
    Layers3,
    Maximize2,
    Minimize2,
    ArrowRight,
} from 'lucide-react';
import dynamic from 'next/dynamic';

// Dynamically import ForceGraph2D
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => (
        <div className="flex items-center justify-center h-[600px]">
            <div className="animate-pulse text-muted-foreground flex items-center gap-2">
                <Network className="h-5 w-5" /> Loading graph engine...
            </div>
        </div>
    ),
});

interface GraphNode {
    id: number;
    label: string;
    value: number;
    color: string;
    category: string;
    bucket_type: string;
    normalized_label: string;
    raw_intent: string;
    aliases: string[];
    query_count: number;
    queries: Array<{
        query: string;
        timestamp: string;
        username: string;
        raw_intent: string;
    }>;
    x?: number;
    y?: number;
}

interface GraphEdge {
    source: number | GraphNode;
    target: number | GraphNode;
    weight: number;
}

interface ForceGraphLink {
    source: number | GraphNode;
    target: number | GraphNode;
    value: number;
}

interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
    curiosity_score: number;
    metadata: {
        total_searches: number;
        unique_topics: number;
        connections: number;
        days: number;
        user_id: number | null;
        filters: {
            categories: Array<{ key: string; label: string; count: number }>;
            bucket_types: Array<{ key: string; label: string; count: number }>;
        };
    };
}

const DATE_RANGE_OPTIONS = [
    { value: '7', label: 'Last 7 days' },
    { value: '30', label: 'Last 30 days' },
    { value: '90', label: 'Last 90 days' },
    { value: '180', label: 'Last 6 months' },
    { value: '365', label: 'Last year' },
];

const CATEGORY_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
    technology: { label: 'Technology', icon: <Zap className="h-3 w-3" /> },
    data: { label: 'Data', icon: <Layers3 className="h-3 w-3" /> },
    career: { label: 'Career', icon: <Briefcase className="h-3 w-3" /> },
    company: { label: 'Company', icon: <Building2 className="h-3 w-3" /> },
    leadership: { label: 'Leadership', icon: <BrainCircuit className="h-3 w-3" /> },
    other: { label: 'Other', icon: <Network className="h-3 w-3" /> },
};

const BUCKET_TYPE_LABELS: Record<string, string> = {
    system_intent: 'System Intents',
    user_topic: 'User Topics',
};

const getNodeRadius = (node: Pick<GraphNode, 'value'>): number =>
    Math.max(7, Math.sqrt(node.value || 1) * 3.2);

export default function CuriosityGraphPage() {
    const router = useRouter();
    const { theme, systemTheme } = useTheme();
    const graphRef = useRef<any>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const [isAdmin, setIsAdmin] = useState(false);
    const [loading, setLoading] = useState(true);
    const [graphData, setGraphData] = useState<GraphData | null>(null);
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
    const [daysFilter, setDaysFilter] = useState('90');
    const [userFilter, setUserFilter] = useState('all');
    const [activeCategories, setActiveCategories] = useState<string[]>([]);
    const [activeBucketTypes, setActiveBucketTypes] = useState<string[]>([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [minEdgeWeight, setMinEdgeWeight] = useState('1');
    const [topTopicLimit, setTopTopicLimit] = useState('all');
    const [isolateSelected, setIsolateSelected] = useState(false);
    const [isExpanded, setIsExpanded] = useState(false);
    const [users, setUsers] = useState<{ id: number; username: string; full_name: string }[]>([]);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

    const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');

    const filteredGraphData = useMemo(() => {
        if (!graphData) return null;

        const normalizedSearch = searchTerm.trim().toLowerCase();
        const parsedTopLimit = topTopicLimit === 'all' ? null : parseInt(topTopicLimit, 10);
        const parsedMinEdgeWeight = Math.max(1, parseInt(minEdgeWeight || '1', 10) || 1);

        let filteredNodes = graphData.nodes.filter((node) => {
            const matchesCategory =
                activeCategories.length === 0 || activeCategories.includes(node.category);
            const matchesBucket =
                activeBucketTypes.length === 0 || activeBucketTypes.includes(node.bucket_type);
            const matchesSearch =
                normalizedSearch.length === 0 ||
                node.label.toLowerCase().includes(normalizedSearch) ||
                node.raw_intent.toLowerCase().includes(normalizedSearch) ||
                node.aliases.some((alias) => alias.toLowerCase().includes(normalizedSearch));
            return matchesCategory && matchesBucket && matchesSearch;
        });

        if (parsedTopLimit) {
            filteredNodes = [...filteredNodes]
                .sort((left, right) => right.value - left.value)
                .slice(0, parsedTopLimit);
        }

        let allowedNodeIds = new Set(filteredNodes.map((node) => node.id));

        let edges = graphData.edges.filter((edge) => {
            const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
            const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;
            return (
                allowedNodeIds.has(sourceId as number) &&
                allowedNodeIds.has(targetId as number) &&
                edge.weight >= parsedMinEdgeWeight
            );
        });

        if (isolateSelected && selectedNode) {
            const connectedIds = new Set<number>([selectedNode.id]);
            edges.forEach((edge) => {
                const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
                const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;
                if (sourceId === selectedNode.id || targetId === selectedNode.id) {
                    connectedIds.add(sourceId as number);
                    connectedIds.add(targetId as number);
                }
            });
            allowedNodeIds = connectedIds;
            filteredNodes = filteredNodes.filter((node) => allowedNodeIds.has(node.id));
            edges = edges.filter((edge) => {
                const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
                const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;
                return allowedNodeIds.has(sourceId as number) && allowedNodeIds.has(targetId as number);
            });
        }

        const nodes = filteredNodes;

        return {
            ...graphData,
            nodes,
            edges,
            curiosity_score: (nodes.length * 10) + (edges.length * 5),
            metadata: {
                ...graphData.metadata,
                total_searches: nodes.reduce((sum, node) => sum + node.value, 0),
                unique_topics: nodes.length,
                connections: edges.length,
            },
        };
    }, [
        graphData,
        activeCategories,
        activeBucketTypes,
        searchTerm,
        minEdgeWeight,
        topTopicLimit,
        isolateSelected,
        selectedNode,
    ]);

    useEffect(() => {
        if (!selectedNode) return;
        const matchingNode =
            filteredGraphData?.nodes.find((node) => node.id === selectedNode.id) || null;
        if (matchingNode !== selectedNode) {
            setSelectedNode(matchingNode);
        }
    }, [filteredGraphData, selectedNode]);

    // Connection Lookups for fast hover checking
    const linksByNode = useMemo(() => {
        const map = new Map<number | string, Set<number | string>>();
        if (!filteredGraphData) return map;

        filteredGraphData.edges.forEach(edge => {
            const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
            const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;

            if (!map.has(sourceId)) map.set(sourceId, new Set());
            if (!map.has(targetId)) map.set(targetId, new Set());

            map.get(sourceId)!.add(targetId);
            map.get(targetId)!.add(sourceId);
        });
        return map;
    }, [filteredGraphData]);

    const nodesById = useMemo(() => {
        const map = new Map<number, GraphNode>();
        filteredGraphData?.nodes.forEach((node) => {
            map.set(node.id, node);
        });
        return map;
    }, [filteredGraphData]);

    const connectedTopics = useMemo(() => {
        if (!selectedNode || !filteredGraphData) {
            return [];
        }

        return filteredGraphData.edges
            .map((edge) => {
                const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
                const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;

                if (sourceId === selectedNode.id) {
                    return {
                        node: nodesById.get(targetId as number) || null,
                        weight: edge.weight,
                    };
                }

                if (targetId === selectedNode.id) {
                    return {
                        node: nodesById.get(sourceId as number) || null,
                        weight: edge.weight,
                    };
                }

                return null;
            })
            .filter((entry): entry is { node: GraphNode; weight: number } => Boolean(entry?.node))
            .sort((left, right) => right.weight - left.weight || right.node.value - left.node.value);
    }, [filteredGraphData, nodesById, selectedNode]);

    // Auth check
    useEffect(() => {
        auth.me()
            .then((user) => {
                const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
                if (userRole !== 'admin') {
                    router.push('/');
                } else {
                    setIsAdmin(true);
                }
            })
            .catch(() => router.push('/login'));
    }, [router]);

    // Initial load for users
    useEffect(() => {
        if (isAdmin) {
            loadUsers();
        }
    }, [isAdmin]);

    // Load graph data
    useEffect(() => {
        if (isAdmin) {
            loadGraphData();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isAdmin, daysFilter, userFilter]);

    // Track container dimensions
    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                const rect = containerRef.current.getBoundingClientRect();
                setDimensions({
                    width: rect.width,
                    height: isExpanded
                        ? Math.max(640, window.innerHeight - 120)
                        : Math.max(500, window.innerHeight - 380),
                });
            }
        };

        updateDimensions();
        // Slightly delay the resize listener to ensure layout shifts are accounted for
        const timeout = setTimeout(updateDimensions, 100);
        window.addEventListener('resize', updateDimensions);
        return () => {
            clearTimeout(timeout);
            window.removeEventListener('resize', updateDimensions);
        };
    }, [graphData, selectedNode, isExpanded]);

    const loadUsers = async () => {
        try {
            const data = await auth.listUsers();
            setUsers(data || []);
        } catch (error) {
            console.error('Failed to load users:', error);
        }
    };

    const loadGraphData = async () => {
        setLoading(true);
        try {
            const params: any = { days: parseInt(daysFilter) };
            if (userFilter !== 'all') {
                params.user_id = parseInt(userFilter);
            }
            const data = await intel.getGraphData(params);
            setGraphData(data);
        } catch (error) {
            console.error('Failed to load graph data:', error);
        } finally {
            setLoading(false);
        }
    };

    const focusNode = useCallback((node: GraphNode | null) => {
        if (!node) {
            return;
        }

        setSelectedNode(node);

        if (!graphRef.current || node.x == null || node.y == null) {
            return;
        }

        const currentZoom = graphRef.current.zoom();
        const targetZoom = Math.max(currentZoom, 2.1);
        graphRef.current.centerAt(node.x, node.y, 700);
        graphRef.current.zoom(targetZoom, 700);
    }, []);

    const handleNodeClick = useCallback((node: any) => {
        if (node && node.id !== undefined) {
            focusNode(node as GraphNode);
        }
    }, [focusNode]);

    const handleNodeHover = useCallback((node: any | null) => {
        setHoverNode(node || null);
    }, []);

    const drawNodePointerArea = useCallback(
        (node: any, color: string, ctx: CanvasRenderingContext2D) => {
            const size = getNodeRadius(node);
            const label = String(node.label || '');
            const labelWidth = Math.max(80, Math.min(220, (label.length * 7) + 18));

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x!, node.y!, size + 10, 0, 2 * Math.PI);
            ctx.fill();

            // Make the visible label area clickable so dense graphs remain usable.
            ctx.fillRect(
                node.x! - (labelWidth / 2),
                node.y! + size + 2,
                labelWidth,
                20
            );
        },
        []
    );

    const formatTimestamp = (ts: string) => {
        const date = new Date(ts);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    // Prepare graph data for ForceGraph2D
    const forceGraphData = useMemo(() => {
        return filteredGraphData
            ? {
                nodes: filteredGraphData.nodes.map((n) => ({ ...n, id: n.id })),
                links: filteredGraphData.edges.map((e): ForceGraphLink => ({
                    source: e.source,
                    target: e.target,
                    value: e.weight,
                })),
            }
            : { nodes: [], links: [] };
    }, [filteredGraphData]);

    useEffect(() => {
        if (!graphRef.current || forceGraphData.nodes.length === 0) {
            return;
        }

        const timer = setTimeout(() => {
            graphRef.current.zoomToFit(500, 70);
            const chargeForce = graphRef.current.d3Force('charge');
            if (chargeForce?.strength) {
                chargeForce.strength(-220);
            }
            const linkForce = graphRef.current.d3Force('link');
            if (linkForce?.distance) {
                linkForce.distance((link: ForceGraphLink) => 90 - Math.min((link.value || 1) * 6, 36));
            }
        }, 150);

        return () => clearTimeout(timer);
    }, [forceGraphData, dimensions]);

    // Custom node rendering (Obsidian-style)
    const paintNode = useCallback(
        (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const label = node.label || '';
            const size = getNodeRadius(node);
            const isSelected = selectedNode?.id === node.id;
            const isHovered = hoverNode?.id === node.id;
            const isNeighborOfSelected = selectedNode
                ? linksByNode.get(selectedNode.id)?.has(node.id) || false
                : false;

            // Determine if node should be dimmed based on hover relationships
            let isDimmed = false;
            let isConnected = false;

            if (hoverNode && hoverNode.id !== node.id) {
                isConnected = linksByNode.get(hoverNode.id)?.has(node.id) || false;
                if (!isConnected) {
                    isDimmed = true;
                }
            } else if (selectedNode && selectedNode.id !== node.id) {
                isConnected = isNeighborOfSelected;
            }

            // Draw node circle
            ctx.beginPath();
            ctx.arc(node.x!, node.y!, size + (isHovered ? 2 : 0), 0, 2 * Math.PI);

            // Node color logic 
            let nodeColor = node.color || (isDark ? '#6b7280' : '#9ca3af');
            if (isDimmed) {
                nodeColor = isDark ? '#374151' : '#e5e7eb'; // Very dim gray
            }

            ctx.fillStyle = nodeColor;
            ctx.fill();

            // Glow effect for selected node or hovered node
            if (isSelected || isHovered || isNeighborOfSelected) {
                ctx.strokeStyle = isDark ? '#ffffff' : '#000000';
                ctx.lineWidth = (isSelected ? 2.2 : 1.3) / globalScale;
                ctx.stroke();
            }

            // Text Label Logic
            // Scale font size based on zoom, but cap it so it stays readable when far away
            // Only draw text if zoomed in enough OR if it's the hovered/connected node
            const showText =
                globalScale >= 1.1 ||
                isHovered ||
                isConnected ||
                isSelected ||
                (node.value || 0) >= 4;

            if (showText && !isDimmed) {
                // Determine responsive font properties
                const baseFontSize = isHovered || isSelected ? 14 : 12;
                // Avoid font getting massive when zooming in super close
                const scaledFontSize = Math.min(baseFontSize / Math.max(globalScale * 0.5, 0.5), baseFontSize * 2);

                ctx.font = `${isHovered || isSelected ? 'bold ' : ''}${scaledFontSize}px Inter, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';

                // Draw slight shadow for text readability
                ctx.fillStyle = isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.8)';
                ctx.shadowColor = isDark ? '#000000' : '#ffffff';
                ctx.shadowBlur = 4;
                ctx.shadowOffsetX = 0;
                ctx.shadowOffsetY = 0;

                const yOffset = node.y! + size + (isHovered ? 3 : 2);

                // Text color
                ctx.fillStyle = isDark ? '#f3f4f6' : '#1f2937';
                ctx.fillText(label, node.x!, yOffset);

                // Reset shadow
                ctx.shadowBlur = 0;
            }
        },
        [selectedNode, hoverNode, linksByNode, isDark]
    );

    // Dynamic link styling (Obsidian-style)
    const paintLink = useCallback(
        (link: any, ctx: CanvasRenderingContext2D) => {
            const start = link.source;
            const end = link.target;

            if (start.x == null || start.y == null || end.x == null || end.y == null) return;

            let isConnectedToHover = false;
            let isDimmed = hoverNode !== null; // Default to dim if ANY node is hovered

            if (hoverNode) {
                // If this link connects directly to the hovered node, highlight it
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
                // No node hovered, standard view
                isDimmed = false;
            }

            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(end.x, end.y);

            // Calculate link style
            let opacity = isDimmed ? 0.04 : 0.24;
            let color = isDark ? '156, 163, 175' : '107, 114, 128'; // gray-400 : gray-500
            let width = Math.max(0.75, (link.value || 1) * 0.25);

            if (isConnectedToHover) {
                opacity = 0.78;
                color = isDark ? '255, 255, 255' : '0, 0, 0';
                width += 1;
            }

            ctx.strokeStyle = `rgba(${color}, ${opacity})`;
            ctx.lineWidth = width;
            ctx.stroke();
        },
        [hoverNode, isDark, selectedNode]
    );

    if (loading && !graphData) {
        return (
            <div className="h-full overflow-auto container mx-auto px-4 py-8 max-w-7xl">
                <div className="space-y-6">
                    <div className="flex flex-col gap-1">
                        <Skeleton className="h-8 w-64" />
                        <Skeleton className="h-4 w-96" />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <Skeleton className="h-[104px]" />
                        <Skeleton className="h-[104px]" />
                        <Skeleton className="h-[104px]" />
                        <Skeleton className="h-[104px]" />
                    </div>

                    <div className="flex gap-4">
                        <Skeleton className="h-10 w-48" />
                        <Skeleton className="h-10 w-24" />
                    </div>

                    <Skeleton className="h-[500px] w-full" />
                </div>
            </div>
        );
    }

    if (!isAdmin) return null;

    const score = filteredGraphData?.curiosity_score || 0;
    const meta = filteredGraphData?.metadata;
    const availableFilters = graphData?.metadata.filters;

    const toggleCategory = (categoryKey: string) => {
        setActiveCategories((current) =>
            current.includes(categoryKey)
                ? current.filter((value) => value !== categoryKey)
                : [...current, categoryKey]
        );
    };

    const toggleBucketType = (bucketType: string) => {
        setActiveBucketTypes((current) =>
            current.includes(bucketType)
                ? current.filter((value) => value !== bucketType)
                : [...current, bucketType]
        );
    };

    const graphWorkspaceClassName = isExpanded
        ? 'fixed inset-4 z-50 flex gap-4 rounded-2xl border bg-background/95 p-4 shadow-2xl backdrop-blur'
        : 'flex gap-4 w-full';

    return (
        <div className="h-full overflow-auto container mx-auto px-4 py-8 max-w-7xl">
            <div className="space-y-6">
                {/* Header matching Companies/Usage/Email KB tabs */}
                <div className="flex flex-col gap-1">
                    <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
                        Curiosity Graph
                    </h1>
                    <p className="text-muted-foreground">
                        Explore the knowledge landscape through connected search topics
                    </p>
                </div>

                {/* KPI Cards — using standard Card styles */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                                Activity Score
                            </CardTitle>
                            <Activity className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{score}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                Base metric + edge weight
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Total Searches
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{meta?.total_searches || 0}</div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Unique Topics
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{meta?.unique_topics || 0}</div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Topic Connections
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{meta?.connections || 0}</div>
                        </CardContent>
                    </Card>
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-4">
                    <div className="w-[180px]">
                        <Select value={daysFilter} onValueChange={setDaysFilter}>
                            <SelectTrigger>
                                <SelectValue placeholder="Time range" />
                            </SelectTrigger>
                            <SelectContent>
                                {DATE_RANGE_OPTIONS.map((opt) => (
                                    <SelectItem key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="w-[220px]">
                        <Select value={userFilter} onValueChange={setUserFilter}>
                            <SelectTrigger>
                                <SelectValue placeholder="All Users" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Users</SelectItem>
                                {users.map((u) => (
                                    <SelectItem key={u.id} value={u.id.toString()}>
                                        {u.full_name} (@{u.username})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <Button variant="outline" onClick={loadGraphData} disabled={loading}>
                        {loading ? 'Refreshing...' : 'Refresh Graph'}
                    </Button>

                    <div className="flex flex-wrap gap-2 ml-auto">
                        <Button
                            variant={activeCategories.length === 0 ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setActiveCategories([])}
                        >
                            All Categories
                        </Button>
                        {availableFilters?.categories.map(({ key, label, count }) => (
                            <Button
                                key={key}
                                variant={activeCategories.includes(key) ? 'default' : 'outline'}
                                size="sm"
                                className="gap-1.5"
                                onClick={() => toggleCategory(key)}
                            >
                                {CATEGORY_LABELS[key]?.icon || <Network className="h-3 w-3" />}
                                {label}
                                <span className="text-xs opacity-70">{count}</span>
                            </Button>
                        ))}
                    </div>
                </div>

                <div className="flex flex-wrap items-end gap-4">
                    <div className="min-w-[240px] flex-1">
                        <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2 block">
                            Topic Search
                        </label>
                        <Input
                            placeholder="Search nodes like SQL, Interviews, Leadership..."
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                        />
                    </div>

                    <div className="w-[160px]">
                        <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2 block">
                            Min Edge Weight
                        </label>
                        <Select value={minEdgeWeight} onValueChange={setMinEdgeWeight}>
                            <SelectTrigger>
                                <SelectValue placeholder="Min edge weight" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1">1+</SelectItem>
                                <SelectItem value="2">2+</SelectItem>
                                <SelectItem value="3">3+</SelectItem>
                                <SelectItem value="5">5+</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="w-[160px]">
                        <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2 block">
                            Top Topics
                        </label>
                        <Select value={topTopicLimit} onValueChange={setTopTopicLimit}>
                            <SelectTrigger>
                                <SelectValue placeholder="All topics" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All</SelectItem>
                                <SelectItem value="25">Top 25</SelectItem>
                                <SelectItem value="50">Top 50</SelectItem>
                                <SelectItem value="100">Top 100</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    <Button
                        variant={isolateSelected ? 'default' : 'outline'}
                        onClick={() => setIsolateSelected((current) => !current)}
                        disabled={!selectedNode}
                    >
                        {isolateSelected ? 'Isolating Selection' : 'Isolate Selected'}
                    </Button>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Topic Scope
                    </span>
                    <Button
                        variant={activeBucketTypes.length === 0 ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setActiveBucketTypes([])}
                    >
                        All Topics
                    </Button>
                    {availableFilters?.bucket_types.map(({ key, label, count }) => (
                        <Button
                            key={key}
                            variant={activeBucketTypes.includes(key) ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => toggleBucketType(key)}
                        >
                            {label}
                            <span className="text-xs opacity-70">{count}</span>
                        </Button>
                    ))}
                    {(activeCategories.length > 0 || activeBucketTypes.length > 0) && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setActiveCategories([]);
                                setActiveBucketTypes([]);
                            }}
                        >
                            Clear Filters
                        </Button>
                    )}
                </div>

                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {searchTerm.trim().length > 0 && (
                        <Badge variant="secondary">Search: {searchTerm.trim()}</Badge>
                    )}
                    <Badge variant="secondary">Edges: {minEdgeWeight}+</Badge>
                    <Badge variant="secondary">
                        Topics: {topTopicLimit === 'all' ? 'All' : `Top ${topTopicLimit}`}
                    </Badge>
                    {activeCategories.length > 0 && (
                        <Badge variant="secondary">
                            Categories:{' '}
                            {activeCategories
                                .map((key) => CATEGORY_LABELS[key]?.label || key)
                                .join(', ')}
                        </Badge>
                    )}
                    {activeBucketTypes.length > 0 && (
                        <Badge variant="secondary">
                            Scope:{' '}
                            {activeBucketTypes
                                .map((key) => BUCKET_TYPE_LABELS[key] || key)
                                .join(', ')}
                        </Badge>
                    )}
                    {isolateSelected && selectedNode && (
                        <Badge variant="secondary">Isolated: {selectedNode.label}</Badge>
                    )}
                    {activeCategories.length === 0 && activeBucketTypes.length === 0 && (
                        <Badge variant="secondary">Showing all topics</Badge>
                    )}
                </div>

                {searchTerm.trim().length > 0 && filteredGraphData && (
                    <Card>
                        <CardContent className="p-4">
                            <div className="flex flex-wrap gap-2">
                                {filteredGraphData.nodes.slice(0, 12).map((node) => (
                                    <Button
                                        key={node.id}
                                        variant={selectedNode?.id === node.id ? 'default' : 'outline'}
                                        size="sm"
                                        className="justify-start gap-2"
                                        onClick={() => focusNode(node)}
                                    >
                                        <span
                                            className="h-2 w-2 rounded-full"
                                            style={{ backgroundColor: node.color }}
                                        />
                                        {node.label}
                                    </Button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {isExpanded && (
                    <div
                        className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm"
                        onClick={() => setIsExpanded(false)}
                    />
                )}

                {/* Graph + Side Panel Container */}
                <div className={graphWorkspaceClassName}>
                    {/* Main Graph Card */}
                    <Card
                        className="flex-1 overflow-hidden min-h-[500px] border relative"
                        ref={containerRef}
                    >
                        {/* Optional overlay instructional text */}
                        <div className="absolute top-4 left-4 z-10 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded border backdrop-blur-sm pointer-events-none">
                            Scroll to zoom • Click/Drag to pan • Click node to expand
                        </div>

                        <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                className="bg-background/85 backdrop-blur-sm"
                                onClick={() => setIsExpanded((current) => !current)}
                            >
                                {isExpanded ? (
                                    <>
                                        <Minimize2 className="h-4 w-4" />
                                        Exit Full Screen
                                    </>
                                ) : (
                                    <>
                                        <Maximize2 className="h-4 w-4" />
                                        Expand
                                    </>
                                )}
                            </Button>
                        </div>

                        <CardContent className="p-0 h-full w-full">
                            {forceGraphData.nodes.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                                    <Network className="h-12 w-12 mb-4 opacity-20" />
                                    <p className="text-base font-medium">No graph data available</p>
                                    <p className="text-sm">
                                        Searches and topics will appear here once connected.
                                    </p>
                                </div>
                            ) : (
                                <ForceGraph2D
                                    ref={graphRef}
                                    graphData={forceGraphData}
                                    width={dimensions.width}
                                    height={dimensions.height}
                                    // Visual configuration
                                    nodeCanvasObject={paintNode}
                                    linkCanvasObject={paintLink}
                                    // Override linkColor if using canvas object, but we provide it just in case
                                    linkColor={() => isDark ? 'rgba(156,163,175,0.1)' : 'rgba(107,114,128,0.1)'}
                                    backgroundColor="transparent"
                                    // Interactions
                                    onNodeClick={handleNodeClick}
                                    onNodeHover={handleNodeHover}
                                    // Physics tweaks for better initial layout
                                    cooldownTicks={160}
                                    d3AlphaDecay={0.035}
                                    d3VelocityDecay={0.24}
                                    enableZoomInteraction={true}
                                    enablePanInteraction={true}
                                    enableNodeDrag={true}
                                    autoPauseRedraw={true}
                                    minZoom={0.35}
                                    maxZoom={6}
                                    // Make both the node and its visible label hoverable/clickable.
                                    nodePointerAreaPaint={drawNodePointerArea}
                                />
                            )}
                        </CardContent>
                    </Card>

                    {/* Detail Side Panel */}
                    {selectedNode && (
                        <Card
                            className={`w-[320px] shrink-0 border shadow-sm flex flex-col min-h-[500px] ${
                                isExpanded ? 'h-[calc(100vh-120px)]' : 'h-[calc(100vh-280px)]'
                            }`}
                        >
                            <CardHeader className="pb-3 border-b border-border/50">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <CardTitle className="text-base leading-tight mb-2 flex items-center gap-2 pr-4">
                                            <span
                                                className="h-2.5 w-2.5 rounded-full shrink-0"
                                                style={{ backgroundColor: selectedNode.color }}
                                            />
                                            {selectedNode.label}
                                        </CardTitle>
                                        <div className="flex gap-2 flex-wrap mt-1">
                                            <Badge variant="secondary" className="font-normal text-xs">
                                                {selectedNode.value} search{selectedNode.value !== 1 && 'es'}
                                            </Badge>
                                            <Badge variant="outline" className="font-normal text-xs capitalize">
                                                {CATEGORY_LABELS[selectedNode.category]?.label || selectedNode.category}
                                            </Badge>
                                            <Badge variant="outline" className="font-normal text-xs">
                                                {BUCKET_TYPE_LABELS[selectedNode.bucket_type] || selectedNode.bucket_type}
                                            </Badge>
                                        </div>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 shrink-0 -mt-1 -mr-1"
                                        onClick={() => setSelectedNode(null)}
                                    >
                                        <X className="h-4 w-4" />
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                                    Topic Details
                                </h4>
                                <div className="space-y-2 mb-4 text-sm">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <Badge variant="secondary">
                                            {selectedNode.query_count} search{selectedNode.query_count !== 1 && 'es'}
                                        </Badge>
                                        <Badge variant="outline">
                                            {connectedTopics.length} direct connection{connectedTopics.length !== 1 && 's'}
                                        </Badge>
                                        {selectedNode.aliases.slice(0, 4).map((alias) => (
                                            <Badge key={alias} variant="outline">
                                                {alias}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                                {connectedTopics.length > 0 && (
                                    <>
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                                            Connected Topics
                                        </h4>
                                        <div className="space-y-2 mb-5">
                                            {connectedTopics.slice(0, 8).map(({ node, weight }) => (
                                                <button
                                                    key={node.id}
                                                    type="button"
                                                    className="w-full rounded-lg border border-border/60 px-3 py-2 text-left transition-colors hover:bg-muted/50"
                                                    onClick={() => focusNode(node)}
                                                >
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="min-w-0">
                                                            <div className="flex items-center gap-2">
                                                                <span
                                                                    className="h-2.5 w-2.5 rounded-full shrink-0"
                                                                    style={{ backgroundColor: node.color }}
                                                                />
                                                                <span className="truncate text-sm font-medium text-foreground">
                                                                    {node.label}
                                                                </span>
                                                            </div>
                                                            <p className="mt-1 text-xs text-muted-foreground">
                                                                {CATEGORY_LABELS[node.category]?.label || node.category}
                                                            </p>
                                                        </div>
                                                        <div className="flex items-center gap-2 shrink-0 text-xs text-muted-foreground">
                                                            <Badge variant="secondary">{weight}</Badge>
                                                            <ArrowRight className="h-3.5 w-3.5" />
                                                        </div>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </>
                                )}
                                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                                    Recent Activity
                                </h4>
                                {selectedNode.queries && selectedNode.queries.length > 0 ? (
                                    <div className="space-y-4">
                                        {selectedNode.queries.map((q, idx) => (
                                            <div
                                                key={idx}
                                                className="text-sm pb-4 border-b border-border/40 last:border-0 last:pb-0"
                                            >
                                                <p className="text-foreground leading-relaxed mb-2">
                                                    "{q.query}"
                                                </p>
                                                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                    <span className="flex items-center gap-1">
                                                        <User className="h-3 w-3" />
                                                        {q.username}
                                                    </span>
                                                    <span>{q.raw_intent}</span>
                                                    <span className="flex items-center gap-1">
                                                        <Clock className="h-3 w-3" />
                                                        {formatTimestamp(q.timestamp)}
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground italic">
                                        No documented queries.
                                    </p>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { intel, auth } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import {
    Search,
    Filter,
    ChevronLeft,
    ChevronRight,
    History,
    ChevronDown,
    ChevronUp,
    MessageSquare,
    Database
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
    Pagination,
    PaginationContent,
    PaginationEllipsis,
    PaginationItem,
    PaginationLink,
    PaginationNext,
    PaginationPrevious,
} from "@/components/ui/pagination";

interface SearchRecord {
    id: string;
    username: string;
    full_name: string;
    query_text: string;
    response_text?: string;
    response_preview?: string;
    intent: string;
    normalized_intent?: string;
    intent_category?: string;
    intent_bucket_type?: string;
    chat_type?: 'intel' | 'general';
    detected_company: string;
    timestamp: string;
    response_time_ms?: number;
}

interface PaginatedResponse {
    count: number;
    next: string | null;
    previous: string | null;
    results: SearchRecord[];
}

const INTENT_OPTIONS = [
    { value: '', label: 'All Intents' },
    { value: 'company_overview', label: 'Company Overview' },
    { value: 'requirements', label: 'Requirements' },
    { value: 'open_requirements', label: 'Requirements' },
    { value: 'interviews', label: 'Interviews' },
    { value: 'interview_questions', label: 'Interviews' },
    { value: 'contacts', label: 'Contacts' },
    { value: 'resources', label: 'Resources' },
    { value: 'general', label: 'General' },
    { value: 'general_chat', label: 'General Chat' },
];

const CHAT_TYPE_OPTIONS = [
    { value: '', label: 'All Chat Types' },
    { value: 'intel', label: 'Intel / Company' },
    { value: 'general', label: 'General Chat' },
];

const DATE_RANGE_OPTIONS = [
    { value: '7', label: 'Last 7 days' },
    { value: '14', label: 'Last 14 days' },
    { value: '30', label: 'Last 30 days' },
    { value: '90', label: 'Last 90 days' },
    { value: '', label: 'All time' },
];

export default function SearchHistoryPage() {
    const router = useRouter();
    const [isAdmin, setIsAdmin] = useState(false);
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<PaginatedResponse | null>(null);
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

    // Filters
    const [usernameFilter, setUsernameFilter] = useState('');
    const [intentFilter, setIntentFilter] = useState('');
    const [chatTypeFilter, setChatTypeFilter] = useState('');
    const [daysFilter, setDaysFilter] = useState('30');
    const [page, setPage] = useState(1);
    const pageSize = 20;

    useEffect(() => {
        auth.me()
            .then((user) => {
                const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
                if (userRole !== 'admin') {
                    router.push('/');
                } else {
                    setIsAdmin(true);
                    loadData();
                }
            })
            .catch(() => router.push('/login'))
            .finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const loadData = async (pageNum = 1) => {
        try {
            const params: Record<string, string | number> = {
                page: pageNum,
                page_size: pageSize,
            };
            if (usernameFilter) params.user = usernameFilter;
            if (intentFilter && intentFilter !== 'all') params.intent = intentFilter;
            if (chatTypeFilter && chatTypeFilter !== 'all') params.chat_type = chatTypeFilter;
            if (daysFilter && daysFilter !== 'all') params.days = parseInt(daysFilter);

            const response = await intel.getHistory(params);
            setData(response);
            setPage(pageNum);
            setExpandedRows(new Set()); // Reset expanded rows on new data
        } catch (error) {
            console.error('Failed to load search history:', error);
        }
    };

    const handleFilter = () => {
        setPage(1);
        loadData(1);
    };

    const toggleRow = (id: string) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedRows(newExpanded);
    };

    const handleNextPage = () => {
        if (data?.next) {
            loadData(page + 1);
        }
    };

    const handlePrevPage = () => {
        if (data?.previous && page > 1) {
            loadData(page - 1);
        }
    };

    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const getChatTypeIcon = (type?: string) => {
        if (type === 'general') return <MessageSquare className="h-4 w-4 text-blue-500" />;
        return <Database className="h-4 w-4 text-purple-500" />;
    };

    if (loading) {
        return (
            <main className="container mx-auto px-4 max-w-7xl py-8">
                <Skeleton className="h-10 w-64 mb-6" />
                <Skeleton className="h-96 w-full" />
            </main>
        );
    }

    if (!isAdmin) {
        return null;
    }

    const totalPages = data ? Math.ceil(data.count / pageSize) : 0;

    return (
        <main className="h-full overflow-auto container mx-auto px-4 max-w-7xl py-8">
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <History className="h-8 w-8 text-primary" />
                    <h1 className="text-3xl font-bold text-foreground">Search History</h1>
                </div>
                <p className="text-muted-foreground">
                    View all search queries and AI responses across the platform.
                </p>
            </div>

            {/* Filters */}
            <Card className="mb-6">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Filter className="h-5 w-5" />
                        Filters
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-wrap gap-4 items-end">
                        <div className="flex-1 min-w-[200px]">
                            <label className="text-sm font-medium text-foreground mb-1.5 block">
                                Username
                            </label>
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search by username..."
                                    value={usernameFilter}
                                    onChange={(e) => setUsernameFilter(e.target.value)}
                                    className="pl-9"
                                />
                            </div>
                        </div>

                        <div className="w-48">
                            <label className="text-sm font-medium text-foreground mb-1.5 block">
                                Chat Type
                            </label>
                            <Select value={chatTypeFilter} onValueChange={setChatTypeFilter}>
                                <SelectTrigger>
                                    <SelectValue placeholder="All Types" />
                                </SelectTrigger>
                                <SelectContent>
                                    {CHAT_TYPE_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value || 'all'}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="w-48">
                            <label className="text-sm font-medium text-foreground mb-1.5 block">
                                Intent
                            </label>
                            <Select value={intentFilter} onValueChange={setIntentFilter}>
                                <SelectTrigger>
                                    <SelectValue placeholder="All Intents" />
                                </SelectTrigger>
                                <SelectContent>
                                    {INTENT_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value || 'all'}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="w-48">
                            <label className="text-sm font-medium text-foreground mb-1.5 block">
                                Date Range
                            </label>
                            <Select value={daysFilter} onValueChange={setDaysFilter}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select range" />
                                </SelectTrigger>
                                <SelectContent>
                                    {DATE_RANGE_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value || 'all'}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <Button onClick={handleFilter}>
                            Apply Filters
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Results Table */}
            <Card>
                <CardHeader className="pb-3 flex-row items-center justify-between">
                    <CardTitle className="text-lg">
                        Search Results
                        {data && (
                            <span className="text-sm font-normal text-muted-foreground ml-2">
                                ({data.count} total)
                            </span>
                        )}
                    </CardTitle>
                    {totalPages > 1 && (
                        <div className="flex justify-end">
                            <Pagination>
                                <PaginationContent>
                                    <PaginationItem>
                                        <PaginationPrevious
                                            onClick={handlePrevPage}
                                            className={!data?.previous ? "pointer-events-none opacity-50" : "cursor-pointer"}
                                        />
                                    </PaginationItem>

                                    <PaginationItem>
                                        <span className="flex h-9 items-center justify-center text-sm font-medium px-4">
                                            Page {page} of {totalPages}
                                        </span>
                                    </PaginationItem>

                                    <PaginationItem>
                                        <PaginationNext
                                            onClick={handleNextPage}
                                            className={!data?.next ? "pointer-events-none opacity-50" : "cursor-pointer"}
                                        />
                                    </PaginationItem>
                                </PaginationContent>
                            </Pagination>
                        </div>
                    )}
                </CardHeader>
                <CardContent>
                    {!data || data.results.length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                            <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No search history found</p>
                            <p className="text-sm">Try adjusting your filters</p>
                        </div>
                    ) : (
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[50px]"></TableHead>
                                        <TableHead className="w-40">User</TableHead>
                                        <TableHead>Query / Response Preview</TableHead>
                                        <TableHead className="w-32">Type</TableHead>
                                        <TableHead className="w-40">Intent</TableHead>
                                        <TableHead className="w-40">Company</TableHead>
                                        <TableHead className="w-44">Timestamp</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.results.map((record) => (
                                        <>
                                            <TableRow
                                                key={record.id}
                                                className={cn(
                                                    "cursor-pointer hover:bg-muted/50 transition-colors",
                                                    expandedRows.has(record.id) && "bg-muted/50 border-b-0"
                                                )}
                                                onClick={() => toggleRow(record.id)}
                                            >
                                                <TableCell>
                                                    {expandedRows.has(record.id) ? (
                                                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                                    ) : (
                                                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                                    )}
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    <div className="flex flex-col">
                                                        <span>{record.full_name || record.username}</span>
                                                        <span className="text-xs text-muted-foreground">@{record.username}</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="max-w-md">
                                                    <div className="space-y-1">
                                                        <div className="font-medium text-sm truncate" title={record.query_text}>
                                                            Q: {record.query_text}
                                                        </div>
                                                        {record.response_preview && (
                                                            <div className="text-xs text-muted-foreground truncate" title={record.response_text}>
                                                                A: {record.response_preview}
                                                            </div>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2 text-sm">
                                                        {getChatTypeIcon(record.chat_type)}
                                                        <span className="capitalize">{record.chat_type === 'intel' ? 'Company' : 'General'}</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="capitalize text-sm">
                                                    <div className="flex flex-col gap-1">
                                                        <span>{record.normalized_intent || record.intent?.replace(/_/g, ' ') || 'unknown'}</span>
                                                        {record.normalized_intent && record.normalized_intent !== record.intent && (
                                                            <span className="text-xs text-muted-foreground">
                                                                raw: {record.intent}
                                                            </span>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground text-sm">
                                                    {record.detected_company || '-'}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground text-xs">
                                                    <div className="flex flex-col gap-0.5">
                                                        <span>{formatTimestamp(record.timestamp)}</span>
                                                        {record.response_time_ms && (
                                                            <span className="text-muted-foreground/70">{record.response_time_ms}ms</span>
                                                        )}
                                                    </div>
                                                </TableCell>
                                            </TableRow>

                                            {/* Expanded detail row */}
                                            {expandedRows.has(record.id) && (
                                                <TableRow className="bg-muted/30 border-t-0 hover:bg-muted/30">
                                                    <TableCell colSpan={7} className="p-0">
                                                        <div className="p-4 space-y-4">
                                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                                <div className="bg-background border rounded-lg p-4">
                                                                    <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                                                                        <span className="h-2 w-2 rounded-full bg-blue-500" />
                                                                        User Query
                                                                    </h4>
                                                                    <p className="text-sm whitespace-pre-wrap">{record.query_text}</p>
                                                                </div>
                                                                <div className="bg-background border rounded-lg p-4">
                                                                    <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                                                                        <span className="h-2 w-2 rounded-full bg-purple-500" />
                                                                        AI Response
                                                                    </h4>
                                                                    <div className="text-sm overflow-y-auto max-h-[300px] prose prose-sm dark:prose-invert">
                                                                        <p className="whitespace-pre-wrap">{record.response_text || 'No response generated.'}</p>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </main>
    );
}

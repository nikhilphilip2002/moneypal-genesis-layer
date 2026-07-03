'use client';

import { useState, useEffect, useCallback } from 'react';
import { emailKB } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    Mail,
    FolderOpen,
    Download,
    CheckCircle2,
    AlertCircle,
    Loader2,
    RefreshCw,
    Database,
    Search,
    Zap,
} from 'lucide-react';

interface EmailHeader {
    message_id: string;
    sender: string;
    recipient: string;
    subject: string;
    date: string;
    folder: string;
    company_name: string;
    already_extracted: boolean;
}

interface ConnectionConfig {
    email: string;
    password: string;
    host: string;
    port: number;
    use_ssl: boolean;
}

export default function EmailKnowledgeBasePage() {
    // Connection state
    const [config, setConfig] = useState<ConnectionConfig>({
        email: '',
        password: '',
        host: 'imap.dreamhost.com',
        port: 993,
        use_ssl: true,
    });
    const [showCustomSettings, setShowCustomSettings] = useState(false);
    const [connected, setConnected] = useState(false);
    const [connecting, setConnecting] = useState(false);
    const [connectionError, setConnectionError] = useState('');

    // Folder state
    const [folders, setFolders] = useState<string[]>([]);
    const [selectedFolder, setSelectedFolder] = useState('INBOX');
    const [loadingFolders, setLoadingFolders] = useState(false);

    // Email browsing state
    const [emails, setEmails] = useState<EmailHeader[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [loadingEmails, setLoadingEmails] = useState(false);
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [searchQuery, setSearchQuery] = useState('');

    // Extraction state
    const [extracting, setExtracting] = useState(false);
    const [extractResult, setExtractResult] = useState<any>(null);

    // Stats state
    const [stats, setStats] = useState<any>(null);

    const loadStats = useCallback(async () => {
        try {
            const data = await emailKB.stats();
            setStats(data);
        } catch (e) {
            // Stats might fail if not admin
        }
    }, []);

    useEffect(() => {
        loadStats();
    }, [loadStats]);

    const handleConnect = async () => {
        setConnecting(true);
        setConnectionError('');
        try {
            const result = await emailKB.testConnection(config);
            if (result.status === 'connected') {
                setConnected(true);
                setLoadingFolders(true);
                const folderData = await emailKB.listFolders(config);
                setFolders(folderData.folders || []);
                setLoadingFolders(false);
            }
        } catch (e: any) {
            setConnectionError(e.message || 'Connection failed');
            setConnected(false);
        } finally {
            setConnecting(false);
        }
    };

    const handleBrowse = async () => {
        setLoadingEmails(true);
        setSelectedIds(new Set());
        try {
            const data = await emailKB.browseEmails({
                ...config,
                folder: selectedFolder,
                date_from: dateFrom || undefined,
                date_to: dateTo || undefined,
                search: searchQuery || undefined,
            });
            setEmails(data.emails || []);
        } catch (e: any) {
            setConnectionError(e.message || 'Failed to browse emails');
        } finally {
            setLoadingEmails(false);
        }
    };

    const handleExtract = async () => {
        if (selectedIds.size === 0) return;
        setExtracting(true);
        setExtractResult(null);
        try {
            const result = await emailKB.extractEmails({
                ...config,
                folder: selectedFolder,
                message_ids: Array.from(selectedIds),
            });
            setExtractResult(result);
            loadStats();
            handleBrowse();
        } catch (e: any) {
            setExtractResult({ error: e.message });
        } finally {
            setExtracting(false);
        }
    };

    const toggleEmail = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const toggleAll = () => {
        if (selectedIds.size === emails.filter(e => !e.already_extracted).length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(emails.filter(e => !e.already_extracted).map(e => e.message_id)));
        }
    };

    return (
        <div className="h-full overflow-auto container mx-auto px-4 py-8 max-w-7xl">
            <div className="space-y-6">
                {/* Page Header */}
                <div className="flex flex-col gap-1">
                    <h1 className="text-2xl font-semibold text-foreground">Email Knowledge Base</h1>
                    <p className="text-muted-foreground">
                        Connect to your email, browse, and extract messages into the intel system
                    </p>
                </div>

                <div className="grid lg:grid-cols-3 gap-6">
                    {/* Left Column — Connection + Stats */}
                    <div className="space-y-6">
                        {/* IMAP Connection Card */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-lg">IMAP Connection</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="email-address">Email Address</Label>
                                    <Input
                                        id="email-address"
                                        type="email"
                                        placeholder="you@example.com"
                                        value={config.email}
                                        onChange={e => setConfig({ ...config, email: e.target.value })}
                                        disabled={connected}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="email-password">Password</Label>
                                    <Input
                                        id="email-password"
                                        type="password"
                                        placeholder="••••••••"
                                        value={config.password}
                                        onChange={e => setConfig({ ...config, password: e.target.value })}
                                        disabled={connected}
                                    />
                                </div>

                                {/* Custom IMAP Settings Toggle */}
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="custom-settings" className="text-sm text-muted-foreground cursor-pointer">
                                        Custom IMAP Settings
                                    </Label>
                                    <Switch
                                        id="custom-settings"
                                        checked={showCustomSettings}
                                        onCheckedChange={setShowCustomSettings}
                                        disabled={connected}
                                    />
                                </div>

                                {showCustomSettings && (
                                    <div className="space-y-3 p-3 rounded-lg bg-muted/50 border border-border">
                                        <div className="space-y-2">
                                            <Label htmlFor="imap-host">IMAP Host</Label>
                                            <Input
                                                id="imap-host"
                                                value={config.host}
                                                onChange={e => setConfig({ ...config, host: e.target.value })}
                                                disabled={connected}
                                            />
                                        </div>
                                        <div className="flex gap-3">
                                            <div className="flex-1 space-y-2">
                                                <Label htmlFor="imap-port">Port</Label>
                                                <Input
                                                    id="imap-port"
                                                    type="number"
                                                    value={config.port}
                                                    onChange={e => setConfig({ ...config, port: parseInt(e.target.value) || 993 })}
                                                    disabled={connected}
                                                />
                                            </div>
                                            <div className="flex-1 space-y-2">
                                                <Label>SSL</Label>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <Switch
                                                        checked={config.use_ssl}
                                                        onCheckedChange={v => setConfig({ ...config, use_ssl: v })}
                                                        disabled={connected}
                                                    />
                                                    <span className="text-sm text-muted-foreground">{config.use_ssl ? 'On' : 'Off'}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {connectionError && (
                                    <Card className="border-destructive bg-destructive/10">
                                        <CardContent className="py-3 px-4">
                                            <div className="flex items-center gap-2 text-sm text-destructive">
                                                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                                {connectionError}
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}

                                {connected ? (
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2 text-sm text-foreground">
                                            <CheckCircle2 className="h-4 w-4" />
                                            Connected
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => {
                                                setConnected(false);
                                                setFolders([]);
                                                setEmails([]);
                                                setConfig(prev => ({ ...prev, password: '' }));
                                            }}
                                        >
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        onClick={handleConnect}
                                        disabled={connecting || !config.email || !config.password}
                                        className="w-full"
                                    >
                                        {connecting ? (
                                            <>
                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                Connecting...
                                            </>
                                        ) : (
                                            'Connect'
                                        )}
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                        {/* Stats Card */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-lg">Knowledge Base Stats</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {stats ? (
                                    <div className="space-y-4">
                                        <div className="grid grid-cols-2 gap-4">
                                            <Card>
                                                <CardContent className="pt-6 text-center">
                                                    <div className="text-2xl font-bold text-foreground">{stats.total_extracted || 0}</div>
                                                    <p className="text-sm text-muted-foreground mt-1">Extracted</p>
                                                </CardContent>
                                            </Card>
                                            <Card>
                                                <CardContent className="pt-6 text-center">
                                                    <div className="text-2xl font-bold text-foreground">{stats.total_in_vector_db || 0}</div>
                                                    <p className="text-sm text-muted-foreground mt-1">In Vector DB</p>
                                                </CardContent>
                                            </Card>
                                        </div>
                                        {stats.companies && stats.companies.length > 0 && (
                                            <div>
                                                <p className="text-sm text-muted-foreground mb-2">Companies</p>
                                                <div className="flex flex-wrap gap-1">
                                                    {stats.companies.map((c: string) => (
                                                        <Badge key={c} variant="secondary">{c}</Badge>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        <Button variant="outline" size="sm" onClick={loadStats} className="w-full">
                                            <RefreshCw className="h-4 w-4 mr-2" /> Refresh Stats
                                        </Button>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <Skeleton className="h-16 w-full" />
                                        <Skeleton className="h-16 w-full" />
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Right Column — Email Browser */}
                    <div className="lg:col-span-2">
                        <Card className="h-full">
                            <CardHeader className="pb-3 flex-row items-center justify-between">
                                <CardTitle className="text-lg">Email Browser</CardTitle>
                                {connected && (
                                    <span className="text-sm text-muted-foreground">
                                        {emails.length} email{emails.length !== 1 ? 's' : ''}
                                    </span>
                                )}
                            </CardHeader>
                            <CardContent>
                                {!connected ? (
                                    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                                        <Mail className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                        <p>Connect to your email account to browse messages</p>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {/* Filters */}
                                        <div className="flex items-end gap-3 flex-wrap">
                                            <div className="flex-1 min-w-[140px]">
                                                <Label className="text-sm font-medium text-foreground mb-1.5 block">Folder</Label>
                                                <Select value={selectedFolder} onValueChange={setSelectedFolder}>
                                                    <SelectTrigger>
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {loadingFolders ? (
                                                            <SelectItem value="loading" disabled>Loading...</SelectItem>
                                                        ) : folders.length > 0 ? (
                                                            folders.map(f => <SelectItem key={f} value={f}>{f}</SelectItem>)
                                                        ) : (
                                                            <SelectItem value="INBOX">INBOX</SelectItem>
                                                        )}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="min-w-[120px]">
                                                <Label className="text-sm font-medium text-foreground mb-1.5 block">From</Label>
                                                <Input
                                                    type="date"
                                                    value={dateFrom}
                                                    onChange={e => setDateFrom(e.target.value)}
                                                />
                                            </div>
                                            <div className="min-w-[120px]">
                                                <Label className="text-sm font-medium text-foreground mb-1.5 block">To</Label>
                                                <Input
                                                    type="date"
                                                    value={dateTo}
                                                    onChange={e => setDateTo(e.target.value)}
                                                />
                                            </div>
                                            <div className="flex-1 min-w-[160px]">
                                                <Label className="text-sm font-medium text-foreground mb-1.5 block">Search</Label>
                                                <div className="relative">
                                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                                    <Input
                                                        placeholder="Search sender or subject..."
                                                        value={searchQuery}
                                                        onChange={e => setSearchQuery(e.target.value)}
                                                        className="pl-9"
                                                    />
                                                </div>
                                            </div>
                                            <Button
                                                onClick={handleBrowse}
                                                disabled={loadingEmails}
                                            >
                                                {loadingEmails ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Browse'}
                                            </Button>
                                        </div>

                                        {/* Email List */}
                                        {emails.length > 0 ? (
                                            <>
                                                <div className="flex items-center justify-between">
                                                    <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
                                                        <Checkbox
                                                            checked={selectedIds.size > 0 && selectedIds.size === emails.filter(e => !e.already_extracted).length}
                                                            onCheckedChange={toggleAll}
                                                        />
                                                        Select all new ({emails.filter(e => !e.already_extracted).length})
                                                    </label>
                                                    <Button
                                                        onClick={handleExtract}
                                                        disabled={extracting || selectedIds.size === 0}
                                                        size="sm"
                                                    >
                                                        {extracting ? (
                                                            <>
                                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                                Extracting...
                                                            </>
                                                        ) : (
                                                            <>
                                                                <Download className="h-4 w-4 mr-2" />
                                                                Extract {selectedIds.size} Emails
                                                            </>
                                                        )}
                                                    </Button>
                                                </div>

                                                {extractResult && (
                                                    <Card className={extractResult.error
                                                        ? 'border-destructive bg-destructive/10'
                                                        : 'bg-muted/50'
                                                    }>
                                                        <CardContent className="py-3 px-4">
                                                            <div className={`flex items-center gap-2 text-sm ${extractResult.error ? 'text-destructive' : 'text-foreground'}`}>
                                                                {extractResult.error ? (
                                                                    <><AlertCircle className="h-4 w-4" /> {extractResult.error}</>
                                                                ) : (
                                                                    <><CheckCircle2 className="h-4 w-4" /> Extracted {extractResult.extracted} emails ({extractResult.skipped} skipped)</>
                                                                )}
                                                            </div>
                                                        </CardContent>
                                                    </Card>
                                                )}

                                                <div className="rounded-md border divide-y divide-border max-h-[520px] overflow-y-auto">
                                                    {emails.map(em => (
                                                        <label
                                                            key={em.message_id}
                                                            className={`flex items-start gap-3 px-4 py-3 hover:bg-muted/50 transition-colors cursor-pointer ${em.already_extracted ? 'opacity-50' : ''
                                                                } ${selectedIds.has(em.message_id) ? 'bg-accent' : ''}`}
                                                        >
                                                            <Checkbox
                                                                checked={selectedIds.has(em.message_id)}
                                                                onCheckedChange={() => toggleEmail(em.message_id)}
                                                                disabled={em.already_extracted}
                                                                className="mt-1"
                                                            />
                                                            <div className="flex-1 min-w-0">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-sm font-medium truncate">{em.subject || '(no subject)'}</span>
                                                                    {em.already_extracted && (
                                                                        <Badge variant="secondary" className="flex-shrink-0">extracted</Badge>
                                                                    )}
                                                                    {em.company_name && (
                                                                        <Badge variant="outline" className="flex-shrink-0">{em.company_name}</Badge>
                                                                    )}
                                                                </div>
                                                                <div className="text-sm text-muted-foreground mt-0.5 truncate">
                                                                    <span className="font-medium">{em.sender}</span>
                                                                    <span className="mx-1">→</span>
                                                                    <span>{em.recipient}</span>
                                                                </div>
                                                                <div className="text-xs text-muted-foreground mt-0.5">
                                                                    {em.date ? new Date(em.date).toLocaleDateString('en-US', {
                                                                        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                                                    }) : 'Unknown date'}
                                                                </div>
                                                            </div>
                                                        </label>
                                                    ))}
                                                </div>
                                            </>
                                        ) : loadingEmails ? (
                                            <div className="flex items-center justify-center py-12">
                                                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                            </div>
                                        ) : (
                                            <div className="text-center py-12 text-muted-foreground">
                                                <p>Select a folder and click <strong>Browse</strong> to view emails</p>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Info Banner */}
                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-start gap-3">
                            <Zap className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-foreground">How to query extracted emails</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Once emails are extracted, go to the <strong>Intel Chat</strong> and ask questions like
                                    &quot;What was the last quote I sent to Acme Corp?&quot; or &quot;Show me emails about the project proposal&quot;.
                                    The system will automatically search your email knowledge base.
                                </p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

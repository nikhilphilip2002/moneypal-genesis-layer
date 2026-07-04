'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { ROLE_LABELS, ROLE_ROUTES, homeRoute, type UserRole } from '@/lib/useUserRole';
import { Card, CardContent } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';

interface UserProfile {
    username: string;
    email: string;
    full_name: string;
    role: UserRole;
}

const MODULE_NAMES: Record<string, string> = {
    '/': 'Executive Dashboard',
    '/macro': 'Macro Intelligence',
    '/competitive': 'Competitive Intelligence',
    '/regulatory': 'Regulatory Intelligence',
    '/admin': 'Platform Administration',
    '/review': 'Intelligence Review',
    '/policy': 'Policy Workspace',
};

function getInitials(name: string): string {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

export default function ProfilePage() {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        auth.me()
            .then((userData: UserProfile) => setUser(userData))
            .catch(() => router.push('/login'))
            .finally(() => setLoading(false));
    }, [router]);

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <span className="text-sm text-muted-foreground animate-pulse">Loading…</span>
            </div>
        );
    }

    if (!user) return null;

    const roleLabel = ROLE_LABELS[user.role] || 'User';
    const modules = (ROLE_ROUTES[user.role] || []).map((route) => MODULE_NAMES[route] || route);

    return (
        <div className="h-full overflow-auto">
            <div className="mx-auto max-w-3xl px-6 py-10">

                {/* Back link */}
                <Link
                    href={homeRoute(user.role)}
                    className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-8"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back
                </Link>

                {/* Page title */}
                <div className="mb-8">
                    <h1 className="font-headline text-xl font-semibold tracking-tight">Account</h1>
                    <p className="text-sm text-muted-foreground mt-0.5">Your Genesis Console access profile.</p>
                </div>

                <Card className="border-border/70">
                    <CardContent className="p-0">
                        <div className="grid md:grid-cols-[220px_1fr]">

                            {/* Left — identity panel */}
                            <div className="flex flex-col items-center gap-4 border-b md:border-b-0 md:border-r border-border/60 p-8">
                                <Avatar className="h-16 w-16">
                                    <AvatarFallback className="bg-foreground text-background text-lg font-semibold tracking-tight">
                                        {getInitials(user.full_name || user.username)}
                                    </AvatarFallback>
                                </Avatar>

                                <div className="text-center space-y-1">
                                    <p className="text-sm font-medium leading-none">
                                        {user.full_name || user.username}
                                    </p>
                                    <p className="text-xs text-muted-foreground">@{user.username}</p>
                                </div>

                                <Badge variant="default" className="text-[10px] px-2 py-0.5 font-medium">
                                    {roleLabel}
                                </Badge>

                                <Separator className="w-full" />

                                <div className="w-full space-y-3 text-xs">
                                    <div>
                                        <p className="text-muted-foreground mb-0.5">Email</p>
                                        <p className="font-medium">{user.email}</p>
                                    </div>
                                    <div>
                                        <p className="text-muted-foreground mb-0.5">Username</p>
                                        <p className="font-mono font-medium">{user.username}</p>
                                    </div>
                                </div>
                            </div>

                            {/* Right — access summary */}
                            <div className="p-8">
                                <h2 className="text-sm font-semibold mb-6">Module access</h2>
                                <div className="space-y-2">
                                    {modules.map((module) => (
                                        <div
                                            key={module}
                                            className="flex items-center gap-2.5 rounded-lg border border-border/60 bg-muted/40 px-3.5 py-2.5 text-sm"
                                        >
                                            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                                            {module}
                                        </div>
                                    ))}
                                </div>
                                <p className="mt-6 text-xs text-muted-foreground">
                                    Access is provisioned by the Moneypal administrator. Contact your administrator to change your role.
                                </p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

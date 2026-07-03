'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Save } from 'lucide-react';
import Link from 'next/link';

interface UserProfile {
    id: number;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    full_name: string;
    is_staff: boolean;
    role?: string;
    date_joined: string;
}

function getRoleLabel(user: UserProfile): string {
    if (user.role === 'admin') return 'Administrator';
    if (user.role === 'manager') return 'Manager';
    return 'User';
}

function getInitials(name: string): string {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    });
}

export default function ProfilePage() {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const router = useRouter();

    useEffect(() => {
        auth.me()
            .then((userData: UserProfile) => {
                setUser(userData);
                setFullName(userData.full_name || '');
                setEmail(userData.email || '');
            })
            .catch(() => router.push('/login'))
            .finally(() => setLoading(false));
    }, [router]);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setSaving(true);
        try {
            await auth.updateProfile(fullName, email);
            setSuccess('Profile updated.');
            const userData = await auth.me();
            setUser(userData);
        } catch (err: any) {
            setError(err.message || 'Failed to update profile.');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <span className="text-sm text-muted-foreground animate-pulse">Loading…</span>
            </div>
        );
    }

    if (!user) return null;

    const roleLabel = getRoleLabel(user);
    const isElevated = user.is_staff || user.role === 'manager' || user.role === 'admin';

    return (
        <div className="h-full overflow-auto">
            <div className="mx-auto max-w-3xl px-6 py-10">

                {/* Back link */}
                <Link
                    href="/"
                    className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-8"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Dashboard
                </Link>

                {/* Page title */}
                <div className="mb-8">
                    <h1 className="text-xl font-semibold tracking-tight">Account</h1>
                    <p className="text-sm text-muted-foreground mt-0.5">Manage your personal information.</p>
                </div>

                <Card className="border-border/70">
                    <CardContent className="p-0">
                        <div className="grid md:grid-cols-[220px_1fr]">

                            {/* Left — identity panel */}
                            <div className="flex flex-col items-center gap-4 border-b md:border-b-0 md:border-r border-border/60 p-8">
                                <Avatar className="h-16 w-16">
                                    <AvatarFallback className="bg-foreground text-background text-lg font-semibold tracking-tight">
                                        {getInitials(fullName || user.username)}
                                    </AvatarFallback>
                                </Avatar>

                                <div className="text-center space-y-1">
                                    <p className="text-sm font-medium leading-none">
                                        {fullName || user.username}
                                    </p>
                                    <p className="text-xs text-muted-foreground">@{user.username}</p>
                                </div>

                                <Badge
                                    variant={isElevated ? 'default' : 'secondary'}
                                    className="text-[10px] px-2 py-0.5 font-medium"
                                >
                                    {roleLabel}
                                </Badge>

                                <Separator className="w-full" />

                                <div className="w-full space-y-3 text-xs">
                                    <div>
                                        <p className="text-muted-foreground mb-0.5">Member since</p>
                                        <p className="font-medium">{formatDate(user.date_joined)}</p>
                                    </div>
                                    <div>
                                        <p className="text-muted-foreground mb-0.5">Username</p>
                                        <p className="font-mono font-medium">{user.username}</p>
                                    </div>
                                </div>
                            </div>

                            {/* Right — edit form */}
                            <div className="p-8">
                                <h2 className="text-sm font-semibold mb-6">Edit profile</h2>

                                <form onSubmit={handleSave} className="space-y-5">
                                    {error && (
                                        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-xs text-destructive">
                                            {error}
                                        </div>
                                    )}
                                    {success && (
                                        <div className="rounded-md border border-border bg-muted px-3 py-2.5 text-xs text-foreground">
                                            {success}
                                        </div>
                                    )}

                                    <div className="space-y-1.5">
                                        <Label htmlFor="fullName" className="text-xs font-medium">
                                            Full name
                                        </Label>
                                        <Input
                                            id="fullName"
                                            type="text"
                                            placeholder="Your full name"
                                            value={fullName}
                                            onChange={(e) => setFullName(e.target.value)}
                                            className="h-9 text-sm"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <Label htmlFor="email" className="text-xs font-medium">
                                            Email address
                                        </Label>
                                        <Input
                                            id="email"
                                            type="email"
                                            placeholder="you@example.com"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            className="h-9 text-sm"
                                        />
                                    </div>

                                    <div className="pt-2">
                                        <Button
                                            type="submit"
                                            disabled={saving}
                                            size="sm"
                                            className="gap-1.5"
                                        >
                                            <Save className="h-3.5 w-3.5" />
                                            {saving ? 'Saving…' : 'Save changes'}
                                        </Button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

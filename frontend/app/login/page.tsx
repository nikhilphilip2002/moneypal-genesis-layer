'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { clearUserRoleCache, homeRoute, type UserRole } from '@/lib/useUserRole';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Image from 'next/image';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await auth.login(username, password);
      localStorage.setItem('token', data.access);
      localStorage.setItem('refreshToken', data.refresh);
      clearUserRoleCache();
      const me = await auth.me().catch(() => null);
      const landing = me?.role ? homeRoute(me.role as UserRole) : '/';
      router.replace(landing);
      router.refresh();
    } catch (err: any) {
      setError(err.message || 'Invalid username or password.');
      setLoading(false);
    }
  };

  return (
    <div className="auth-page px-4 py-6 sm:px-6">
      <div className="glass-strong glass-in rounded-3xl w-full max-w-md p-6 sm:p-8 space-y-5 sm:space-y-6 overflow-hidden">

        {/* Joint Moneypal × GICC branding */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex items-center gap-3">
            <div className="relative w-32 h-16 overflow-hidden">
              <Image
                src="/moneypal.png"
                alt="Moneypal"
                fill
                className="object-contain"
                priority
              />
            </div>
            <span className="text-xl font-light text-muted-foreground">×</span>
            <div className="relative w-16 h-16 overflow-hidden">
              <Image
                src="/gicc.png"
                alt="GICC"
                fill
                className="object-contain p-1"
                priority
              />
            </div>
          </div>
          <div className="space-y-1">
            <h1 className="font-headline text-2xl font-semibold tracking-tight text-foreground">Genesis Intelligence Console</h1>
            <p className="text-sm text-muted-foreground">
              A joint onboarding environment for Moneypal Digital Services and GICC
            </p>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="px-4 py-3 rounded-xl bg-destructive/10 border border-destructive/25 text-sm text-destructive glass-in-fast">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={loading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />
          </div>
          <Button type="submit" className="w-full h-12 text-base" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          Access is provisioned by Moneypal for GICC leadership.
        </p>
      </div>
    </div>
  );
}

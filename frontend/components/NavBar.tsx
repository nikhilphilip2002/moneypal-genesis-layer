'use client';

import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { auth, clearLocalAuthState } from '@/lib/api';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ThemeToggle } from '@/components/ThemeToggle';

const adminTopNavItems = [
  { href: '/', label: 'Dashboard' },
  { href: '/curiosity-graph', label: 'Curiosity Graph' },
];

const standardNavItems = [
  { href: '/companies', label: 'Companies' },
  { href: '/knowledge-base', label: 'Knowledge Base' },
  { href: '/general-chat', label: 'General Chat' },
];

function getInitials(name: string): string {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) || 'U';
}

export default function NavBar() {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [role, setRole] = useState<string>('standard');
  const [username, setUsername] = useState('');
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    auth.me()
      .then(user => {
        const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
        setRole(userRole);
        setUsername(user.username || 'User');
        setIsLoggedIn(true);
      })
      .catch(() => {
        setIsLoggedIn(false);
        setRole('standard');
      })
      .finally(() => setIsInitialized(true));
  }, [pathname]);

  const handleLogout = async () => {
    await auth.logout().catch(() => null);
    clearLocalAuthState();
    setIsLoggedIn(false);
    setRole('standard');
    window.location.href = '/login';
  };

  if (pathname === '/login' || pathname === '/register' || pathname === '/callback') return null;

  if (!isInitialized) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-3.5 w-28 rounded bg-muted animate-pulse" />
      </div>
    );
  }

  const visibleNavItems = (role === 'admin' || role === 'manager')
    ? adminTopNavItems
    : standardNavItems;

  const roleLabel = role === 'admin' ? 'Administrator' : role === 'manager' ? 'Manager' : 'User';

  return (
    <div className="flex flex-1 items-center justify-between">
      <nav className="flex items-center gap-0.5">
        {visibleNavItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-200',
              pathname === item.href
                ? '[background:rgba(255,255,255,0.75)] dark:[background:rgba(255,255,255,0.10)] [backdrop-filter:saturate(180%)_blur(16px)] border border-white/80 dark:border-white/18 [border-top-color:rgba(255,255,255,0.95)] shadow-[0_2px_8px_rgba(221,122,58,0.10),0_1px_0_rgba(255,255,255,0.85)_inset] text-foreground font-medium'
                : 'text-muted-foreground hover:[background:rgba(255,255,255,0.50)] dark:hover:[background:rgba(255,255,255,0.07)] hover:text-foreground'
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-2.5">
        <ThemeToggle />
        {isLoggedIn && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 rounded-xl border border-white/75 dark:border-white/14 [border-top-color:rgba(255,255,255,0.95)] dark:[border-top-color:rgba(255,255,255,0.22)] [background:rgba(255,255,255,0.50)] dark:[background:rgba(255,255,255,0.07)] [backdrop-filter:saturate(180%)_blur(16px)] [-webkit-backdrop-filter:saturate(180%)_blur(16px)] px-1.5 py-1 transition-all duration-200 hover:[background:rgba(255,255,255,0.70)] dark:hover:[background:rgba(255,255,255,0.12)] shadow-[0_2px_8px_rgba(221,122,58,0.08),0_1px_0_rgba(255,255,255,0.80)_inset] focus-visible:outline-none">
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="bg-foreground text-background text-[10px] font-semibold">
                    {getInitials(username)}
                  </AvatarFallback>
                </Avatar>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <div className="px-2 py-2">
                <p className="text-sm font-medium leading-none">{username}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{roleLabel}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-sm cursor-pointer"
                onClick={() => router.push('/profile')}
              >
                Edit profile
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-sm cursor-pointer"
                onClick={handleLogout}
              >
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  );
}

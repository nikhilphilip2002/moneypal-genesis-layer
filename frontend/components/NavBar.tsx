'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { auth } from '@/lib/api';
import { ROLE_LABELS, ROLE_ROUTES, clearUserRoleCache, type UserRole } from '@/lib/useUserRole';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ThemeToggle } from '@/components/ThemeToggle';

const NAV_LABELS: Record<string, string> = {
  '/': 'Dashboard',
  '/macro': 'Macro',
  '/competitive': 'Competitive',
  '/regulatory': 'Regulatory',
  '/admin': 'Administration',
  '/review': 'Review',
  '/policy': 'Policy',
};

function getInitials(name: string): string {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) || 'U';
}

export default function NavBar() {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [role, setRole] = useState<UserRole | null>(null);
  const [username, setUsername] = useState('');
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    auth.me()
      .then(user => {
        setRole((user.role as UserRole) || null);
        setUsername(user.full_name || user.username || 'User');
        setIsLoggedIn(true);
      })
      .catch(() => {
        setIsLoggedIn(false);
        setRole(null);
      })
      .finally(() => setIsInitialized(true));
  }, [pathname]);

  const handleLogout = async () => {
    await auth.logout().catch(() => null);
    clearUserRoleCache();
    setIsLoggedIn(false);
    setRole(null);
    window.location.href = '/login';
  };

  if (pathname === '/login') return null;

  if (!isInitialized) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-3.5 w-28 rounded bg-muted animate-pulse" />
      </div>
    );
  }

  const visibleNavItems = role
    ? ROLE_ROUTES[role].map((href) => ({ href, label: NAV_LABELS[href] || href }))
    : [];

  const roleLabel = role ? ROLE_LABELS[role] : 'User';

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
                ? 'bg-accent text-accent-foreground border border-border/40 font-semibold'
                : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-2.5">
        <div className="hidden h-8 w-8 items-center justify-center overflow-hidden sm:flex">
          <Image src="/gicc.png" alt="GICC" width={32} height={32} className="h-7 w-7 object-contain" />
        </div>
        <ThemeToggle />
        {isLoggedIn && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 rounded-xl border border-white/75 dark:border-white/14 [border-top-color:rgba(255,255,255,0.95)] dark:[border-top-color:rgba(255,255,255,0.22)] [background:rgba(255,255,255,0.50)] dark:[background:rgba(255,255,255,0.07)] [backdrop-filter:saturate(180%)_blur(16px)] [-webkit-backdrop-filter:saturate(180%)_blur(16px)] px-1.5 py-1 transition-all duration-200 hover:[background:rgba(255,255,255,0.70)] dark:hover:[background:rgba(255,255,255,0.12)] shadow-[0_2px_8px_rgba(0,93,170,0.08),0_1px_0_rgba(255,255,255,0.80)_inset] focus-visible:outline-none">
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
                View profile
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

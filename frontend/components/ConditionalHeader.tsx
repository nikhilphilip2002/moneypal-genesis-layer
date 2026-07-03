'use client';

import { usePathname } from 'next/navigation';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import NavBar from '@/components/NavBar';

const AUTH_ROUTES = ['/login'];

export default function ConditionalHeader() {
  const pathname = usePathname();
  if (AUTH_ROUTES.includes(pathname)) return null;

  return (
    <header className="glass-vibrancy hidden md:flex h-14 shrink-0 items-center gap-2 px-4 sticky top-0 z-20 rounded-none">
      <SidebarTrigger className="-ml-1 hover:bg-white/30 dark:hover:bg-white/8 rounded-lg transition-all duration-200" />
      <Separator orientation="vertical" className="mr-2 h-4 opacity-30" />
      <NavBar />
    </header>
  );
}

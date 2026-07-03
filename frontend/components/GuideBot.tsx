'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Bot } from 'lucide-react';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { GuidePanel } from '@/components/guide/GuidePanel';
import { useUserRole } from '@/lib/useUserRole';
import { cn } from '@/lib/utils';

const GUIDE_SEEN_KEY = 'aroha_guide_seen_v1';
const HIDDEN_PATHS = ['/login', '/register', '/callback'];

export default function GuideBot() {
  const pathname = usePathname();
  const { role } = useUserRole();
  const [open, setOpen] = useState(false);
  const [pulse, setPulse] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const seen = localStorage.getItem(GUIDE_SEEN_KEY);
    if (!seen) {
      const t = setTimeout(() => {
        setOpen(true);
        localStorage.setItem(GUIDE_SEEN_KEY, '1');
      }, 1200);
      return () => clearTimeout(t);
    } else {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 3000);
      return () => clearTimeout(t);
    }
  }, []);

  if (!mounted) return null;
  if (HIDDEN_PATHS.includes(pathname)) return null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Open guide"
        className={cn(
          'fixed right-6 z-40 flex items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 active:scale-95',
          'bottom-[calc(88px+env(safe-area-inset-bottom,0px)+16px)] md:bottom-6',
        )}
        style={{ height: 52, width: 52 }}
      >
        <Bot className="h-6 w-6" />
        {pulse && (
          <span className="absolute inset-0 rounded-full animate-ping bg-primary/40" />
        )}
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full max-w-[440px] p-0 flex flex-col">
          <GuidePanel role={role} onClose={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </>
  );
}

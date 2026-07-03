'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Home, BarChart3, BookOpen, MessageCircle, User, Plus } from 'lucide-react'
import { useUserRole } from '@/lib/useUserRole'
import { cn } from '@/lib/utils'

type TabDef = {
  href: string
  label: string
  icon: typeof Home
  matchPrefix?: string
}

function tabsForRole(role: 'admin' | 'manager' | 'standard' | null): TabDef[] {
  const slot2: TabDef =
    role === 'admin' || role === 'manager'
      ? { href: '/ibridge-analysis', label: 'Insights', icon: BarChart3 }
      : { href: '/knowledge-base', label: 'Knowledge', icon: BookOpen, matchPrefix: '/knowledge-base' }

  return [
    { href: '/', label: 'Home', icon: Home },
    slot2,
    { href: '/general-chat?new=1', label: 'New', icon: Plus, matchPrefix: '__fab__' },
    { href: '/general-chat', label: 'Chat', icon: MessageCircle, matchPrefix: '/general-chat' },
    { href: '/profile', label: 'Me', icon: User },
  ]
}

function isActive(tab: TabDef, pathname: string): boolean {
  if (tab.matchPrefix === '__fab__') return false
  if (tab.matchPrefix) return pathname.startsWith(tab.matchPrefix)
  if (tab.href === '/') return pathname === '/'
  return pathname === tab.href || pathname.startsWith(`${tab.href}/`)
}

const AUTH_ROUTES = new Set(['/login', '/register', '/callback'])

export default function MobileTabBar() {
  const pathname = usePathname()
  const router = useRouter()
  const { role } = useUserRole()
  if (AUTH_ROUTES.has(pathname)) return null
  const tabs = tabsForRole(role)

  return (
    <nav
      aria-label="Primary"
      className="md:hidden fixed inset-x-3 z-30 grid grid-cols-5 items-center rounded-3xl border border-white/60 bg-white/75 backdrop-blur-xl shadow-[0_12px_30px_rgba(31,26,20,0.12)] dark:bg-black/55 dark:border-white/10"
      style={{
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)',
        height: '64px',
      }}
    >
      {tabs.map((tab, i) => {
        const active = isActive(tab, pathname)
        const isFab = tab.matchPrefix === '__fab__'

        if (isFab) {
          return (
            <button
              key={i}
              type="button"
              onClick={() => router.push(tab.href)}
              aria-label={tab.label}
              className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-primary to-[#F5A06C] text-white shadow-[0_10px_22px_rgba(221,122,58,0.45)] active:scale-95 transition-transform"
            >
              <tab.icon className="h-5 w-5" strokeWidth={2.5} />
            </button>
          )
        }

        return (
          <Link
            key={i}
            href={tab.href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'flex flex-col items-center justify-center gap-0.5 text-[10px] font-semibold transition-colors',
              active ? 'text-primary' : 'text-muted-foreground'
            )}
          >
            <tab.icon className={cn('h-5 w-5', active && 'drop-shadow-[0_2px_4px_rgba(221,122,58,0.35)]')} strokeWidth={active ? 2.4 : 1.9} />
            <span>{tab.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

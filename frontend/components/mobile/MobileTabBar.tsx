'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, TrendingUp, Building, Scale, Settings2, ClipboardCheck, FileText, User } from 'lucide-react'
import { useUserRole, ROLE_ROUTES, type UserRole } from '@/lib/useUserRole'
import { cn } from '@/lib/utils'

type TabDef = {
  href: string
  label: string
  icon: typeof LayoutDashboard
}

const MODULE_TABS: TabDef[] = [
  { href: '/', label: 'Home', icon: LayoutDashboard },
  { href: '/macro', label: 'Macro', icon: TrendingUp },
  { href: '/competitive', label: 'Compete', icon: Building },
  { href: '/regulatory', label: 'Regulatory', icon: Scale },
  { href: '/admin', label: 'Admin', icon: Settings2 },
  { href: '/review', label: 'Review', icon: ClipboardCheck },
  { href: '/policy', label: 'Policy', icon: FileText },
]

function tabsForRole(role: UserRole | null): TabDef[] {
  const allowed = role ? ROLE_ROUTES[role] : []
  const tabs = MODULE_TABS.filter((t) => allowed.includes(t.href))
  return [...tabs, { href: '/profile', label: 'Me', icon: User }]
}

function isActive(tab: TabDef, pathname: string): boolean {
  if (tab.href === '/') return pathname === '/'
  return pathname === tab.href || pathname.startsWith(`${tab.href}/`)
}

const AUTH_ROUTES = new Set(['/login'])

export default function MobileTabBar() {
  const pathname = usePathname()
  const { role } = useUserRole()
  if (AUTH_ROUTES.has(pathname)) return null
  const tabs = tabsForRole(role)

  return (
    <nav
      aria-label="Primary"
      className="md:hidden fixed inset-x-3 z-30 grid items-center rounded-3xl border border-white/60 bg-white/75 backdrop-blur-xl shadow-[0_12px_30px_rgba(0,69,129,0.12)] dark:bg-black/55 dark:border-white/10"
      style={{
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)',
        height: '64px',
        gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))`,
      }}
    >
      {tabs.map((tab, i) => {
        const active = isActive(tab, pathname)
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
            <tab.icon className={cn('h-5 w-5', active && 'drop-shadow-[0_2px_4px_rgba(0,93,170,0.35)]')} strokeWidth={active ? 2.4 : 1.9} />
            <span>{tab.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

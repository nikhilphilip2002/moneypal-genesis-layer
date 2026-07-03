'use client'

import { usePathname, useRouter } from 'next/navigation'
import Image from 'next/image'
import { ChevronLeft, Bell } from 'lucide-react'

// Map route prefixes to their mobile top-bar title.
const TITLES: Array<[string | RegExp, string]> = [
  [/^\/$/, 'Moneypal Genesis'],
  [/^\/macro/, 'Macro Intelligence'],
  [/^\/competitive/, 'Competitive Intel'],
  [/^\/regulatory/, 'Regulatory Intel'],
  [/^\/admin/, 'Administration'],
  [/^\/review/, 'Intelligence Review'],
  [/^\/policy/, 'Policy Workspace'],
  [/^\/profile/, 'Profile'],
]

const ROOT_PATHS = new Set(['/', '/macro', '/competitive', '/regulatory', '/admin', '/review', '/policy', '/profile'])

function titleFor(pathname: string): string {
  for (const [pattern, title] of TITLES) {
    if (typeof pattern === 'string' ? pathname === pattern : pattern.test(pathname)) return title
  }
  return 'Moneypal Genesis'
}

const AUTH_ROUTES = new Set(['/login'])

export default function MobileTopNav() {
  const pathname = usePathname()
  const router = useRouter()
  if (AUTH_ROUTES.has(pathname)) return null
  const title = titleFor(pathname)
  const showBack = !ROOT_PATHS.has(pathname)

  return (
    <header
      className="md:hidden sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-white/40 bg-white/70 px-3 backdrop-blur-xl dark:bg-black/45 dark:border-white/10"
      style={{
        paddingTop: 'calc(env(safe-area-inset-top, 0px) + 8px)',
        paddingBottom: '10px',
      }}
    >
      <div className="flex items-center gap-2 min-w-0">
        {showBack ? (
          <button
            type="button"
            onClick={() => router.back()}
            aria-label="Back"
            className="grid h-9 w-9 place-items-center rounded-xl border border-white/60 bg-white/60 backdrop-blur-sm active:scale-95 transition-transform dark:bg-white/5 dark:border-white/10"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
        ) : (
          <div className="relative h-10 w-20 shrink-0 overflow-hidden">
            <Image src="/moneypal.png" alt="Moneypal" fill className="object-contain p-0.5" priority />
          </div>
        )}
        <h1 className="truncate text-[15px] font-semibold tracking-tight">{title}</h1>
      </div>

      <button
        type="button"
        aria-label="Notifications"
        className="grid h-9 w-9 place-items-center rounded-xl border border-white/60 bg-white/60 backdrop-blur-sm active:scale-95 transition-transform dark:bg-white/5 dark:border-white/10"
      >
        <Bell className="h-4 w-4" />
      </button>
    </header>
  )
}

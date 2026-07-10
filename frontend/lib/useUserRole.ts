'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { auth } from '@/lib/api'

// admin = Moneypal Administrator (full platform)
// gicc_admin = GICC Administrator (dashboard + competitive + regulatory)
// gicc_policy = GICC Policy Maker (regulatory + competitive)
// gicc_director = GICC Director (executive dashboard only)
export type UserRole = 'admin' | 'gicc_admin' | 'gicc_policy' | 'gicc_director'

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Moneypal Administrator',
  gicc_admin: 'GICC Administrator',
  gicc_policy: 'GICC Policy Maker',
  gicc_director: 'GICC Director',
}

// Routes each role may see, in nav order (first entry = landing page).
// Role workspaces from the developer brief: admin → platform administration,
// gicc_admin → intelligence review, gicc_policy → policy formulation.
export const ROLE_ROUTES: Record<UserRole, string[]> = {
  admin: ['/', '/macro', '/competitive', '/regulatory', '/admin'],
  gicc_admin: ['/', '/competitive', '/regulatory', '/review'],
  gicc_policy: ['/regulatory', '/competitive', '/policy'],
  gicc_director: ['/'],
}

// Landing page after login, per role.
export function homeRoute(role: UserRole): string {
  return ROLE_ROUTES[role][0]
}

export function canAccess(role: UserRole, route: string): boolean {
  return ROLE_ROUTES[role].includes(route)
}

// Module-level cache so multiple consumers (AppSidebar, NavBar, …) don't
// each re-fetch /me on every navigation.
let cachedRole: UserRole | null = null
let inflight: Promise<UserRole | null> | null = null

function fetchRole(): Promise<UserRole | null> {
  if (cachedRole) return Promise.resolve(cachedRole)
  if (inflight) return inflight
  inflight = auth
    .me()
    .then((user: { role?: string }) => {
      const role = (user.role as UserRole) || null
      cachedRole = role
      return role
    })
    .catch(() => null)
    .finally(() => {
      inflight = null
    })
  return inflight
}

export function clearUserRoleCache() {
  cachedRole = null
}

export function useUserRole(): { role: UserRole | null; ready: boolean } {
  const pathname = usePathname()
  const [role, setRole] = useState<UserRole | null>(cachedRole)
  const [ready, setReady] = useState<boolean>(cachedRole !== null)

  // Re-runs on client-side navigation (e.g. right after login) so consumers
  // like AppSidebar pick up the role without a hard refresh. fetchRole caches,
  // so this only hits /me while the role is still unknown.
  useEffect(() => {
    if (typeof window === 'undefined') return
    let cancelled = false
    fetchRole().then((r) => {
      if (!cancelled) {
        setRole(r)
        setReady(true)
      }
    })
    return () => {
      cancelled = true
    }
  }, [pathname])

  return { role, ready }
}

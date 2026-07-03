'use client'

import { useEffect, useState } from 'react'
import { auth } from '@/lib/api'

export type UserRole = 'admin' | 'manager' | 'standard'

// Module-level cache so multiple consumers (AppSidebar, MobileShell, …) don't
// each re-fetch /me on every navigation.
let cachedRole: UserRole | null = null
let inflight: Promise<UserRole> | null = null

function fetchRole(): Promise<UserRole> {
  if (cachedRole) return Promise.resolve(cachedRole)
  if (inflight) return inflight
  inflight = auth
    .me()
    .then((user: { role?: string; is_staff?: boolean }) => {
      const role = (user.role as UserRole) || (user.is_staff ? 'admin' : 'standard')
      cachedRole = role
      return role
    })
    .catch(() => {
      cachedRole = 'standard'
      return 'standard' as UserRole
    })
    .finally(() => {
      inflight = null
    })
  return inflight
}

export function clearUserRoleCache() {
  cachedRole = null
}

export function useUserRole(): { role: UserRole | null; ready: boolean } {
  const [role, setRole] = useState<UserRole | null>(cachedRole)
  const [ready, setReady] = useState<boolean>(cachedRole !== null)

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
  }, [])

  return { role, ready }
}

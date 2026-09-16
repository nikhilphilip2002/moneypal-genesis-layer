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

export function isUserRole(role: string): role is UserRole {
  return Object.prototype.hasOwnProperty.call(ROLE_LABELS, role)
}

// Routes each role may see, in nav order (first entry = landing page).
// Role workspaces from the developer brief: admin → platform administration,
// gicc_admin → intelligence review, gicc_policy → policy formulation.
// `/ask` (Genesis NLQ) is loan-book analytics, so it goes to the two GICC business roles
// and to platform admin — not to gicc_policy, whose workspace is regulatory text rather
// than the portfolio. Kept off the front of every list: homeRoute() lands on entry [0].
export const ROLE_ROUTES: Record<UserRole, string[]> = {
  admin: ['/', '/workbench', '/ask', '/macro', '/competitive', '/regulatory', '/admin'],
  gicc_admin: ['/', '/workbench', '/ask', '/competitive', '/regulatory', '/review'],
  gicc_policy: ['/regulatory', '/competitive', '/policy', '/workbench'],
  gicc_director: ['/', '/workbench', '/ask'],
}

// Landing page after login, per role. The Workbench is the primary surface now, so it is
// the landing page wherever the role can see it; otherwise fall back to the role's first
// permitted route.
export function homeRoute(role: UserRole): string {
  const routes = ROLE_ROUTES[role]
  return routes.includes('/workbench') ? '/workbench' : routes[0]
}

export function canAccess(role: UserRole, route: string): boolean {
  return ROLE_ROUTES[role].includes(route)
}

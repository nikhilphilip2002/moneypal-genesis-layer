'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { auth } from '@/lib/api';
import { canAccess, homeRoute, isUserRole } from '@/lib/useUserRole';

export function useRequireAuth(route: string): boolean {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    let active = true;

    auth
      .me()
      .then((user) => {
        if (!active) return;
        if (!isUserRole(user.role)) {
          router.replace('/login');
          return;
        }
        if (!canAccess(user.role, route)) {
          router.replace(homeRoute(user.role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => {
        if (active) router.replace('/login');
      });

    return () => {
      active = false;
    };
  }, [route, router]);

  return authorized;
}

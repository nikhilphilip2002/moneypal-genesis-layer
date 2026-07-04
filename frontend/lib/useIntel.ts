'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type IntelFetch<T> = {
  data: T | null;
  loading: boolean;
  error: boolean;
  reload: () => void;
};

// Version segment invalidates session caches when brief formats change.
const PREFIX = 'intel.v3:';

function readCache<T>(key: string): T | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeCache(key: string, data: unknown) {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(PREFIX + key, JSON.stringify(data));
  } catch {
    // storage full/unavailable — caching is best-effort
  }
}

// Fetch-state hook shared by the intelligence pages, backed by sessionStorage
// so navigating between tabs re-renders instantly instead of resetting to
// skeletons. `key` must be unique per endpoint. reload() bypasses the cache.
// `live: true` shows the cached value instantly but always refetches in the
// background — for status/health data that must never be served stale.
export function useIntel<T>(
  key: string,
  fetcher: (refresh?: boolean) => Promise<T>,
  options?: { live?: boolean },
): IntelFetch<T> {
  const live = options?.live ?? false;
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: boolean }>(() => {
    const cached = readCache<T>(key);
    return { data: cached, loading: cached === null, error: false };
  });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(
    (force = false) => {
      const cached = readCache<T>(key);
      if (!force && cached !== null && !live) {
        setState({ data: cached, loading: false, error: false });
        return;
      }
      // Live mode keeps showing the cached value while revalidating.
      setState((prev) => ({ data: live ? (prev.data ?? cached) : null, loading: !(live && cached !== null), error: false }));
      fetcherRef
        .current(force)
        .then((data) => {
          writeCache(key, data);
          setState({ data, loading: false, error: false });
        })
        .catch(() => setState((prev) => ({ data: live ? prev.data : null, loading: false, error: !live || prev.data === null })));
    },
    [key, live],
  );

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: () => load(true) };
}

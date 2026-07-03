'use client';

import { useCallback, useEffect, useState } from 'react';

export type IntelFetch<T> = {
  data: T | null;
  loading: boolean;
  error: boolean;
  reload: () => void;
};

// Minimal fetch-state hook shared by the intelligence pages. The fetcher is
// captured on first render — pages pass stable module-level API functions.
export function useIntel<T>(fetcher: () => Promise<T>): IntelFetch<T> {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: boolean }>({
    data: null,
    loading: true,
    error: false,
  });
  const load = useCallback(() => {
    setState({ data: null, loading: true, error: false });
    fetcher()
      .then((data) => setState({ data, loading: false, error: false }))
      .catch(() => setState({ data: null, loading: false, error: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  return { ...state, reload: load };
}

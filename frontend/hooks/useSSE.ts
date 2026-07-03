// hooks/useSSE.ts
import { getToken } from '@/lib/api';
import { useEffect, useState } from 'react';

export function useAgentLogs(jobId: string) {
  const [logs, setLogs] = useState<any[]>([]);
  const [status, setStatus] = useState<'idle' | 'streaming' | 'complete' | 'error'>('idle');

  useEffect(() => {
    if (!jobId) return;

    const token = getToken();
    const queryString = token ? `?token=${encodeURIComponent(token)}` : '';
    const eventSource = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/agent/logs/${jobId}/${queryString}`,
      { withCredentials: true }
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLogs((prev) => [...prev, data]);
        
        if (data.status === 'completed' || data.status === 'failed') {
          setStatus(data.status === 'completed' ? 'complete' : 'error');
          eventSource.close();
        }
      } catch (e) {
        console.error("Failed to parse SSE event", e);
      }
    };

    eventSource.onopen = () => setStatus('streaming');
    eventSource.onerror = () => {
      setStatus('error');
      eventSource.close();
    };

    return () => eventSource.close();
  }, [jobId]);

  return { logs, status };
}

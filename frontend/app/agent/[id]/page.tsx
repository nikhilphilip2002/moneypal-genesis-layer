'use client';

import { useParams } from 'next/navigation';
import { useAgentLogs } from '@/hooks/useSSE';
import { useEffect } from 'react';
import { auth } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import { ScrollArea } from '@/components/ui/scroll-area';

export default function AgentLiveView() {
  const params = useParams();
  const jobId = params.id as string;
  const { logs, status } = useAgentLogs(jobId);

  useEffect(() => {
    auth.me().catch(() => {
      window.location.href = '/login';
    });
  }, []);

  const statusConfig = {
    streaming: { variant: 'secondary' as const, label: 'STREAMING', pulse: true },
    complete: { variant: 'success' as const, label: 'COMPLETE', pulse: false },
    error: { variant: 'destructive' as const, label: 'ERROR', pulse: false },
    pending: { variant: 'secondary' as const, label: 'PENDING', pulse: false },
  };

  const currentStatus = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">Agent Live Monitor</h1>
        <p className="text-muted-foreground">Monitor agent execution in real-time</p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Status:</span>
          <Badge variant={currentStatus.variant} className={currentStatus.pulse ? 'animate-pulse' : ''}>
            {currentStatus.label}
          </Badge>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Live Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[600px] w-full rounded-md border bg-muted p-4">
            <div className="space-y-6">
              {logs.length === 0 && (
                <div className="text-muted-foreground italic">Waiting for logs...</div>
              )}
              {logs.map((log, index) => (
                <div key={index} className="border-b border-border pb-4 last:border-0 last:pb-0">
                  <div className="flex items-center gap-2 mb-2 opacity-80 font-mono">
                    <span className="text-xs text-muted-foreground">[{new Date(log.timestamp || Date.now()).toLocaleTimeString()}]</span>
                    <span className="text-xs text-blue-400 font-bold uppercase tracking-wider">[{log.node || 'agent'}]</span>
                  </div>
                  <div className="text-foreground pl-1">
                    <MarkdownRenderer 
                      content={
                        log.message || 
                        (log.error_message ? `**Error:** ${log.error_message}` : `\`\`\`json\n${JSON.stringify(log, null, 2)}\n\`\`\``)
                      } 
                    />
                  </div>
                </div>
              ))}
              {status === 'streaming' && (
                <div className="animate-pulse text-muted-foreground font-mono mt-2">_</div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Job Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Job ID</p>
              <p className="font-medium text-foreground">{jobId}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Last Event</p>
              <p className="font-medium text-foreground">
                {logs.length > 0 ? logs[logs.length - 1].node : 'None'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

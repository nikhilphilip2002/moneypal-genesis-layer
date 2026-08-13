'use client';

import dynamic from 'next/dynamic';
import { FileSpreadsheet, Network } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const DBSchemaGraph = dynamic(() => import('@/components/intel/DBSchemaGraph'), {
  ssr: false,
  loading: () => <WorkspaceLoading label="Loading the Enterprise Curiosity Graph…" />,
});

const DNBSReport = dynamic(() => import('@/components/intel/DNBSReport'), {
  ssr: false,
  loading: () => <WorkspaceLoading label="Loading regulatory reports…" />,
});

export type WorkspaceView = 'curiosity-graph' | 'regulatory-reports';

export const WORKSPACE_TOOLS: Array<{
  id: WorkspaceView;
  label: string;
  description: string;
  icon: typeof Network;
}> = [
  {
    id: 'curiosity-graph',
    label: 'Enterprise Curiosity Graph',
    description: 'Explore customers, accounts, branches, products, and their relationships.',
    icon: Network,
  },
  {
    id: 'regulatory-reports',
    label: 'RBI regulatory reports',
    description: 'Prepare, inspect, and export DNBS-02, DNBS-13, DNBS-4A, and DNBS-4B returns.',
    icon: FileSpreadsheet,
  },
];

export default function WorkbenchWorkspace({
  view,
  onOpenChange,
}: {
  view: WorkspaceView | null;
  onOpenChange: (open: boolean) => void;
}) {
  const tool = WORKSPACE_TOOLS.find((item) => item.id === view);

  return (
    <Dialog open={view !== null} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[96svh] w-[98vw] max-w-[1600px] grid-cols-none flex-col gap-0 overflow-hidden rounded-2xl bg-background p-0 sm:rounded-2xl">
        <DialogHeader className="shrink-0 border-b bg-card px-5 py-4 pr-14 text-left">
          <DialogTitle className="flex items-center gap-2 text-base">
            {tool && <tool.icon className="size-4 text-primary" />}
            {tool?.label ?? 'Workbench tool'}
          </DialogTitle>
          <DialogDescription className="text-xs">{tool?.description}</DialogDescription>
        </DialogHeader>

        <div className="relative min-h-0 flex-1 overflow-auto p-3 sm:p-5">
          {view === 'curiosity-graph' && (
            <div className="h-full min-h-[680px] rounded-2xl border border-border/70 bg-card p-3 sm:p-5">
              <DBSchemaGraph contained />
            </div>
          )}
          {view === 'regulatory-reports' && (
            <div className="mx-auto w-full max-w-7xl">
              <DNBSReport />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function WorkspaceLoading({ label }: { label: string }) {
  return (
    <div className="flex min-h-[420px] items-center justify-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}

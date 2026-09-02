'use client';

import dynamic from 'next/dynamic';
import {
  Building2,
  ClipboardCheck,
  FileSpreadsheet,
  Landmark,
  LayoutDashboard,
  Network,
  Scale,
  Settings2,
  UserRound,
} from 'lucide-react';
import type { UserRole } from '@/lib/useUserRole';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

const DBSchemaGraph = dynamic(() => import('@/components/intel/DBSchemaGraph'), {
  ssr: false,
  loading: () => <WorkspaceLoading label="Loading the Enterprise Information Graph…" />,
});

const DNBSReport = dynamic(() => import('@/components/intel/DNBSReport'), {
  ssr: false,
  loading: () => <WorkspaceLoading label="Loading regulatory reports…" />,
});

const ProfilePage = dynamic(() => import('@/app/profile/page'), {
  loading: () => <WorkspaceLoading label="Loading your profile…" />,
});
const AdminPage = dynamic(() => import('@/app/admin/page'), {
  loading: () => <WorkspaceLoading label="Loading platform administration…" />,
});
const ReviewPage = dynamic(() => import('@/app/review/page'), {
  loading: () => <WorkspaceLoading label="Loading intelligence review…" />,
});
const PolicyPage = dynamic(() => import('@/app/policy/page'), {
  loading: () => <WorkspaceLoading label="Loading policy workspace…" />,
});
const MacroPage = dynamic(() => import('@/app/macro/page'), {
  loading: () => <WorkspaceLoading label="Loading macro intelligence…" />,
});
const CompetitivePage = dynamic(() => import('@/app/competitive/page'), {
  loading: () => <WorkspaceLoading label="Loading competitive intelligence…" />,
});
const RegulatoryPage = dynamic(() => import('@/app/regulatory/page'), {
  loading: () => <WorkspaceLoading label="Loading regulatory intelligence…" />,
});
const PortfolioDashboard = dynamic(() => import('./PortfolioDashboard'), {
  loading: () => <WorkspaceLoading label="Loading the portfolio dashboard…" />,
});

export type WorkspaceView =
  | 'portfolio-dashboard'
  | 'curiosity-graph'
  | 'regulatory-reports'
  | 'profile'
  | 'administration'
  | 'intelligence-review'
  | 'policy-workspace'
  | 'macro-intelligence'
  | 'competitive-intelligence'
  | 'regulatory-intelligence';

export const WORKSPACE_TOOLS: Array<{
  id: WorkspaceView;
  label: string;
  description: string;
  icon: typeof Network;
}> = [
  {
    id: 'portfolio-dashboard',
    label: 'Portfolio dashboard',
    description: 'KPIs, trends, product mix, branch performance, and risk movement in one view.',
    icon: LayoutDashboard,
  },
  {
    id: 'curiosity-graph',
    label: 'Enterprise Information Graph',
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

export const WORKSPACE_MODULES: Array<{
  id: WorkspaceView;
  label: string;
  description: string;
  icon: typeof Network;
  roles: readonly UserRole[];
}> = [
  {
    id: 'macro-intelligence',
    label: 'Macro Intelligence',
    description: 'Economic indicators, sector context, and published market evidence.',
    icon: Landmark,
    roles: ['admin'],
  },
  {
    id: 'competitive-intelligence',
    label: 'Competitive Intelligence',
    description: 'Institution profiles, products, positioning, and market landscape.',
    icon: Building2,
    roles: ['admin', 'gicc_admin', 'gicc_policy'],
  },
  {
    id: 'regulatory-intelligence',
    label: 'Regulatory Intelligence',
    description: 'RBI requirements, categories, evidence, and regulatory analysis.',
    icon: Scale,
    roles: ['admin', 'gicc_admin', 'gicc_policy'],
  },
  {
    id: 'administration',
    label: 'Platform Administration',
    description: 'Users, institutions, system health, registries, and platform configuration.',
    icon: Settings2,
    roles: ['admin'],
  },
  {
    id: 'intelligence-review',
    label: 'Intelligence Review',
    description: 'Review and validate intelligence outputs before wider use.',
    icon: ClipboardCheck,
    roles: ['gicc_admin'],
  },
  {
    id: 'policy-workspace',
    label: 'Policy Workspace',
    description: 'Develop policy responses from reviewed regulatory intelligence.',
    icon: FileSpreadsheet,
    roles: ['gicc_policy'],
  },
  {
    id: 'profile',
    label: 'Account profile',
    description: 'Your identity, role, contact details, and provisioned access.',
    icon: UserRound,
    roles: ['admin', 'gicc_admin', 'gicc_policy', 'gicc_director'],
  },
];

export function modulesForRole(role: string | undefined) {
  return WORKSPACE_MODULES.filter((module) => module.roles.includes(role as UserRole));
}

export default function WorkbenchWorkspace({
  view,
  onOpenChange,
  onAsk,
}: {
  view: WorkspaceView | null;
  onOpenChange: (open: boolean) => void;
  onAsk: (question: string) => void;
}) {
  const tool = [...WORKSPACE_TOOLS, ...WORKSPACE_MODULES].find((item) => item.id === view);
  const isModule = WORKSPACE_MODULES.some((item) => item.id === view);

  return (
    <Dialog open={view !== null} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'flex grid-cols-none flex-col gap-0 overflow-hidden bg-background p-0',
          view === 'curiosity-graph' || view === 'portfolio-dashboard' || isModule
            ? 'h-svh w-screen max-w-none rounded-none border-0 sm:rounded-none'
            : 'h-[96svh] w-[98vw] max-w-[1600px] rounded-2xl sm:rounded-2xl',
        )}
      >
        {view === 'portfolio-dashboard' ? (
          <DialogTitle className="sr-only">Portfolio dashboard</DialogTitle>
        ) : (
          <DialogHeader className="shrink-0 border-b bg-card px-5 py-4 pr-14 text-left">
            <DialogTitle className="flex items-center gap-2 text-base">
              {tool && <tool.icon className="size-4 text-primary" />}
              {tool?.label ?? 'Workbench tool'}
            </DialogTitle>
            <DialogDescription className="text-xs">{tool?.description}</DialogDescription>
          </DialogHeader>
        )}

        <div className={cn(
          'relative min-h-0 flex-1',
          view === 'curiosity-graph'
            ? 'overflow-hidden p-3'
            : isModule ? 'overflow-auto bg-background' : 'overflow-auto p-3 sm:p-5',
        )}>
          {view === 'curiosity-graph' && (
            <div className="h-full min-h-0 overflow-hidden rounded-2xl border border-border/70 bg-card p-3 sm:p-4">
              <DBSchemaGraph contained />
            </div>
          )}
          {view === 'portfolio-dashboard' && (
            <PortfolioDashboard onAsk={(question) => { onOpenChange(false); onAsk(question); }} />
          )}
          {view === 'regulatory-reports' && (
            <div className="mx-auto w-full max-w-7xl">
              <DNBSReport />
            </div>
          )}
          {view === 'profile' && <ProfilePage />}
          {view === 'administration' && <AdminPage />}
          {view === 'intelligence-review' && <ReviewPage />}
          {view === 'policy-workspace' && <PolicyPage />}
          {view === 'macro-intelligence' && <MacroPage />}
          {view === 'competitive-intelligence' && <CompetitivePage />}
          {view === 'regulatory-intelligence' && <RegulatoryPage />}
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

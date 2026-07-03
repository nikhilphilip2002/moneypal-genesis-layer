'use client';

import { Bot } from 'lucide-react';
import { SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AppWalkthrough } from './AppWalkthrough';
import { IntelQueryGuide } from './IntelQueryGuide';
import type { UserRole } from '@/lib/useUserRole';

interface Props {
  role: UserRole | null;
  onClose: () => void;
}

export function GuidePanel({ role, onClose }: Props) {
  return (
    <div className="flex h-full flex-col">
      <SheetHeader className="shrink-0 border-b border-border px-5 pb-4 pt-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <SheetTitle className="text-base">Aroha Guide</SheetTitle>
            <SheetDescription className="text-xs">
              Learn what this platform can do for you
            </SheetDescription>
          </div>
        </div>
      </SheetHeader>

      {/* Default to Intel Guide — that's the core content */}
      <Tabs defaultValue="intel" className="flex min-h-0 flex-1 flex-col">
        <TabsList className="mx-5 mt-3 shrink-0 w-auto self-start">
          <TabsTrigger value="intel" className="text-xs">Intel Guide</TabsTrigger>
          <TabsTrigger value="tour" className="text-xs">App Tour</TabsTrigger>
        </TabsList>

        <TabsContent value="intel" className="mt-0 flex-1 overflow-hidden">
          <ScrollArea className="h-full px-5 pt-4">
            <IntelQueryGuide />
          </ScrollArea>
        </TabsContent>

        <TabsContent value="tour" className="mt-0 flex-1 overflow-hidden">
          <ScrollArea className="h-full px-5 pt-4">
            <AppWalkthrough role={role} onNavigate={onClose} />
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}

'use client';

import { useEffect, useState } from 'react';
import { HelpCircle, X, ArrowRight, ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// The guidebot: a one-time spotlight tour on first visit, and a persistent "?" helper that
// answers "how do I…" from a small static capability doc — no model, no source, so it works
// offline and never fabricates. The tour is a centred, stepped card rather than element
// spotlights: robust to layout, and enough to orient a first-time user.

const TOUR_KEY = 'workbench_tour_done_v1';

const TOUR_STEPS = [
  {
    title: 'Welcome to the Workbench',
    body: 'One chat for everything. Ask about the loan book, the market, or the regulations — it routes your question to the right source and answers from it, grounded and cited.',
  },
  {
    title: 'The “+” does more than type',
    body: 'Open “+” to run tools and reports, pin a source so a question always goes where you want, or check the model — everything runs locally by default.',
  },
  {
    title: 'Your history is saved',
    body: 'Every conversation lands in the left rail. Click one to revisit it, or “New” to start fresh. Nothing leaves your machine.',
  },
];

const FAQ = [
  { q: 'Ask about our loan book', a: 'Just type it — disbursement, PAR 30, collections, by branch or product. It routes to the loan book automatically.' },
  { q: 'Force a specific source', a: 'Use “+” → Pin a source, then ask. Your question goes only there until you unpin it.' },
  { q: 'Run a report or action', a: 'Use “+” → Tools & actions. Available tools depend on your role.' },
  { q: 'Is my data private?', a: 'Yes — the model runs locally, so loan-book data stays on this machine unless a deployment opts into a cloud burst.' },
  { q: 'Start a new conversation', a: 'Click “New” in the left rail. Past conversations stay in History.' },
];

export default function Guidebot() {
  const [tourOpen, setTourOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined' && !localStorage.getItem(TOUR_KEY)) {
      setTourOpen(true);
    }
  }, []);

  const closeTour = () => {
    setTourOpen(false);
    if (typeof window !== 'undefined') localStorage.setItem(TOUR_KEY, '1');
  };

  return (
    <>
      {/* Persistent helper trigger. */}
      <button
        onClick={() => setHelpOpen((o) => !o)}
        aria-label="Help"
        className="fixed bottom-4 right-4 z-40 flex size-10 items-center justify-center rounded-full border bg-background shadow-md transition-colors hover:bg-muted"
      >
        {helpOpen ? <X className="size-5" /> : <HelpCircle className="size-5" />}
      </button>

      {helpOpen && (
        <div className="fixed bottom-16 right-4 z-40 w-80 max-w-[calc(100vw-2rem)] rounded-xl border bg-background p-3 shadow-xl">
          <div className="mb-2 flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            <span className="text-sm font-semibold">How do I…</span>
            <button className="ml-auto text-muted-foreground hover:text-foreground" onClick={() => { setTourOpen(true); setStep(0); setHelpOpen(false); }}>
              <span className="text-[11px] underline">Replay tour</span>
            </button>
          </div>
          <ul className="space-y-2">
            {FAQ.map((item) => (
              <li key={item.q}>
                <p className="text-xs font-medium">{item.q}</p>
                <p className="text-xs text-muted-foreground">{item.a}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* First-run tour. */}
      {tourOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border bg-background p-5 shadow-2xl">
            <div className="mb-1 flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10">
                <Sparkles className="size-4 text-primary" />
              </div>
              <span className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                Step {step + 1} of {TOUR_STEPS.length}
              </span>
              <button className="ml-auto text-muted-foreground hover:text-foreground" onClick={closeTour} aria-label="Skip">
                <X className="size-4" />
              </button>
            </div>
            <h2 className="text-base font-semibold">{TOUR_STEPS[step].title}</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">{TOUR_STEPS[step].body}</p>

            <div className="mt-4 flex items-center justify-between">
              <div className="flex gap-1">
                {TOUR_STEPS.map((_, i) => (
                  <span key={i} className={cn('size-1.5 rounded-full', i === step ? 'bg-primary' : 'bg-muted-foreground/30')} />
                ))}
              </div>
              <div className="flex gap-2">
                {step > 0 && (
                  <Button size="sm" variant="ghost" onClick={() => setStep((s) => s - 1)}>
                    <ArrowLeft className="size-4" /> Back
                  </Button>
                )}
                {step < TOUR_STEPS.length - 1 ? (
                  <Button size="sm" onClick={() => setStep((s) => s + 1)}>
                    Next <ArrowRight className="size-4" />
                  </Button>
                ) : (
                  <Button size="sm" onClick={closeTour}>Get started</Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

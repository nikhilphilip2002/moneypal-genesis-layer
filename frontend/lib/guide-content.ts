export type QueryExample = {
  query: string;
  intent: string;
  note: string;
};

export type OutOfScope = {
  query: string;
  reason: string;
};

export type AppSection = {
  title: string;
  path: string;
  icon: string;
  description: string;
  tips: string[];
  roles: ('admin' | 'manager' | 'standard')[];
};

export const INTEL_GOOD_EXAMPLES: QueryExample[] = [
  {
    query: 'Who is placed at Fintellix?',
    intent: 'resources',
    note: 'Lists employees currently deployed at a client site',
  },
  {
    query: 'List requirements at MuSigma',
    intent: 'requirements',
    note: 'Open job positions for a specific company',
  },
  {
    query: 'Who joined recently in HR?',
    intent: 'resources',
    note: 'New joiners filtered by department',
  },
  {
    query: 'Emails from John Doe this month',
    intent: 'email',
    note: 'Admin only — searches the email knowledge base',
  },
  {
    query: 'Interview questions for a Java developer',
    intent: 'interviews',
    note: 'Common tech interview prep questions',
  },
  {
    query: 'Give me an overview of MuSigma',
    intent: 'company overview',
    note: 'Company profile, services, and history',
  },
  {
    query: 'List all our clients',
    intent: 'list clients',
    note: 'Portfolio-level query — no company name needed',
  },
  {
    query: 'Which companies need Python developers?',
    intent: 'cross-company',
    note: 'Cross-client skill requirements in one query',
  },
  {
    query: 'How many employees are working in CreditNirvana?',
    intent: 'resources',
    note: 'Headcount at a specific client location',
  },
  {
    query: 'Technologies required at CreditNirvana',
    intent: 'requirements',
    note: 'Tech stack needed to place employees there',
  },
];

export const INTEL_OUT_OF_SCOPE: OutOfScope[] = [
  {
    query: 'What is the weather today?',
    reason: 'Real-world / external data — not in the intelligence database',
  },
  {
    query: 'Write me a SQL query',
    reason: 'Code generation is out of scope for Company Intel',
  },
  {
    query: 'Who is the CEO of Apple?',
    reason: 'Only companies in the client portfolio are indexed',
  },
  {
    query: 'Book a meeting with Jane Doe',
    reason: 'No calendar or scheduling integration exists',
  },
  {
    query: 'What is the stock price of Infosys?',
    reason: 'Real-time market data is not available here',
  },
  {
    query: 'Translate this paragraph to French',
    reason: 'Use General Intel chat for open-ended tasks like translation',
  },
];

export const INTENT_TABLE: { pattern: string; example: string }[] = [
  { pattern: 'Who is placed at [Company]?',          example: 'Who is placed at Fintellix?' },
  { pattern: 'Employees working in [Company]',       example: 'Employees working in MuSigma' },
  { pattern: 'Requirements at [Company]',            example: 'Requirements at CreditNirvana' },
  { pattern: 'Interview questions for [Role]',       example: 'Interview questions for a React developer' },
  { pattern: 'Overview of [Company]',                example: 'Overview of MuSigma' },
  { pattern: 'List all clients / our clients',       example: 'List all our clients' },
  { pattern: 'Which companies need [Skill]?',        example: 'Which companies need Java?' },
  { pattern: 'Emails from [Name] in [Period]',       example: 'Emails from John Doe last week' },
];

export const APP_SECTIONS: AppSection[] = [
  {
    title: 'Company Intel',
    path: '/intel',
    icon: 'Zap',
    description:
      'Natural-language queries against the client intelligence database — placements, open requirements, contacts, and company profiles. Answers stream in real time.',
    tips: [
      'Always include a company name for contact, resource, or requirement queries',
      'Leave the company out for portfolio-level queries like "list all clients"',
      'Answers stream word-by-word — no need to wait for the full response',
      'Conversations are saved — use the sidebar to revisit past sessions',
    ],
    roles: ['admin', 'manager'],
  },
  {
    title: 'General Intel',
    path: '/general-chat',
    icon: 'MessageCircle',
    description:
      'Freeform AI chat for anything outside the structured client database — drafting emails, summarising documents, general Q&A, brainstorming.',
    tips: [
      'No company context required',
      'Great for tasks the intel assistant cannot do (translation, drafting, etc.)',
    ],
    roles: ['admin', 'manager', 'standard'],
  },
  {
    title: 'YouTube Snippets',
    path: '/youtube-chat',
    icon: 'Zap',
    description:
      'Chat with a knowledge base built from curated YouTube content. Ask topic-specific questions and get relevant transcript snippets.',
    tips: ['Ask focused questions to get the most relevant snippets'],
    roles: ['admin', 'manager', 'standard'],
  },
  {
    title: 'iBridge Analysis',
    path: '/ibridge-analysis',
    icon: 'ClipboardCheck',
    description:
      'Analyse learner attempt data — gap detection, coaching recommendations, and SQL/code proficiency reports per learner.',
    tips: ['Select a learner and time range before running a report'],
    roles: ['admin', 'manager', 'standard'],
  },
  {
    title: 'Companies',
    path: '/companies',
    icon: 'Building',
    description:
      'Directory of all indexed client companies with active status and quick links to their intel.',
    tips: [],
    roles: ['admin', 'manager', 'standard'],
  },
  {
    title: 'Job Requirements',
    path: '/intel/requirements',
    icon: 'Briefcase',
    description:
      'Browse and search all open job positions across every client — filterable by skill, location, and experience.',
    tips: [],
    roles: ['admin', 'manager'],
  },
  {
    title: 'Email KB',
    path: '/email-knowledge-base',
    icon: 'Mail',
    description:
      'Admin-only semantic search over the internal email archive. You can also query it inline via Intel: "emails from John Doe this month".',
    tips: [],
    roles: ['admin'],
  },
  {
    title: 'Curiosity Graph',
    path: '/curiosity-graph',
    icon: 'Network',
    description:
      'Visual knowledge graph of topics extracted from team search history — useful for spotting trends and knowledge gaps.',
    tips: [],
    roles: ['admin'],
  },
  {
    title: 'Usage',
    path: '/usage',
    icon: 'BarChart3',
    description:
      'LLM token usage and request counts across 1-minute, 1-hour, and 24-hour windows with a log of recent requests.',
    tips: [],
    roles: ['admin', 'manager'],
  },
];

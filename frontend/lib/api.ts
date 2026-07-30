const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://100.70.118.31:4321/api').replace(/\/$/, '');

// ─── Shared response contract (mirrors genesis_core.schema) ───

export type Confidence = 'high' | 'medium' | 'low';

export type SourceRef = {
  document: string;
  url: string;
  page?: string | null;
};

export type IntelligenceResponse = {
  title: string;
  summary: string;
  key_points: string[];
  source: SourceRef;
  ai_note: string;
  last_updated: string;
  confidence: Confidence;
};

export type Institution = {
  id: string;
  name: string;
  type: string;
  headquarters?: string | null;
  msme_focus?: boolean;
  website?: string | null;
  qdrant_collection?: string;
};

export type SwotResponse = {
  institution: string;
  swot_analysis: string;
  source: SourceRef;
  ai_note: string;
};

export type RegulationCategory = {
  id: string;
  display_name: string;
  applicability?: string | null;
  effective_date?: string | null;
  priority?: string;
  rbi_url?: string | null;
  qdrant_collection?: string;
};

export type RegulatoryAlert = {
  title: string;
  category: string;
  severity: 'high' | 'medium' | 'low';
  summary: string;
  action_required: string;
  source_url: string;
  ai_note: string;
};

export type SectionProvenance = {
  status: 'ok' | 'empty' | 'error' | 'no_source';
  row_count: number;
  /** Why the section produced nothing. */
  error?: string;
  /** Caveat about data that did resolve, e.g. an undated source. */
  note?: string;
};

export type DNBS02ReportData = {
  frequency: 'monthly' | 'quarterly' | 'yearly' | 'custom';
  period: string;
  start_date: string;
  end_date: string;
  /** Date of the bronze.genln_rpt_day snapshot the point-in-time sections are measured on. */
  snapshot_date: string;
  /** Year of the bronze.glbbal trial balance backing Parts 1/3/4. */
  gl_year: number;
  duration_days?: number;
  generated_at: string;

  /** Per-section outcome. A section is only trustworthy when its status is 'ok'. */
  provenance: Record<string, SectionProvenance>;
  live_sections: string[];
  degraded_sections: string[];
  /** True only when every section resolved from the database. */
  is_live_pg: boolean;

  /** Portion of the open loan book that has a dated snapshot behind it. */
  coverage: {
    covered_accounts: number;
    covered_lakhs: number;
    uncovered_accounts: number;
    uncovered_lakhs: number;
    covered_pct: number;
  };

  summary: {
    total_loan_book: number;
    accrued_interest: number;
    account_count: number;
    borrower_count: number;
    owned_funds: number;
    provision_held: number;
    gross_npa_amount: number;
    gross_npa_pct: number;
    /** null when risk-weighted assets have no source. */
    crar_pct: number | null;
  };
  part1_capital: { gl_group: string; particulars: string; amount_lakhs: number }[];
  part2_loans: { category: string; account_count: number; amount_lakhs: number; share_pct: number }[];
  part2_maturity: { bucket: string; account_count: number; amount_lakhs: number }[];
  part3_income: { head: string; amount_lakhs: number }[];
  part4_nof: { particulars: string; amount_lakhs: number }[];
  part6_sensitive: { sector: string; particulars: string; exposure_lakhs: number }[];
  part8_asset_quality: {
    asset_code: string;
    status: string;
    is_npa: boolean;
    count: number;
    amount_lakhs: number;
    provision_lakhs: number;
  }[];
  part8a_msme: {
    category: string;
    account_count: number;
    amount_lakhs: number;
    min_interest_rate: number;
    max_interest_rate: number;
    weighted_avg_interest_rate: number;
  }[];
  annex2_shareholders: { name: string; type_of_capital: string; num_shares: number; face_value: number; shareholding_pct: number }[];
  annex9_top_borrowers: {
    cust_id: string;
    borrower_name: string;
    pan: string;
    borrower_type: string;
    account_count: number;
    sanctioned_amt: number;
    disbursed_amt: number;
    undisbursed_amt: number;
    principal_outstanding: number;
    accrued_interest: number;
    account_status: string;
    total_outstanding: number;
  }[];
  annex10_top_investments: {
    entity_name: string;
    gl_head: string;
    nature: string;
    investment_type: string;
    pan: string;
    book_value: number;
    is_group_company: string;
    amt_outstanding: number;
  }[];
  annex11_top_npas: {
    borrower_name: string;
    pan: string;
    borrower_type: string;
    principal_os: number;
    int_due: number;
    asset_code: string;
    npa_date: string;
    last_payment_date: string;
    sanctioned_amt: number;
  }[];
  annex13_branches: {
    branch_code: string;
    branch_name: string;
    address: string;
    city: string;
    state: string;
    district: string;
    customer_count: number;
    account_count: number;
    total_outstanding: number;
  }[];
};

export type DNBS02Periods = {
  monthly: { value: string; label: string; end_date: string }[];
  snapshot_dates: string[];
  gl_years: number[];
  note: string;
};


export type DemoUser = {
  username: string;
  role: string;
  full_name: string;
  email: string;
};

export type OnboardingPhase = {
  name: string;
  status: 'active' | 'upcoming' | 'done';
  detail: string;
};

export type PlatformStatus = {
  qdrant: { ok: boolean; host: string; port: number };
  llm: { model: string; configured: boolean };
  embeddings: { model: string };
  registries: { institutions: number; regulations: number };
  collections: Array<{
    collection: string;
    label: string;
    module: string;
    indexed: boolean;
    vectors: number | null;
  }>;
  onboarding: {
    client: string;
    client_url: string;
    platform: string;
    phases: OnboardingPhase[];
  };
};

export type ReviewItem = {
  id: string;
  title: string;
  module: string;
  status: 'pending' | 'reviewed' | 'flagged';
  note: string;
  reviewed_at: string | null;
};

export type SearchResult = {
  module: string;
  collection_label: string;
  text: string;
  source: string;
  page: number | null;
  score: number;
};

// ─── Auth/session helpers ───

export const getToken = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('token');
  }
  return null;
};

export function clearLocalAuthState() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refreshToken');
}

function redirectToLogin() {
  if (typeof window === 'undefined' || window.location.pathname.startsWith('/login')) return;
  clearLocalAuthState();
  window.location.href = '/login';
}

// Generic API request helper
async function apiRequest(endpoint: string, options: RequestInit = {}, retry = true): Promise<any> {
  const token = getToken();

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    if (response.status === 401 && retry && !endpoint.startsWith('/auth/login')) {
      redirectToLogin();
    }
    const errorBody = await response.json().catch(() => ({}));
    const message =
      errorBody.error ||
      errorBody.detail ||
      `HTTP error! status: ${response.status}`;
    throw new Error(message);
  }

  return response.json();
}

// ─── Auth API (hardcoded demo users on the backend) ───

export const auth = {
  login: (username: string, password: string) =>
    apiRequest('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  me: () => apiRequest('/auth/me/'),

  users: (): Promise<DemoUser[]> => apiRequest('/auth/users/'),

  // Mock backend has no server session — logout is purely client-side.
  logout: () => {
    clearLocalAuthState();
    return Promise.resolve();
  },
};

// ─── Module 1: Macro-economic intelligence ───

export const macro = {
  snapshot: (refresh?: boolean): Promise<IntelligenceResponse> => apiRequest(`/macro/snapshot${refresh ? '?refresh=1' : ''}`),
  karnataka: (refresh?: boolean): Promise<IntelligenceResponse> => apiRequest(`/macro/karnataka${refresh ? '?refresh=1' : ''}`),
  msme: (refresh?: boolean): Promise<IntelligenceResponse> => apiRequest(`/macro/msme${refresh ? '?refresh=1' : ''}`),
  briefing: (refresh?: boolean): Promise<IntelligenceResponse> => apiRequest(`/macro/briefing${refresh ? '?refresh=1' : ''}`),
};

// ─── Module 2: Competitive intelligence ───

export const competitive = {
  institutions: (): Promise<Institution[]> => apiRequest('/competitive/institutions'),
  profile: (id: string, refresh?: boolean): Promise<IntelligenceResponse> =>
    apiRequest(`/competitive/institutions/${encodeURIComponent(id)}${refresh ? '?refresh=1' : ''}`),
  swot: (id: string, refresh?: boolean): Promise<SwotResponse> =>
    apiRequest(`/competitive/institutions/${encodeURIComponent(id)}/swot${refresh ? '?refresh=1' : ''}`),
  landscape: (refresh?: boolean): Promise<IntelligenceResponse> => apiRequest(`/competitive/landscape${refresh ? '?refresh=1' : ''}`),
  momVintage: (): Promise<any> => apiRequest('/competitive/mom-vintage'),
};

// ─── Module 3: Regulatory intelligence ───

export const regulatory = {
  categories: (): Promise<RegulationCategory[]> => apiRequest('/regulatory/categories'),
  detail: (id: string, refresh?: boolean): Promise<IntelligenceResponse> =>
    apiRequest(`/regulatory/${encodeURIComponent(id)}${refresh ? '?refresh=1' : ''}`),
  alerts: (): Promise<RegulatoryAlert[]> => apiRequest('/regulatory/alerts'),
  dnbsPeriods: (): Promise<DNBS02Periods> => apiRequest('/regulatory/dnbs02/periods'),
  dnbsReport: (frequency: string = 'monthly', period: string = '', startDate?: string, endDate?: string): Promise<DNBS02ReportData> => {
    let url = `/regulatory/dnbs02?frequency=${encodeURIComponent(frequency)}&period=${encodeURIComponent(period)}`;
    if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
    if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;
    return apiRequest(url);
  },
  getDnbsExcelUrl: (frequency: string = 'monthly', period: string = '', startDate?: string, endDate?: string): string => {
    let url = `${API_URL}/regulatory/dnbs02/export?frequency=${encodeURIComponent(frequency)}&period=${encodeURIComponent(period)}`;
    if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
    if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;
    return url;
  },
};



// ─── Platform administration (Moneypal Administrator) ───

export const admin = {
  status: (): Promise<PlatformStatus> => apiRequest('/admin/status'),
  dbSchema: (params?: { search?: string; view_level?: string; zonal_id?: string; manager_id?: string; agent_id?: string; customer_id?: string; month?: string } | string): Promise<any> => {
    let q = '';
    if (typeof params === 'string') {
      q = params ? `?search=${encodeURIComponent(params)}` : '';
    } else if (params) {
      const parts: string[] = [];
      if (params.search) parts.push(`search=${encodeURIComponent(params.search)}`);
      if (params.view_level) parts.push(`view_level=${encodeURIComponent(params.view_level)}`);
      if (params.zonal_id) parts.push(`zonal_id=${encodeURIComponent(params.zonal_id)}`);
      if (params.manager_id) parts.push(`manager_id=${encodeURIComponent(params.manager_id)}`);
      if (params.agent_id) parts.push(`agent_id=${encodeURIComponent(params.agent_id)}`);
      if (params.customer_id) parts.push(`customer_id=${encodeURIComponent(params.customer_id)}`);
      if (params.month) parts.push(`month=${encodeURIComponent(params.month)}`);
      if (parts.length > 0) q = '?' + parts.join('&');
    }
    return apiRequest(`/admin/db-schema${q}`);
  },
  monthlyBreakdown: (month?: string): Promise<any> =>
    apiRequest(`/admin/monthly-breakdown${month ? `?month=${encodeURIComponent(month)}` : ''}`),
  momLoanAnalysis: (): Promise<any> =>
    apiRequest('/admin/mom-loan-analysis'),
  dbSchemaSearch: (q: string, entity_type: string = 'all'): Promise<{ query: string; entity_type: string; results: any[] }> =>
    apiRequest(`/admin/db-schema/search?q=${encodeURIComponent(q)}&entity_type=${encodeURIComponent(entity_type)}`),
  addInstitution: (data: { name: string; type: string; website?: string; headquarters?: string; msme_focus?: boolean }) =>
    apiRequest('/competitive/institutions', { method: 'POST', body: JSON.stringify(data) }),
  addRegulation: (data: { display_name: string; rbi_url?: string; applicability?: string; effective_date?: string; priority?: string }) =>
    apiRequest('/regulatory/categories', { method: 'POST', body: JSON.stringify(data) }),
};

// ─── Intelligence review (GICC Administrator) ───

export const review = {
  items: (): Promise<ReviewItem[]> => apiRequest('/review/items'),
  update: (id: string, status: ReviewItem['status'], note: string): Promise<Partial<ReviewItem>> =>
    apiRequest(`/review/items/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify({ status, note }),
    }),
};

// ─── Policy formulation (GICC Policy Maker) ───

export const policy = {
  brief: (data: { regulation_ids: string[]; institution_ids: string[]; focus: string }): Promise<IntelligenceResponse> =>
    apiRequest('/policy/brief', { method: 'POST', body: JSON.stringify(data) }),
};

// ─── Cross-collection semantic search + Ask Genesis Q&A ───

export type AskResponse = {
  question: string;
  answer: string;
  results: SearchResult[];
};

export type RecentIntel = {
  title: string;
  module: 'Macro' | 'Competitive' | 'Regulatory';
  href: string;
  last_updated: number | null;
};

export type ActionItem = {
  title: string;
  detail: string;
  priority: 'High' | 'Medium';
  href: string;
};

export const intelligence = {
  search: (query: string): Promise<{ query: string; results: SearchResult[] }> =>
    apiRequest('/intelligence/search', { method: 'POST', body: JSON.stringify({ query }) }),
  ask: (query: string): Promise<AskResponse> =>
    apiRequest('/intelligence/ask', { method: 'POST', body: JSON.stringify({ query }) }),
  recent: (): Promise<RecentIntel[]> => apiRequest('/intelligence/recent'),
  actionItems: (): Promise<ActionItem[]> => apiRequest('/intelligence/action-items'),
};

// ─── Health check ───

export const health = {
  check: () => apiRequest('/health'),
};

// ─── Genesis NLQ — natural-language query layer ───
// Mirrors backend/app/services/nlq/contracts.py. ChartSpec.rows is always populated, even
// for kpi and line, so the table view and CSV export need no round-trip.

export type ChartType =
  | 'kpi' | 'line' | 'bar' | 'grouped_bar' | 'stacked_bar'
  | 'table' | 'ranking' | 'variance' | 'scatter' | 'heatmap';

export type Unit = 'inr' | 'percent' | 'count' | 'days' | 'ratio' | 'text' | 'date';

export type Lineage = {
  path: 'queryspec' | 'text_to_sql';
  sql: string;
  source_tables: string[];
  formulas: Record<string, string>;
  row_count: number;
  duration_ms: number;
  as_of: string | null;
  warnings: string[];
  unverified: boolean;
  requires_signoff: string[];
};

export type ColumnSpec = {
  name: string;
  label: string;
  unit: Unit;
  format: string | null;
  sensitivity: 'public' | 'internal' | 'pii';
  masked: boolean;
};

export type AxisSpec = { field: string; label: string; grain: string | null; unit: Unit };
export type SeriesSpec = { field: string; label: string; unit: Unit; axis: 'left' | 'right' };

export type QuerySpec = {
  metrics: string[];
  dimensions: string[];
  filters: { field: string; op: string; value: unknown }[];
  period: { grain?: string; start?: string | null; end?: string | null; relative?: string | null };
  compare_to?: unknown;
  order_by?: { field: string; direction: 'asc' | 'desc' } | null;
  limit: number;
};

export type ChartSpec = {
  chart_type: ChartType;
  title: string;
  subtitle: string | null;
  x: AxisSpec | null;
  series: SeriesSpec[];
  columns: ColumnSpec[];
  rows: Record<string, unknown>[];
  summary: string;
  drilldown: QuerySpec | null;
  lineage: Lineage;
};

export type NlqClarification = { route: 'clarify'; question: string; suggestions: string[] };
export type NlqRefusal = {
  route: 'refuse';
  reason: 'out_of_scope' | 'not_in_data' | 'predictive' | 'advice' | 'unsafe';
  message: string;
  examples: string[];
};

export type NlqAskResponse = {
  conversation_id: string;
  turn_id: string;
  status: 'answered' | 'clarify' | 'refused';
  chart: ChartSpec | null;
  clarification: NlqClarification | null;
  refusal: NlqRefusal | null;
  plan_summary: string;
};

export type NlqCatalogMetric = {
  id: string; label: string; unit: Unit; grain: string; formula: string;
  synonyms: string[]; requires_signoff: boolean; caveat: string;
};

export type NlqCatalog = {
  version: string;
  metrics: NlqCatalogMetric[];
  dimensions: { id: string; label: string; type: string; synonyms: string[]; cardinality: number | null }[];
  example_questions: string[];
};

export type NlqHealth = {
  status: 'ok' | 'degraded';
  llm: { status: string; provider: string; model: string; detail?: string };
  db: { status: string; detail?: string };
  catalog: { status: string; version?: string; metrics?: number };
  capabilities: { execute: boolean; ask: boolean; text_to_sql: boolean };
};

// SSE stage names, in the order the backend emits them.
export type NlqStage = 'understanding' | 'planning' | 'writing_sql' | 'querying' | 'charting';

export type NlqStreamEvent =
  | { type: 'stage'; stage: NlqStage }
  | { type: 'rewrite'; resolved_question: string }
  | { type: 'plan'; route: string; model: string }
  | { type: 'chart'; response: NlqAskResponse }
  | { type: 'clarify'; clarification: NlqClarification }
  | { type: 'refusal'; refusal: NlqRefusal }
  | { type: 'error'; message: string; retryable: boolean }
  | { type: 'done' };

export const nlq = {
  health: (): Promise<NlqHealth> => apiRequest('/nlq/health'),
  catalog: (): Promise<NlqCatalog> => apiRequest('/nlq/catalog'),

  // No LLM: drill-downs, saved questions and dashboards all run through this, which is why
  // they keep working when the assistant is offline.
  execute: (query_spec: QuerySpec): Promise<ChartSpec> =>
    apiRequest('/nlq/execute', { method: 'POST', body: JSON.stringify({ query_spec }) }),

  conversation: (id: string) => apiRequest(`/nlq/conversations/${id}`),
  clearConversation: (id: string) =>
    apiRequest(`/nlq/conversations/${id}`, { method: 'DELETE' }),
  feedback: (turn_id: string, verdict: 'up' | 'down', comment = '') =>
    apiRequest('/nlq/feedback', { method: 'POST', body: JSON.stringify({ turn_id, verdict, comment }) }),
  suggestions: (conversation_id?: string) =>
    apiRequest(`/nlq/suggestions${conversation_id ? `?conversation_id=${conversation_id}` : ''}`),

  // Streams SSE. Uses fetch rather than EventSource because the endpoint is a POST and
  // needs the Authorization header.
  async *ask(
    question: string,
    conversationId: string | null,
    signal?: AbortSignal,
  ): AsyncGenerator<NlqStreamEvent> {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access') : null;
    const res = await fetch(`${API_URL}/nlq/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question, conversation_id: conversationId }),
      signal,
    });

    if (!res.ok || !res.body) {
      const detail = await res.text().catch(() => '');
      throw new Error(detail || `Ask failed (${res.status})`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line; a partial frame stays buffered.
      let split: number;
      while ((split = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);

        let event = '';
        let data = '';
        for (const line of frame.split('\n')) {
          if (line.startsWith('event: ')) event = line.slice(7).trim();
          else if (line.startsWith('data: ')) data += line.slice(6);
        }
        if (!event) continue;

        let payload: any = {};
        try { payload = data ? JSON.parse(data) : {}; } catch { continue; }

        switch (event) {
          case 'stage': yield { type: 'stage', stage: payload.stage }; break;
          case 'rewrite': yield { type: 'rewrite', resolved_question: payload.resolved_question }; break;
          case 'plan': yield { type: 'plan', route: payload.route, model: payload.model }; break;
          case 'chart': yield { type: 'chart', response: payload as NlqAskResponse }; break;
          case 'clarify': yield { type: 'clarify', clarification: payload as NlqClarification }; break;
          case 'refusal': yield { type: 'refusal', refusal: payload as NlqRefusal }; break;
          case 'error': yield { type: 'error', message: payload.message, retryable: !!payload.retryable }; break;
          case 'done': yield { type: 'done' }; return;
        }
      }
    }
  },
};

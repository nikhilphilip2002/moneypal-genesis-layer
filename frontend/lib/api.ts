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
  report_mode: 'regulatory' | 'custom';
  filing_eligible: boolean;
  filing_note: string;

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
  quarterly: { value: string; label: string; end_date: string }[];
  yearly: { value: string; label: string; end_date: string }[];
  snapshot_dates: string[];
  gl_years: number[];
  note: string;
};

export type RegulatoryReportDefinition = {
  id: 'dnbs02' | 'dnbs13' | 'dnbs4a' | 'dnbs4b_structural' | 'dnbs4b_irs';
  return_code: string;
  name: string;
  frequency: 'monthly' | 'quarterly';
  description: string;
  workbook_output: string;
};

export type RegulatoryReportData = {
  report_id: string;
  return_code: string;
  name: string;
  frequency: string;
  start_date: string;
  end_date: string;
  generated_at: string;
  source: string;
  source_date?: string;
  report_mode: 'regulatory' | 'custom';
  filing_eligible: boolean;
  filing_note: string;
  status: 'draft' | 'partial' | 'blocked' | 'complete' | 'not_applicable';
  provenance: Record<string, SectionProvenance>;
  summary: Record<string, number | string>;
};

export type RegulatoryReportPeriods = {
  monthly?: { value: string; label: string; end_date: string }[];
  quarterly?: { value: string; label: string; end_date: string }[];
  source_dates?: string[];
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

export type BriefStreamHandlers = {
  onToken: (text: string) => void;
  onDone: (data: IntelligenceResponse) => void;
  onError: (message: string) => void;
};

// Consumes the /macro/briefing/stream SSE endpoint. Uses fetch (not EventSource)
// so the Bearer token can be sent. A cached brief arrives as a single `done`
// event; a freshly generated one streams `token` events first.
export async function streamBriefing(
  { refresh, signal }: { refresh?: boolean; signal?: AbortSignal },
  { onToken, onDone, onError }: BriefStreamHandlers,
): Promise<void> {
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}/macro/briefing/stream${refresh ? '?refresh=1' : ''}`, {
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
      signal,
    });
  } catch (err: any) {
    if (err?.name !== 'AbortError') onError('Could not reach the briefing service.');
    return;
  }

  if (!response.ok || !response.body) {
    if (response.status === 401) redirectToLogin();
    onError(`Briefing stream failed (status ${response.status}).`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const dispatch = (frame: string) => {
    let event = 'message';
    const dataLines: string[] = [];
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    let payload: any;
    try {
      payload = JSON.parse(dataLines.join('\n'));
    } catch {
      return;
    }
    if (event === 'token') onToken(payload.t ?? '');
    else if (event === 'done') onDone(payload as IntelligenceResponse);
    else if (event === 'error') onError(payload.message || 'Generation failed.');
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      // SSE frames are separated by a blank line.
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        if (frame.trim()) dispatch(frame);
      }
    }
  } catch (err: any) {
    if (err?.name !== 'AbortError') onError('The briefing stream was interrupted.');
  }
}

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
  reports: (): Promise<RegulatoryReportDefinition[]> => apiRequest('/regulatory/reports'),
  reportPeriods: (reportId: string): Promise<RegulatoryReportPeriods> =>
    apiRequest(`/regulatory/reports/${encodeURIComponent(reportId)}/periods`),
  report: (reportId: string, frequency: string, period: string, startDate?: string, endDate?: string): Promise<RegulatoryReportData> => {
    let url = `/regulatory/reports/${encodeURIComponent(reportId)}?frequency=${encodeURIComponent(frequency)}&period=${encodeURIComponent(period)}`;
    if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
    if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;
    return apiRequest(url);
  },
  getReportExcelUrl: (reportId: string, frequency: string, period: string, startDate?: string, endDate?: string): string => {
    let url = `${API_URL}/regulatory/reports/${encodeURIComponent(reportId)}/export?frequency=${encodeURIComponent(frequency)}&period=${encodeURIComponent(period)}`;
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
  | 'kpi' | 'line' | 'area' | 'stacked_area'
  | 'bar' | 'grouped_bar' | 'stacked_bar' | 'ranking' | 'donut'
  | 'variance' | 'dumbbell' | 'scatter' | 'heatmap' | 'small_multiples'
  | 'table';

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
// No `axis`. Two measures of different scale get two charts or a common index — never two
// y-scales on one plot, which is the one chart mistake that invents a correlation.
export type SeriesSpec = { field: string; label: string; unit: Unit };

export type QuerySpec = {
  metrics: string[];
  dimensions: string[];
  filters: { field: string; op: string; value: unknown }[];
  period: { grain?: string; start?: string | null; end?: string | null; relative?: string | null };
  compare_to?: unknown;
  order_by?: { field: string; direction: 'asc' | 'desc' } | null;
  limit: number;
  as_share?: boolean;
};

export type ChartSpec = {
  chart_type: ChartType;
  title: string;
  subtitle: string | null;
  x: AxisSpec | null;
  // Names the column that splits long-format rows into one series per value, so the
  // renderer pivots on a declared key rather than inferring one from the data.
  series_by: AxisSpec | null;
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

// --- Workbench (unified chat orchestrator) --------------------------------------------
// One chat that routes each question to the right source (loan book, macro, ...) and
// streams back a card per source. Mirrors the nlq SSE client; the event set is richer
// because a single turn can fan out to several sources.

export type WorkbenchSource = {
  id: string;
  label: string;
  describes: string;
  sensitive: boolean;
};

export type WorkbenchCard = {
  source: string;
  card_type: 'chart' | 'brief' | 'schema' | 'clarify' | 'refusal' | 'error';
  payload: any;
};

export type WorkbenchConversation = {
  conversation_id: string;
  title: string;
  updated_at: string;
  turn_count: number;
};

export type WorkbenchStreamEvent =
  | { type: 'conversation'; conversation_id: string }
  | { type: 'stage'; stage: string }
  | { type: 'route'; sources: string[]; intent: string; model: string }
  | { type: 'source_start'; source: string }
  | { type: 'source_card'; card: WorkbenchCard }
  | { type: 'synthesis'; text: string }
  | { type: 'refusal'; refusal: { reason: string; message: string } }
  | { type: 'error'; message: string; retryable: boolean }
  | { type: 'done' };

export type WorkbenchTool = {
  id: string;
  label: string;
  description: string;
  kind: string;
  params: Record<string, any>;
};

export const workbench = {
  sources: (): Promise<{ mode: string; data_access: 'direct' | 'mcp'; sources: WorkbenchSource[] }> =>
    apiRequest('/workbench/sources'),

  tools: (): Promise<{ tools: WorkbenchTool[] }> => apiRequest('/workbench/tools'),

  conversations: (): Promise<{ conversations: WorkbenchConversation[] }> =>
    apiRequest('/workbench/conversations'),

  conversation: (id: string): Promise<{
    conversation_id: string;
    title: string;
    updated_at: string;
    turns: { question: string; sources: string[]; at: string }[];
  }> => apiRequest(`/workbench/conversations/${id}`),

  runTool: async (toolId: string, params: Record<string, any> = {}): Promise<WorkbenchCard> => {
    const { source, card_type, ...payload } = await apiRequest(`/workbench/tool/${toolId}`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    });
    return { source, card_type, payload };
  },

  async *ask(
    question: string,
    conversationId: string | null,
    pinnedSource?: string | null,
    dataAccess?: 'direct' | 'mcp',
    signal?: AbortSignal,
  ): AsyncGenerator<WorkbenchStreamEvent> {
    const token = getToken();
    const res = await fetch(`${API_URL}/workbench/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question,
        conversation_id: conversationId,
        pinned_source: pinnedSource ?? null,
        data_access: dataAccess ?? null,
      }),
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
          case 'conversation': yield { type: 'conversation', conversation_id: payload.conversation_id }; break;
          case 'stage': yield { type: 'stage', stage: payload.stage }; break;
          case 'route':
            yield { type: 'route', sources: payload.sources || [], intent: payload.intent || '', model: payload.model || '' };
            break;
          case 'source_start': yield { type: 'source_start', source: payload.source }; break;
          case 'source_card': {
            const { source, card_type, ...rest } = payload;
            yield { type: 'source_card', card: { source, card_type, payload: rest } };
            break;
          }
          case 'synthesis': yield { type: 'synthesis', text: payload.text }; break;
          case 'refusal': yield { type: 'refusal', refusal: { reason: payload.reason, message: payload.message } }; break;
          case 'error': yield { type: 'error', message: payload.message, retryable: !!payload.retryable }; break;
          case 'done': yield { type: 'done' }; return;
        }
      }
    }
  },
};

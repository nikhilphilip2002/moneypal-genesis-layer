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
};

// ─── Module 3: Regulatory intelligence ───

export const regulatory = {
  categories: (): Promise<RegulationCategory[]> => apiRequest('/regulatory/categories'),
  detail: (id: string, refresh?: boolean): Promise<IntelligenceResponse> =>
    apiRequest(`/regulatory/${encodeURIComponent(id)}${refresh ? '?refresh=1' : ''}`),
  alerts: (): Promise<RegulatoryAlert[]> => apiRequest('/regulatory/alerts'),
};

// ─── Platform administration (Moneypal Administrator) ───

export const admin = {
  status: (): Promise<PlatformStatus> => apiRequest('/admin/status'),
  dbSchema: (params?: { search?: string; view_level?: string; zonal_id?: string; manager_id?: string; agent_id?: string; customer_id?: string } | string): Promise<any> => {
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
      if (parts.length > 0) q = '?' + parts.join('&');
    }
    return apiRequest(`/admin/db-schema${q}`);
  },
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

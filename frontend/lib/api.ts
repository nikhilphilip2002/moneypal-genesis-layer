const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export type OidcConfig = {
  keycloak_url: string;
  realm: string;
  client_id: string;
  authorization_endpoint: string;
  redirect_uri: string;
  post_logout_redirect_uri: string;
};

// Helper to get legacy bearer token, if one exists from older sessions.
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
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    if (response.status === 401 && retry) {
      const refreshed = await auth.refreshSession().catch(() => null);
      if (refreshed) {
        return apiRequest(endpoint, options, false);
      }
      redirectToLogin();
    }
    const errorBody = await response.json().catch(() => ({}));
    // Extract message: prefer explicit fields, then join field-level validation errors
    const message =
      errorBody.error ||
      errorBody.detail ||
      (typeof errorBody === 'object' && !Array.isArray(errorBody)
        ? Object.entries(errorBody)
            .map(([field, msgs]) =>
              Array.isArray(msgs) ? `${field}: ${msgs.join(' ')}` : String(msgs)
            )
            .join(' · ')
        : null) ||
      `HTTP error! status: ${response.status}`;
    throw new Error(message);
  }

  return response.json();
}

// Auth API
export const auth = {
  oidcConfig: (): Promise<OidcConfig> => apiRequest('/auth/oidc/config/'),

  completeOidcLogin: (code: string, codeVerifier: string, redirectUri: string) =>
    apiRequest('/auth/oidc/callback/', {
      method: 'POST',
      body: JSON.stringify({
        code,
        code_verifier: codeVerifier,
        redirect_uri: redirectUri,
      }),
    }),

  refreshSession: () =>
    apiRequest('/auth/session/refresh/', {
      method: 'POST',
      body: JSON.stringify({ refresh: getToken() ? localStorage.getItem('refreshToken') : undefined }),
    }, false),

  logout: () =>
    apiRequest('/auth/logout/', {
      method: 'POST',
    }, false),

  login: (username: string, password: string) =>
    apiRequest('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  register: (username: string, password: string, email: string, fullName: string, confirmPassword: string) =>
    apiRequest('/auth/register/', {
      method: 'POST',
      body: JSON.stringify({ username, password, email, full_name: fullName, confirm_password: confirmPassword }),
    }),

  me: () => apiRequest('/auth/me/'),

  updateProfile: (fullName: string, email: string) =>
    apiRequest('/auth/profile/', {
      method: 'PUT',
      body: JSON.stringify({ full_name: fullName, email }),
    }),

  listUsers: () => apiRequest('/auth/users/'),
};

// Companies API
export const companies = {
  list: () => apiRequest('/companies/'),
  get: (id: string) => apiRequest(`/companies/${id}/`),
  create: (data: { id: string; name: string; url: string }) =>
    apiRequest('/companies/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: Partial<{ name: string; url: string; status: string }>) =>
    apiRequest(`/companies/${id}/`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    apiRequest(`/companies/${id}/`, {
      method: 'DELETE',
    }),
  sync: () =>
    apiRequest('/companies/sync/', {
      method: 'POST',
    }),
  stats: () => apiRequest('/companies/stats/'),
  scrape: (id: string, maxDepth?: number) =>
    apiRequest(`/companies/${id}/scrape/`, {
      method: 'POST',
      body: JSON.stringify({ max_depth: maxDepth }),
    }),
  scrapeIncomplete: (maxDepth?: number) =>
    apiRequest('/companies/scrape/incomplete/', {
      method: 'POST',
      body: JSON.stringify({ max_depth: maxDepth }),
    }),
  jobs: (id: string) => apiRequest(`/companies/${id}/jobs/`),
};

// Agent API
export const agent = {
  run: (url: string, maxDepth?: number) =>
    apiRequest('/agent/run/', {
      method: 'POST',
      body: JSON.stringify({ url, max_depth: maxDepth }),
    }),
  status: (jobId: string) => apiRequest(`/agent/status/${jobId}/`),
  logs: (jobId: string) => {
    const token = getToken();
    return `${API_URL}/agent/logs/${jobId}/?token=${token}`;
  },
};

// RAG API
export const rag = {
  query: (query: string, topK?: number, filters?: Record<string, string>, generateResponse?: boolean) =>
    apiRequest('/rag/query/', {
      method: 'POST',
      body: JSON.stringify({
        query,
        top_k: topK || 5,
        filters,
        generate_response: generateResponse !== false,
      }),
    }),
  companies: () => apiRequest('/rag/companies/'),
  stats: () => apiRequest('/rag/stats/'),
  search: (query: string, topK?: number, filters?: Record<string, string>) =>
    apiRequest('/rag/search/', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK || 10, filters }),
    }),
};

// Usage API
export const usage = {
  stats: () => apiRequest('/usage/'),
  logs: (limit?: number) => apiRequest(`/usage/logs/?limit=${limit || 10}`),
};

// iBridge Analysis API
export const ibridge = {
  stats: (track?: string) => {
    const searchParams = new URLSearchParams();
    if (track) searchParams.set('track', track);
    const qs = searchParams.toString();
    return apiRequest(`/ibridge/stats/${qs ? `?${qs}` : ''}`);
  },
  users: (track?: string, search?: string) => {
    const searchParams = new URLSearchParams();
    if (track) searchParams.set('track', track);
    if (search) searchParams.set('search', search);
    const qs = searchParams.toString();
    return apiRequest(`/ibridge/users/${qs ? `?${qs}` : ''}`);
  },
  databases: (user?: string, track?: string) => {
    const searchParams = new URLSearchParams();
    if (user) searchParams.set('user', user);
    if (track) searchParams.set('track', track);
    const qs = searchParams.toString();
    return apiRequest(`/ibridge/databases/${qs ? `?${qs}` : ''}`);
  },
  report: (params: { user?: string; database: string; track?: string }) => {
    const searchParams = new URLSearchParams();
    if (params.user) searchParams.set('user', params.user);
    searchParams.set('database', params.database);
    if (params.track) searchParams.set('track', params.track);
    return apiRequest(`/ibridge/report/?${searchParams.toString()}`);
  },
  questionDetail: (params: { user?: string; database: string; question: string; track?: string }) => {
    const searchParams = new URLSearchParams();
    if (params.user) searchParams.set('user', params.user);
    searchParams.set('database', params.database);
    searchParams.set('question', params.question);
    if (params.track) searchParams.set('track', params.track);
    return apiRequest(`/ibridge/question-detail/?${searchParams.toString()}`);
  },
};

// Intel API (Intelligence Platform)
export const intel = {
  // Main query endpoint
  query: (query: string, company?: string, intent?: string) =>
    apiRequest('/intel/query/', {
      method: 'POST',
      body: JSON.stringify({ query, company, intent_hint: intent }),
    }),

  queryStream: async (
    query: string,
    onMetadata: (data: any) => void,
    onChunk: (text: string) => void,
    onError: (error: string) => void,
    company?: string,
    intent?: string
  ) => {
    const token = getToken();
    try {
      const response = await fetch(`${API_URL}/intel/query/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ query, company, intent_hint: intent, stream: true }),
      });

      if (!response.ok) {
        const status = response.status;
        const msg =
          status === 401 ? 'Your session has expired. Please log in again.' :
          status === 403 ? 'You don\'t have permission to perform this query.' :
          status === 404 ? 'The requested resource could not be found.' :
          status >= 500 ? 'Something went wrong on the server. Please try again in a moment.' :
          `Request failed (${status}). Please try again.`;
        onError(msg);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim();
            if (dataStr === '[DONE]') {
              return;
            }
            try {
              const data = JSON.parse(dataStr);
              if (data.type === 'metadata') {
                onMetadata(data);
              } else if (data.type === 'chunk') {
                onChunk(data.text);
              } else if (data.type === 'error') {
                onError(data.text);
              }
            } catch (err) {
              console.error('Failed to parse SSE data:', dataStr, err);
            }
          }
        }
      }
    } catch (err: any) {
      onError(err.message || String(err));
    }
  },

  // Requirements
  listRequirements: (params?: { company?: string; location?: string; skills?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.company) searchParams.set('company', params.company);
    if (params?.location) searchParams.set('location', params.location);
    if (params?.skills) searchParams.set('skills', params.skills);
    return apiRequest(`/intel/requirements/?${searchParams.toString()}`);
  },
  searchRequirements: (query: string, company?: string, skills?: string[], location?: string) =>
    apiRequest('/intel/requirements/search/', {
      method: 'POST',
      body: JSON.stringify({ query, company, skills, location }),
    }),

  // Interviews
  listInterviews: (params?: { company?: string; role?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.company) searchParams.set('company', params.company);
    if (params?.role) searchParams.set('role', params.role);
    return apiRequest(`/intel/interviews/?${searchParams.toString()}`);
  },
  searchInterviews: (query: string, company?: string, role?: string) =>
    apiRequest('/intel/interviews/search/', {
      method: 'POST',
      body: JSON.stringify({ query, company, role }),
    }),

  // Clients
  listClients: (search?: string) => {
    const searchParams = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiRequest(`/intel/clients/${searchParams}`);
  },
  getClient: (company: string) =>
    apiRequest(`/intel/clients/${encodeURIComponent(company)}/`),

  // Admin endpoints
  getContacts: (company: string) =>
    apiRequest(`/intel/contacts/${encodeURIComponent(company)}/`),
  getResources: (company: string, currentOnly?: boolean) => {
    const params = currentOnly !== undefined ? `?current_only=${currentOnly}` : '';
    return apiRequest(`/intel/resources/${encodeURIComponent(company)}/${params}`);
  },
  getHistory: (params?: { user?: string; intent?: string; days?: number; page?: number; page_size?: number; chat_type?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.user) searchParams.set('user', params.user);
    if (params?.intent && params.intent !== 'all') searchParams.set('intent', params.intent);
    if (params?.chat_type && params.chat_type !== 'all') searchParams.set('chat_type', params.chat_type);
    if (params?.days) searchParams.set('days', params.days.toString());
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
    return apiRequest(`/intel/history/?${searchParams.toString()}`);
  },
  getGraphData: (params?: {
    user_id?: number;
    days?: number;
    categories?: string[];
    bucket_types?: string[];
    min_weight?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.user_id) searchParams.set('user_id', params.user_id.toString());
    if (params?.days) searchParams.set('days', params.days.toString());
    if (params?.categories?.length) searchParams.set('categories', params.categories.join(','));
    if (params?.bucket_types?.length) searchParams.set('bucket_types', params.bucket_types.join(','));
    if (params?.min_weight) searchParams.set('min_weight', params.min_weight.toString());
    return apiRequest(`/intel/graph/?${searchParams.toString()}`);
  },
  triggerSync: (syncType?: 'all' | 'clients' | 'requirements' | 'interviews') =>
    apiRequest('/intel/sync/', {
      method: 'POST',
      body: JSON.stringify({ sync_type: syncType || 'all' }),
    }),

  // Stats
  stats: () => apiRequest('/intel/stats/'),

  // Reports
  getCompanyReport: (company: string) =>
    apiRequest(`/intel/report/${encodeURIComponent(company)}/`),
};

// Conversations API (Chat History)
export const conversations = {
  list: (chatType?: string) => apiRequest(`/intel/conversations/${chatType ? `?chat_type=${chatType}` : ''}`),

  create: (title?: string, chatType: 'intel' | 'general' | 'youtube' = 'intel') =>
    apiRequest('/intel/conversations/', {
      method: 'POST',
      body: JSON.stringify({ title: title || '', chat_type: chatType }),
    }),

  get: (id: string) => apiRequest(`/intel/conversations/${id}/`),

  delete: (id: string) =>
    apiRequest(`/intel/conversations/${id}/`, {
      method: 'DELETE',
    }),

  addMessage: (id: string, role: 'user' | 'assistant', content: string, intent?: string, report?: string) =>
    apiRequest(`/intel/conversations/${id}/messages/`, {
      method: 'POST',
      body: JSON.stringify({ role, content, intent: intent || '', report: report || '' }),
    }),
};

// General Chat API (no company data access)
export const generalChat = {
  query: (message: string, history?: Array<{ role: string; content: string }>) =>
    apiRequest('/intel/general-chat/', {
      method: 'POST',
      body: JSON.stringify({ query: message, history: history || [] }),
    }),

  queryStream: async (
    message: string,
    history: Array<{ role: string; content: string }>,
    onChunk: (text: string) => void,
    onError: (error: string) => void,
    onSource?: (sources: any[]) => void,
  ) => {
    const token = getToken();
    try {
      const response = await fetch(`${API_URL}/intel/general-chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ query: message, history: history || [], stream: true }),
      });

      if (!response.ok) {
        const status = response.status;
        const msg =
          status === 401 ? 'Your session has expired. Please log in again.' :
          status === 403 ? 'You don\'t have permission to perform this action.' :
          status >= 500 ? 'Something went wrong on the server. Please try again in a moment.' :
          `Request failed (${status}). Please try again.`;
        onError(msg);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim();
            if (dataStr === '[DONE]') {
              return;
            }
            try {
              const data = JSON.parse(dataStr);
              if (data.type === 'chunk') {
                onChunk(data.text);
              } else if (data.type === 'youtube_sources' && onSource) {
                onSource(data.sources);
              } else if (data.type === 'error') {
                onError(data.text);
              }
            } catch (err) {
              console.error('Failed to parse SSE data:', dataStr, err);
            }
          }
        }
      }
    } catch (err: any) {
      onError(err.message || String(err));
    }
  },

  downloadPdf: async (content: string, topic: string) => {
    const token = getToken();
    const response = await fetch(`${API_URL}/intel/general-chat/download/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({ content, topic }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Download failed' }));
      throw new Error(error.error || `HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    const safeTopic = topic.replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_').slice(0, 80) || 'presentation';
    const filename = `${safeTopic}.pdf`;

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  downloadSnippet: async (videoUrl: string, startTime: number, endTime: number) => {
    const token = getToken();
    const response = await fetch(`${API_URL}/youtube-kb/download-snippet/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({ video_url: videoUrl, start_time: startTime, end_time: endTime }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Snippet download failed' }));
      throw new Error(error.error || `HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    // Get filename from Content-Disposition header if available
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `snippet_${Math.floor(startTime)}s.mp4`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
      if (filenameMatch && filenameMatch.length > 1) {
        filename = filenameMatch[1].replace(/["']/g, '');
      }
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
};

// YouTube Chat API
export const youtubeChat = {
  queryStream: async (
    message: string,
    history: Array<{ role: string; content: string }>,
    searchMode: 'db' | 'direct',
    onChunk: (text: string) => void,
    onError: (error: string) => void,
    onSource?: (sources: any[]) => void,
  ) => {
    const token = getToken();
    try {
      const response = await fetch(`${API_URL}/youtube-kb/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ query: message, history: history || [], search_mode: searchMode, stream: true }),
      });

      if (!response.ok) {
        const status = response.status;
        const msg =
          status === 401 ? 'Your session has expired. Please log in again.' :
          status === 403 ? 'You don\'t have permission to perform this action.' :
          status >= 500 ? 'Something went wrong on the server. Please try again in a moment.' :
          `Request failed (${status}). Please try again.`;
        onError(msg);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim();
            if (dataStr === '[DONE]') {
              return;
            }
            try {
              const data = JSON.parse(dataStr);
              if (data.type === 'chunk') {
                onChunk(data.text);
              } else if (data.type === 'youtube_sources' && onSource) {
                onSource(data.sources);
              } else if (data.type === 'error') {
                onError(data.text);
              }
            } catch (err) {
              console.error('Failed to parse SSE data:', dataStr, err);
            }
          }
        }
      }
    } catch (err: any) {
      onError(err.message || String(err));
    }
  },
};

// Email Knowledge Base API (Admin)
export const emailKB = {
  testConnection: (data: {
    email: string; password: string;
    host?: string; port?: number; use_ssl?: boolean;
  }) =>
    apiRequest('/email-kb/connect/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listFolders: (data: {
    email: string; password: string;
    host?: string; port?: number; use_ssl?: boolean;
  }) =>
    apiRequest('/email-kb/folders/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  browseEmails: (data: {
    email: string; password: string; folder?: string;
    date_from?: string; date_to?: string; search?: string;
    host?: string; port?: number; use_ssl?: boolean;
  }) =>
    apiRequest('/email-kb/emails/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  extractEmails: (data: {
    email: string; password: string; folder: string;
    message_ids: string[];
    host?: string; port?: number; use_ssl?: boolean;
  }) =>
    apiRequest('/email-kb/extract/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  stats: () => apiRequest('/email-kb/stats/'),
};

// Health check
export const health = {
  check: () => apiRequest('/health/'),
};

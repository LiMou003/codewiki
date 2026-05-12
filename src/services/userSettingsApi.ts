export interface EmbeddingSettings {
  dimension?: number;
}

export interface RetrievalSettings {
  top_k?: number;
}

export interface AutoRefreshSettings {
  enabled?: boolean;
  interval_minutes?: number;
}

export interface UserConfig {
  embedding?: EmbeddingSettings;
  retrieval?: RetrievalSettings;
  auto_refresh?: AutoRefreshSettings;
}

export interface UserSettings {
  config: UserConfig | null;
}

export type UserSettingsUpdate = { config?: UserConfig | null };

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cw_token') : null;
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function getUserSettings(): Promise<UserSettings> {
  const res = await fetch('/api/user/settings', {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to load settings: ${res.status}`);
  return res.json();
}

export async function updateUserSettings(data: UserSettingsUpdate): Promise<UserSettings> {
  const res = await fetch('/api/user/settings', {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to save settings: ${res.status}`);
  return res.json();
}

export function getDefaultConfig(): UserConfig {
  return {
    embedding: { dimension: 1024 },
    retrieval: { top_k: 20 },
    auto_refresh: { enabled: true, interval_minutes: 60 },
  };
}

export type User = {
  id: string;
  email: string;
  handle: string;
  display_name: string;
  created_at: string;
  email_verified_at: string | null;
};

export type Me = { user: User; scopes: string[]; csrf_token: string | null };

export type TokenRow = {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};

export type Version = {
  id: string;
  number: number;
  message: string | null;
  entry_path: string;
  total_bytes: number;
  file_count: number;
  rolled_back_from: number | null;
  author_user_id: string | null;
  by_agent: boolean;
  created_at: string;
};

export type VersionFile = { path: string; sha256: string; size_bytes: number; content_type: string };

export type Page = {
  id: string;
  slug: string;
  title: string;
  visibility: string;
  owner_handle: string;
  current_version: Version | null;
  created_at: string;
  updated_at: string;
};

export type PageList = { items: Page[]; next_cursor: string | null };
export type VersionList = { items: Version[]; next_cursor: string | null };
export type Publish = { page: Page; version: Version; created: boolean };
export type ViewUrl = { url: string; expires_at: string };

export type BrowserSession = {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent: string | null;
  ip: string | null;
  current: boolean;
};

export type TokenCreated = TokenRow & { token: string };

export const SCOPES: { id: string; label: string; hint: string }[] = [
  { id: "pages:read", label: "Read pages", hint: "List and open pages" },
  { id: "pages:write", label: "Publish pages", hint: "Create pages and new versions" },
  { id: "comments:read", label: "Read comments", hint: "See comments on pages" },
  { id: "comments:write", label: "Write comments", hint: "Reply and comment as the agent" },
  { id: "requests:act", label: "Act on requests", hint: "Pick up and complete requests" },
  { id: "events:read", label: "Receive events", hint: "Listen for live updates" },
];

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let csrf: string | null = null;
export const setCsrf = (value: string | null) => {
  csrf = value;
};

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; form?: FormData } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrf) headers["X-CSRF-Token"] = csrf;

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body: init.form ?? (init.body !== undefined ? JSON.stringify(init.body) : undefined),
    });
  } catch {
    throw new ApiError(0, "network", "Cannot reach Paddock. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(res.status, err?.code ?? "error", err?.message ?? "Something went wrong. Try again.");
  }
  return data as T;
}

export async function fetchMe(): Promise<Me> {
  const me = await api<Me>("/v1/me");
  setCsrf(me.csrf_token);
  return me;
}

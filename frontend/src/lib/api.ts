export type User = {
  id: string;
  email: string;
  handle: string;
  display_name: string;
  created_at: string;
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

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
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
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
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

export type User = {
  id: string;
  email: string;
  handle: string;
  display_name: string;
  created_at: string;
  email_verified_at: string | null;
};

export type Me = { user: User; scopes: string[] };

export type Onboarding = {
  needs_onboarding: boolean;
  email: string;
  name: string | null;
  suggestions: string[];
};
export type HandleCheck = { handle: string; available: boolean; reason: string | null };

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

export type Role = "owner" | "editor" | "commenter" | "viewer";
export type MemberRole = "viewer" | "commenter" | "editor";
export type Visibility = "private" | "members" | "link";

export type Member = {
  user_id: string;
  handle: string;
  display_name: string;
  email: string;
  role: MemberRole;
  created_at: string;
};

export type Invite = {
  id: string;
  email: string;
  role: MemberRole;
  created_at: string;
  expires_at: string;
  expired: boolean;
};
export type InviteCreated = Invite & { accept_url: string; emailed: boolean };
export type InvitePreview = {
  page_title: string;
  owner_handle: string;
  invited_by: string | null;
  email: string;
  role: MemberRole;
  expires_at: string;
};

export type ShareLinkRow = {
  id: string;
  role: "viewer" | "commenter";
  created_at: string;
  expires_at: string | null;
  expired: boolean;
};
export type ShareLinkCreated = ShareLinkRow & { url: string };
export type Shared = {
  page_id: string;
  title: string;
  owner_handle: string;
  role: "viewer" | "commenter";
  version_number: number | null;
  updated_at: string;
};

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  editor: "Can edit",
  commenter: "Can comment",
  viewer: "Can view",
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
  role: Role;
  current_version: Version | null;
  created_at: string;
  updated_at: string;
};

export type PageList = { items: Page[]; next_cursor: string | null };
export type VersionList = { items: Version[]; next_cursor: string | null };
export type Publish = { page: Page; version: Version; created: boolean };
export type ViewUrl = { url: string; expires_at: string };

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

// The sign-in token Neon issues with the session (a short-lived JWT). Kept in memory and renewed a minute
// before it runs out, so most requests do not need an extra call.
let cached: { token: string; expires: number } | null = null;

export function forgetToken() {
  cached = null;
}

const looksLikeJwt = (value: unknown): value is string =>
  typeof value === "string" && value.split(".").length === 3;

async function fetchToken(): Promise<string | null> {
  const { authClient } = await import("./auth/client");
  // Neon sends the JWT with the session, and the SDK puts it in session.token.
  const res = await authClient.getSession();
  const fromSession = res.data?.session?.token;
  if (looksLikeJwt(fromSession)) return fromSession;
  // Otherwise ask Neon for one directly. Our server passes this call on.
  const direct = await fetch("/api/auth/token", { credentials: "same-origin" });
  if (!direct.ok) return null;
  const body = await direct.json().catch(() => null);
  return looksLikeJwt(body?.token) ? body.token : null;
}

async function loadToken(): Promise<string | null> {
  try {
    const token = await fetchToken();
    if (!token) return null;
    const exp = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).exp;
    cached = { token, expires: exp * 1000 };
    return token;
  } catch (err) {
    console.warn("Could not get the sign-in token", err);
    return null;
  }
}

// Several requests start together when a screen opens. They share one token lookup instead of one each.
let loading: Promise<string | null> | null = null;

async function bearer(): Promise<string | null> {
  if (cached && cached.expires - 60_000 > Date.now()) return cached.token;
  loading ??= loadToken().finally(() => {
    loading = null;
  });
  return loading;
}

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; form?: FormData } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  const token = await bearer();
  if (token) headers["Authorization"] = `Bearer ${token}`;

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
  return api<Me>("/v1/me");
}

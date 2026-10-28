export type Strength = { level: 0 | 1 | 2 | 3 | 4; label: string; tip: string };

const COMMON = ["password", "123456", "qwerty", "letmein", "welcome", "iloveyou", "admin", "paddock", "abc123", "111111"];

/** A simple, readable strength estimate. The server only requires 10 characters. */
export function passwordStrength(pw: string, extras: string[] = []): Strength {
  if (pw.length === 0) return { level: 0, label: "", tip: "Use at least 10 characters." };
  if (pw.length < 10) return { level: 0, label: "Too short", tip: `${10 - pw.length} more character${10 - pw.length === 1 ? "" : "s"} needed.` };

  const lower = pw.toLowerCase();
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  let points = pw.length >= 18 ? 3 : pw.length >= 14 ? 2 : 1;
  points += classes >= 4 ? 2 : classes === 3 ? 1 : 0;

  const common = COMMON.some((c) => lower.includes(c));
  const personal = extras.some((e) => e.length >= 3 && lower.includes(e.toLowerCase()));
  if (/(.)\1{2,}/.test(pw)) points -= 1;
  if (/(abc|bcd|cde|123|234|345|456|567|678|789|qwe|asd)/i.test(pw)) points -= 1;

  let level: 1 | 2 | 3 | 4 = points <= 1 ? 1 : points === 2 ? 2 : points <= 4 ? 3 : 4;
  if (common || personal) level = 1;

  const labels = { 1: "Weak", 2: "Fair", 3: "Good", 4: "Strong" } as const;
  let tip = "Nice. Keep it somewhere safe.";
  if (common) tip = "Avoid common words like password.";
  else if (personal) tip = "Avoid using your name, handle or email.";
  else if (level < 3 && pw.length < 14) tip = "Longer is stronger. Try a phrase of unrelated words.";
  else if (level < 4 && classes < 3) tip = "Mix in numbers, capitals or symbols.";
  else if (level < 4) tip = "Add a few more characters for a strong password.";
  return { level, label: labels[level], tip };
}

export type Check = { id: string; label: string; ok: boolean };

/** The same rules as above, as a short list the person can tick off. Only the first one is required by the server. */
export function passwordChecks(pw: string, extras: string[] = []): Check[] {
  const lower = pw.toLowerCase();
  const common = COMMON.some((c) => lower.includes(c));
  const personal = extras.some((e) => e.length >= 3 && lower.includes(e.toLowerCase()));
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  return [
    { id: "len", label: "10 or more characters", ok: pw.length >= 10 },
    { id: "plain", label: "No common word, name or email", ok: pw.length > 0 && !common && !personal },
    { id: "mix", label: "A mix of letters, numbers or symbols", ok: classes >= 3 },
  ];
}

// Free hosting puts idle servers to sleep, and waking one takes up to a minute. Starting that early,
// while someone reads the landing page or types their password, means it is awake when they need it.

const QUIET = 5 * 60 * 1000;
let lastWarm = 0;

export function warmServers() {
  if (typeof window === "undefined" || Date.now() - lastWarm < QUIET) return;
  lastWarm = Date.now();
  // Not awaited. Our server answers once the database is up and has started waking the content server.
  fetch("/api/warm", { cache: "no-store", keepalive: true }).catch(() => {});
}

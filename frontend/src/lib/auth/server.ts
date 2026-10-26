import { createNeonAuth } from "@neondatabase/auth/next/server";

// Server side of Neon Auth. The route in app/api/auth passes browser calls on to Neon
// and keeps the session cookie on our own address, so it works in every browser.
export const auth = createNeonAuth({
  baseUrl: process.env.NEON_AUTH_BASE_URL!,
  cookies: { secret: process.env.NEON_AUTH_COOKIE_SECRET! },
});

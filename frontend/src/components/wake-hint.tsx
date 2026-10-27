"use client";

import { useEffect, useState } from "react";

// Shown under a loading state. Stays quiet for the first seconds, then explains a slow start.
export function WakeHint({ what = "Paddock" }: { what?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 3000);
    return () => clearTimeout(t);
  }, []);
  return (
    <p role="status" className="text-[13px] text-muted-foreground">
      {slow ? `${what} is waking up after a quiet spell. This can take up to a minute, and only the first visit is slow.` : "Loading"}
    </p>
  );
}

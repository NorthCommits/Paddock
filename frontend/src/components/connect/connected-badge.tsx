import { CheckCircle2, Circle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

/** Says whether an app is connected, with an icon and words so colour is never the only signal. */
export function ConnectedBadge({ connected }: { connected: boolean }) {
  return connected ? (
    <Badge variant="success" className="gap-1">
      <CheckCircle2 size={12} aria-hidden="true" />
      Connected
    </Badge>
  ) : (
    <Badge variant="neutral" className="gap-1">
      <Circle size={12} aria-hidden="true" />
      Not connected yet
    </Badge>
  );
}

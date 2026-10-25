import type { Metadata } from "next";
import { EmptyState, LinkButton } from "@/components/ui";

export const metadata: Metadata = { title: "Pages" };

export default function Page() {
  return (
    <>
      <h1 className="text-[22px] font-semibold leading-7 text-ink">Pages</h1>
      <EmptyState
        title="No pages yet"
        body="Pages appear here when one of your agents publishes. Connect an agent to get started."
        action={<LinkButton href="/connect" variant="primary">Connect an agent</LinkButton>}
      />
    </>
  );
}

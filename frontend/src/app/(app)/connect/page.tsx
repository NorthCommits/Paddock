import type { Metadata } from "next";
import { CopyField, LinkButton } from "@/components/ui";

export const metadata: Metadata = { title: "Connect an agent" };

export default function Page() {
  return (
    <div className="max-w-[640px]">
      <h1 className="text-[22px] font-semibold leading-7 text-ink">Connect an agent</h1>
      <p className="mt-2 text-[15px] leading-[22px] text-ink-2">
        Any agent that can run a command or call an HTTP API can work with Paddock. You keep the model and its keys.
      </p>
      <ol className="mt-8 space-y-8">
        <li>
          <h2 className="text-[15px] font-semibold text-ink">1. Create a token</h2>
          <p className="mt-1 text-[13px] text-ink-2">Choose only the scopes the agent needs. The secret is shown once.</p>
          <div className="mt-3">
            <LinkButton href="/settings/tokens?new=1" variant="primary">Create token</LinkButton>
          </div>
        </li>
        <li>
          <h2 className="text-[15px] font-semibold text-ink">2. Give it to your agent</h2>
          <p className="mt-1 text-[13px] text-ink-2">Store it as an environment variable, never in a file you commit.</p>
          <div className="mt-3">
            <CopyField label="environment variable" value={"export PADDOCK_TOKEN=pdk_your_token"} />
          </div>
        </li>
        <li>
          <h2 className="text-[15px] font-semibold text-ink">3. Check the connection</h2>
          <p className="mt-1 text-[13px] text-ink-2">This should print your account. Publishing pages arrives in the next release.</p>
          <div className="mt-3">
            <CopyField
              label="test command"
              value={'curl -H "Authorization: Bearer $PADDOCK_TOKEN" \\\n  https://your-paddock-address/api/v1/me'}
            />
          </div>
        </li>
      </ol>
    </div>
  );
}

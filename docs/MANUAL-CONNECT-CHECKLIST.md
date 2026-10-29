# Manual check: connecting the real apps

The automated tests use a stand-in client. The real apps have their own quirks, so each one needs one hand check against your live Paddock. Do these after deploying and after setting `API_PUBLIC_URL` and `NEXT_PUBLIC_MCP_URL` (see the deployment guide).

Set these first:

- Your address: the API address followed by `/mcp`. It is the same text the Connect page shows. Example: `https://paddock-api-xxxx.onrender.com/mcp`.
- Sign in to Paddock in your normal browser before you start, so the consent page opens straight away.
- Do not paste any token or secret into a chat. These checks never need one.

Before the apps, open `<your API address>/.well-known/oauth-protected-resource/mcp` in a browser. It should show a short JSON text with `resource` ending in `/mcp`. If it does not, stop and fix the settings first.

After each app, check Paddock itself: on the Connect page the tab for that app shows Connected within a few seconds, and Settings, Tokens lists a row marked "Connected with sign-in". Revoke the row when you finish a check so the next check starts clean.

## 1. Claude Desktop

Needs a Claude plan that allows custom connectors.

1. Open Settings, then Connectors, then Add custom connector.
2. Paste your address and add it.
3. Choose Connect. Your browser opens the Paddock consent page.
4. Click Allow.

Expected: the browser returns to Claude, the connector shows as connected, and asking Claude "list my Paddock pages" works. Asking it to publish a small page ("publish a page called Hello with one line of text") creates a page that appears in Paddock.

Report back: what the connect screen said at each step, any error text word for word, and whether the page appeared.

## 2. ChatGPT desktop or web

Needs Developer mode, available on Pro and Plus plans.

1. Turn on Developer mode in Settings, then Connectors, then Advanced.
2. Choose Create connector. Paste your address. Choose OAuth as the sign-in method.
3. Complete the sign-in in the browser and click Allow.
4. In a new chat, enable the connector and ask: "list my Paddock pages".

Expected: the connector saves without an error, the consent page shows, and the chat can list pages and publish one.

Report back: whether ChatGPT asked for a client ID or secret (it should not), the exact error text if saving failed, and whether it listed and published.

## 3. Claude Code

1. In a terminal run: `claude mcp add --transport http paddock <your address>`
2. Start Claude Code and type `/mcp`. Choose paddock, then Authenticate.
3. Your browser opens the consent page. Click Allow.
4. Back in Claude Code, ask it to list your Paddock pages, then to publish a small page.

Expected: `/mcp` shows paddock as connected, and the page appears in Paddock. This one uses a local address on your computer for the return step, so it also checks the loopback port rule.

Report back: the `/mcp` status text, any error, and whether the page appeared.

## 4. Codex

1. In a terminal run: `codex mcp add paddock --url <your address>`
2. Codex opens your browser for sign-in. Click Allow.
3. Start Codex and ask it to list your Paddock pages, then publish a small page.

Expected: the browser returns to Codex, and the tools work.

Report back: the Codex version (`codex --version`), what happened at each step, and any error word for word.

## Things to try once

- Click Deny on the consent page instead of Allow. The app should say access was denied, and no row should appear in Settings, Tokens.
- Revoke the connection in Settings, then use the app again. The tools should fail and the app should offer to sign in again.
- Wait for the free server to sleep (about 15 minutes idle) and connect again. The first attempt may take up to a minute while the server wakes. Report how the app behaves while it waits.
- If an app times out on the token step while the free server wakes, remove the connection in Settings, then Tokens, and connect again.

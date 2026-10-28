"""A small read only load test. It calls a few endpoints repeatedly with an agent token and
reports throughput and latency. It creates and changes nothing.

    python scripts/loadtest.py --url http://localhost:8000 --token pdk_... --seconds 20 --workers 20

Rate limits apply to the token, so for a real run start the API with RATE_LIMIT_ENABLED=false
or the result will mostly show 429 answers (which are counted separately).
"""

import argparse
import asyncio
import statistics
import time

import httpx


async def worker(client, paths, stop_at, results):
    i = 0
    while time.monotonic() < stop_at:
        path = paths[i % len(paths)]
        i += 1
        start = time.perf_counter()
        try:
            res = await client.get(path)
            code = res.status_code
        except httpx.HTTPError:
            code = 0
        results.append((path, code, (time.perf_counter() - start) * 1000))


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))] if values else 0.0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"}
    limits = httpx.Limits(max_connections=args.workers)
    async with httpx.AsyncClient(
        base_url=args.url, headers=headers, limits=limits, timeout=30
    ) as c:
        pages = (await c.get("/v1/pages", params={"limit": 5})).json()["items"]
        paths = ["/healthz", "/v1/me", "/v1/pages?limit=20"]
        paths += [f"/v1/pages/{p['id']}" for p in pages]
        paths += [f"/v1/pages/{p['id']}/versions" for p in pages]
        results: list = []
        stop_at = time.monotonic() + args.seconds
        began = time.monotonic()
        await asyncio.gather(*(worker(c, paths, stop_at, results) for _ in range(args.workers)))
        took = time.monotonic() - began

    print(
        f"{len(results)} requests in {took:.1f}s with {args.workers} workers "
        f"({len(results) / took:.0f} per second)"
    )
    codes: dict[int, int] = {}
    for _, code, _ in results:
        codes[code] = codes.get(code, 0) + 1
    print("answers:", ", ".join(f"{k}: {v}" for k, v in sorted(codes.items())))
    print(f"{'path':<28}{'count':>7}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}")
    for path in dict.fromkeys(r[0] for r in results):
        times = [r[2] for r in results if r[0] == path and r[1] == 200]
        if times:
            shown = path if len(path) <= 27 else path[:12] + "..." + path[-12:]
            print(
                f"{shown:<28}{len(times):>7}{statistics.median(times):>9.1f}"
                f"{pct(times, 0.95):>9.1f}{max(times):>9.1f}"
            )


asyncio.run(main())

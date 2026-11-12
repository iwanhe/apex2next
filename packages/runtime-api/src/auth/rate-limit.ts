/**
 * Fixed-window login rate limit per client (WP9-009 throttling), in memory: enough for the single API instance of
 * the pilot. Several instances would need a shared store (e.g. a table in schema iam).
 */
export class RateLimiter {
  private readonly hits = new Map<string, { windowStart: number; count: number }>();

  constructor(private readonly limit: number, private readonly windowMs = 60_000, private readonly now = () => Date.now()) {}

  /** Counts one attempt; false when the client is over the limit for the current window. */
  take(key: string): boolean {
    const t = this.now();
    const e = this.hits.get(key);
    if (!e || t - e.windowStart >= this.windowMs) {
      this.hits.set(key, { windowStart: t, count: 1 });
      if (this.hits.size > 10_000) this.sweep(t);
      return true;
    }
    e.count += 1;
    return e.count <= this.limit;
  }

  private sweep(t: number) {
    for (const [k, e] of this.hits) if (t - e.windowStart >= this.windowMs) this.hits.delete(k);
  }
}

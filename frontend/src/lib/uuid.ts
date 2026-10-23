/**
 * RFC 4122 v4 UUID that works outside a secure context.
 *
 * `crypto.randomUUID()` is gated behind a secure context: it exists on HTTPS and on
 * localhost, but is `undefined` on a plain-HTTP origin. Calling it there throws
 * "crypto.randomUUID is not a function" and takes the whole component down.
 *
 * `crypto.getRandomValues()` is NOT gated, so it stays available on HTTP and gives us the
 * same cryptographic quality. Math.random is the last resort — these ids are only used to
 * key React lists and as an idempotency header, never as a secret.
 */
export function uuid(): string {
  const c: Crypto | undefined = globalThis.crypto;

  if (typeof c?.randomUUID === "function") {
    return c.randomUUID();
  }

  if (typeof c?.getRandomValues === "function") {
    const b = c.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40; // version 4
    b[8] = (b[8] & 0x3f) | 0x80; // variant 10xx
    const hex = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

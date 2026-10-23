/**
 * Reading a message out of something thrown.
 *
 * TypeScript types a `catch` binding as `unknown`, because JavaScript allows throwing anything —
 * an `Error`, a string, a rejected fetch, `undefined`. The usual workaround is `catch (e: any)`
 * followed by `e?.message`, which silences the compiler by discarding type safety and quietly
 * renders "undefined" to the user whenever the thrown value is not an Error.
 *
 * This narrows properly instead, and always returns something worth showing.
 */

/** The message from a thrown value, or `fallback` when there is nothing readable. */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string" && error.trim()) return error;

  // Fetch wrappers and API clients often reject with a plain object carrying a message or detail.
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    for (const key of ["message", "detail", "error"] as const) {
      const value = record[key];
      if (typeof value === "string" && value.trim()) return value;
    }
  }
  return fallback;
}

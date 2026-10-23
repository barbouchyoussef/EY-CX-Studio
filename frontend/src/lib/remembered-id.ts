/**
 * Remembering which record a module was working on, across a reload.
 *
 * `localStorage` is not always available to be used: a private window, blocked site data or a
 * full quota make it *throw* on access rather than return null. Every failure here is swallowed
 * on purpose — losing the memory costs a reload landing on the wrong screen, which is not worth
 * taking the page down for.
 */

/** The id remembered under `key`, or null if there is none, it is unusable, or storage is not available. */
export function rememberedId(key: string): number | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

/** Remember `id` under `key`, or forget it when `id` is null. Never throws. */
export function rememberId(key: string, id: number | string | null): void {
  try {
    if (id === null) localStorage.removeItem(key);
    else localStorage.setItem(key, String(id));
  } catch {
    // Storage unavailable: the reload simply will not resume. See the note above.
  }
}

/** Forget whatever is stored under `key`. Never throws. */
export function forgetId(key: string): void {
  rememberId(key, null);
}

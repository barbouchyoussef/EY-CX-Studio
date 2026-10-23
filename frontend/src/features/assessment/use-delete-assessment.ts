/**
 * The delete-an-assessment confirmation: which one is pending, whether it is in flight, and why
 * it failed.
 *
 * Three flags that must agree — a pending row with no spinner, a spinner with nothing pending,
 * an error left over from a previous attempt — kept together so they cannot drift apart. The
 * caller supplies what to do once the row is gone, because removing it from the visible list is
 * the hub's business, not this one's.
 */

import { useCallback, useState } from "react";

import { authFetch } from "../../lib/api";

type Deletable = { id: number; company_name: string };

export function useDeleteAssessment(onDeleted: (id: number) => void, french: boolean) {
  const [pending, setPending] = useState<Deletable | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Open the confirmation, clearing any message left from a previous attempt. */
  const ask = useCallback((item: Deletable) => {
    setError(null);
    setPending(item);
  }, []);

  /** Close the confirmation and drop any message with it. */
  const cancel = useCallback(() => {
    setPending(null);
    setError(null);
  }, []);

  const confirm = useCallback(async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch(`/assessments/${pending.id}`, { method: "DELETE" });
      if (res.ok) {
        onDeleted(pending.id);
        setPending(null);
      } else {
        setError(
          french
            ? "Suppression impossible (vous n'êtes peut-être pas le propriétaire)."
            : "Could not delete (you may not be the owner).",
        );
      }
    } finally {
      setBusy(false);
    }
  }, [pending, onDeleted, french]);

  return { pending, busy, error, ask, cancel, confirm };
}

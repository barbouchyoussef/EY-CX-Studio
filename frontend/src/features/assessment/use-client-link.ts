/**
 * The "send this assessment to a client" form, and the link it produces.
 *
 * Five fields that only this panel touches, lifted out of the assessment hub so they are not
 * sitting among the conversation and navigation state. Creating the link stays in the hub,
 * because that step also drives the typing indicator and the shared error line; this owns the
 * fields it writes into and the copy-to-clipboard behaviour, which needs nothing else.
 */

import { useCallback, useState } from "react";

export function useClientLink() {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const copyLink = useCallback(async () => {
    if (!link) return;
    try {
      // navigator.clipboard only exists in a secure context (HTTPS or localhost). This is served
      // over plain HTTP, where it is undefined, so the legacy execCommand path is the one that
      // actually runs in production.
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(link);
      } else {
        const ta = document.createElement("textarea");
        ta.value = link;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked — the link is visible for manual copy */
    }
  }, [link]);

  const reset = useCallback(() => {
    setName("");
    setRole("");
    setEmail("");
    setLink(null);
    setCopied(false);
  }, []);

  return { name, setName, role, setRole, email, setEmail, link, setLink, copied, copyLink, reset };
}

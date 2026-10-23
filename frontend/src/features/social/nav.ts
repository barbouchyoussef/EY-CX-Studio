/**
 * Which report section the reader is currently looking at.
 *
 * Lives apart from `primitives` for a mechanical reason: React Fast Refresh only
 * works when a module exports components and nothing else, so a hook shipped alongside them
 * silently disables hot reloading for the whole file during development.
 */

import { useEffect, useState } from "react";

export type NavSection = { id: string; label: string };

/** Highlights whichever section the reader is currently in.
 *
 * Measured on scroll rather than with IntersectionObserver: sections here vary hugely in
 * height, and "the last heading I scrolled past" is the behaviour a reader expects, which
 * observer ratios do not give you for a section taller than the viewport. */
export function useActiveSection(ids: string[]): string {
  const [active, setActive] = useState(ids[0] ?? "");

  useEffect(() => {
    if (ids.length === 0) return;
    const measure = () => {
      let current = ids[0];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= 140) current = id;
      }
      // At the very bottom the last section may never cross the line; snap to it.
      if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 4) {
        current = ids[ids.length - 1];
      }
      setActive(current);
    };
    measure();
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [ids]);

  return active;
}

/** Sticky section index — stays on screen for the whole document and tracks position. */

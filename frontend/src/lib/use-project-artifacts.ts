/**
 * What is attached to the project currently open.
 *
 * Both hooks cancel on unmount, and tag the loaded result with the project it came from rather
 * than clearing state when the project changes — so one project's rows can never show as attached
 * while the next project's answer is still in flight.
 *
 * `markAttached` records an import immediately so a row does not flicker back to "unattached" for
 * the length of a round trip. The server stays the source of truth.
 */

import { useCallback, useEffect, useState } from "react";

import { useActiveProject } from "../context/ActiveProjectContext";
import { listArtifacts, type AnalysisKind, type ProjectArtifact } from "./projectsApi";

/** One shared empty set, so "nothing attached" is a stable value and never a new render. */
const NONE: ReadonlySet<string> = new Set();

type Loaded = { projectId: number; refs: Set<string> };

type ProjectArtifactRefs = {
  /** The ref ids of this kind attached to the open project. Empty when no project is open. */
  refs: ReadonlySet<string>;
  /** Record a ref as attached, immediately, after a successful import. */
  markAttached: (refId: string) => void;
};

export function useProjectArtifactRefs(kind: AnalysisKind): ProjectArtifactRefs {
  const { project } = useActiveProject();
  const projectId = project?.id;
  const [loaded, setLoaded] = useState<Loaded | null>(null);

  useEffect(() => {
    if (projectId === undefined) return;
    let cancelled = false;
    listArtifacts(projectId)
      .then((artifacts) => {
        if (cancelled) return;
        setLoaded({
          projectId,
          refs: new Set(artifacts.filter((a) => a.kind === kind).map((a) => a.ref_id)),
        });
      })
      .catch(() => {
        // The dashboard still works without this: every row reads as unattached, which is better
        // than blocking a list on a call that only decorates it.
        if (!cancelled) setLoaded({ projectId, refs: new Set() });
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, kind]);

  const markAttached = useCallback((refId: string) => {
    setLoaded((prev) => (prev ? { ...prev, refs: new Set(prev.refs).add(refId) } : prev));
  }, []);

  return {
    refs: loaded && loaded.projectId === projectId ? loaded.refs : NONE,
    markAttached,
  };
}


/**
 * Everything attached to the open project, as the artifacts themselves.
 *
 * The pipeline lists what a project holds rather than filtering a list by id, so it needs the
 * objects. Same lifecycle as the refs hook above: cancelled on unmount, and the result is tagged
 * with the project it came from so one project's results are never shown under another.
 */
export function useProjectArtifacts(): { artifacts: ProjectArtifact[]; reload: () => void } {
  const { project } = useActiveProject();
  const projectId = project?.id;
  const [loaded, setLoaded] = useState<{ projectId: number; items: ProjectArtifact[] } | null>(null);
  // Bumped to ask again after a detach or a delete, which change what the project holds.
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    if (projectId === undefined) return;
    let cancelled = false;
    listArtifacts(projectId)
      .then((items) => {
        if (!cancelled) setLoaded({ projectId, items });
      })
      .catch(() => {
        if (!cancelled) setLoaded({ projectId, items: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, reloadCount]);

  return {
    artifacts: loaded && loaded.projectId === projectId ? loaded.items : EMPTY_ARTIFACTS,
    reload: useCallback(() => setReloadCount((n) => n + 1), []),
  };
}

/** Stable empty list, so "no project" never causes a re-render on identity alone. */
const EMPTY_ARTIFACTS: ProjectArtifact[] = [];

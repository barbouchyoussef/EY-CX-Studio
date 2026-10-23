import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  getProject,
  setProjectStep,
  attachArtifact,
  type AnalysisKind,
  type Project,
  type StepKey,
  type StepStatus,
} from "../lib/projectsApi";
import { forgetId, rememberId, rememberedId } from "../lib/remembered-id";

const ACTIVE_PROJECT_KEY = "cx_active_project";

interface ActiveProjectState {
  project: Project | null;
  loading: boolean; // true only during the initial restore
  open: (p: Project) => void;
  exit: () => void;
  refresh: () => Promise<void>;
  setStepStatus: (key: StepKey, status: StepStatus) => Promise<void>;
  completeStep: (key: StepKey) => Promise<void>;
  attach: (kind: AnalysisKind, refId: string, stepKey: StepKey, title?: string) => Promise<void>;
}

const Ctx = createContext<ActiveProjectState | null>(null);

/**
 * The active project, lifted to the app root so it survives module launches (a module unmounts
 * the services hub). Backed by localStorage so a reload rejoins the same project. This is what
 * lets a tool run attach its result into the project it was launched from.
 */
export function ActiveProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore on first load from the remembered id.
  useEffect(() => {
    const id = rememberedId(ACTIVE_PROJECT_KEY);
    if (!id) {
      setLoading(false);
      return;
    }
    getProject(id)
      .then(setProject)
      .catch(() => forgetId(ACTIVE_PROJECT_KEY))
      .finally(() => setLoading(false));
  }, []);

  const open = useCallback((p: Project) => {
    setProject(p);
    rememberId(ACTIVE_PROJECT_KEY, p.id);
  }, []);

  const exit = useCallback(() => {
    setProject(null);
    forgetId(ACTIVE_PROJECT_KEY);
  }, []);

  // Read the id from storage (not closure) so callbacks are never stale.
  const refresh = useCallback(async () => {
    const id = rememberedId(ACTIVE_PROJECT_KEY);
    if (!id) return;
    try {
      setProject(await getProject(id));
    } catch {
      /* keep what we have */
    }
  }, []);

  const setStepStatus = useCallback(async (key: StepKey, status: StepStatus) => {
    const id = rememberedId(ACTIVE_PROJECT_KEY);
    if (!id) return;
    setProject((prev) => (prev ? { ...prev, steps: { ...prev.steps, [key]: status } } : prev)); // optimistic
    try {
      setProject(await setProjectStep(id, key, status));
    } catch {
      /* keep optimistic value */
    }
  }, []);

  const completeStep = useCallback((key: StepKey) => setStepStatus(key, "done"), [setStepStatus]);

  const attach = useCallback(
    async (kind: AnalysisKind, refId: string, stepKey: StepKey, title?: string) => {
      const id = rememberedId(ACTIVE_PROJECT_KEY);
      if (!id) return;
      try {
        await attachArtifact(id, { kind, ref_id: refId, step_key: stepKey, title });
        await refresh();
      } catch {
        /* attach is best-effort; a failure must never block the run's result */
      }
    },
    [refresh],
  );

  return (
    <Ctx.Provider value={{ project, loading, open, exit, refresh, setStepStatus, completeStep, attach }}>
      {children}
    </Ctx.Provider>
  );
}

export function useActiveProject(): ActiveProjectState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useActiveProject must be used within an ActiveProjectProvider");
  return ctx;
}

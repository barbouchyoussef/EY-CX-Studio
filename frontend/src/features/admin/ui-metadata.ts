/**
 * What the admin screens call things, and the shape of the reference data behind them.
 *
 * The labels, help text and placeholders for every editable field live here as data rather than
 * scattered through the forms, because they are the vocabulary the platform presents to whoever
 * maintains the framework -- and that wording gets revised far more often than the forms do.
 *
 * The server may send its own overrides. `mergeAdminUiMetadata` folds those onto these defaults
 * field by field, so a partial override changes one label without blanking the rest.
 */

export type UiFieldMetadata = {
  label: string;
  description?: string | null;
  button_label?: string | null;
  modal_title?: string | null;
  placeholder?: string | null;
  options?: { value: string; label: string; description?: string | null }[] | null;
};
export type UiSectionMetadata = {
  title: string;
  help_text?: string | null;
  fields: Record<string, UiFieldMetadata>;
};
export type AdminUiMetadata = {
  axes: UiSectionMetadata;
  capabilities: UiSectionMetadata;
  recommendations: UiSectionMetadata;
};

export function mergeAdminUiMetadata(source?: Partial<AdminUiMetadata> | null): AdminUiMetadata {
  return {
    axes: {
      ...DEFAULT_ADMIN_UI_METADATA.axes,
      ...(source?.axes ?? {}),
      fields: {
        ...DEFAULT_ADMIN_UI_METADATA.axes.fields,
        ...(source?.axes?.fields ?? {}),
      },
    },
    capabilities: {
      ...DEFAULT_ADMIN_UI_METADATA.capabilities,
      ...(source?.capabilities ?? {}),
      fields: {
        ...DEFAULT_ADMIN_UI_METADATA.capabilities.fields,
        ...(source?.capabilities?.fields ?? {}),
      },
    },
    recommendations: {
      ...DEFAULT_ADMIN_UI_METADATA.recommendations,
      ...(source?.recommendations ?? {}),
      fields: {
        ...DEFAULT_ADMIN_UI_METADATA.recommendations.fields,
        ...(source?.recommendations?.fields ?? {}),
      },
    },
  };
}

export const DEFAULT_ADMIN_UI_METADATA: AdminUiMetadata = {
  axes: {
    title: "Axes",
    help_text:
      "Axis guidance defines the high-level meaning of Manage, Analyze, and Improve. The LLM uses it as context before focusing on the selected capability.",
    fields: {
      description: {
        label: "Axis definition",
        description: "Defines what this axis means in the CX maturity model.",
        button_label: "Edit definition",
        modal_title: "Edit axis definition",
        placeholder: "Describe the scope and business meaning of this axis...",
      },
      question_guidelines: {
        label: "Axis question strategy",
        description: "Guides how the LLM should frame questions while it is inside this axis.",
        button_label: "Edit strategy",
        modal_title: "Edit axis question strategy",
        placeholder: "Write the questioning strategy for this axis...",
      },
    },
  },
  capabilities: {
    title: "Capabilities",
    help_text:
      "Capability definition, evidence signals, and question strategy shape how the LLM understands, scores, and asks about each capability.",
    fields: {
      description: {
        label: "Capability definition",
        description:
          "Defines what this capability means. The LLM uses it to understand the business intent and separate it from adjacent capabilities.",
        button_label: "Edit definition",
        modal_title: "Edit capability definition",
        placeholder: "Describe what this capability means and what business area it evaluates...",
      },
      evidence_required: {
        label: "Evidence signals",
        description:
          "Examples of concrete proof the LLM should recognize. These are semantic signals, not strict keywords.",
        button_label: "Edit signals",
        modal_title: "Edit evidence signals",
        placeholder: "List evidence signals separated by semicolons, for example: named owner; review cadence; action log...",
      },
      question_guidelines: {
        label: "Question strategy",
        description:
          "Internal guidance for how the LLM should ask about this capability. This is not a fixed client-facing script.",
        button_label: "Edit strategy",
        modal_title: "Edit question strategy",
        placeholder: "Write the internal questioning strategy used by the LLM...",
      },
    },
  },
  recommendations: {
    title: "Quick win templates",
    help_text:
      "Quick win templates are the single admin source for quick-win action direction, after text, owner hints, and sequencing hints. The before text is generated from assessment insights.",
    fields: {
      quick_win_guideline: {
        label: "Quick win action",
        description: "The practical action the quick win should recommend in the final report.",
        button_label: "Edit action",
        modal_title: "Edit quick win action",
        placeholder: "Write the practical quick-win action...",
      },
      after_text: {
        label: "Expected outcome",
        description: "The improved state or business/customer outcome after this quick win is completed.",
        button_label: "Edit outcome",
        modal_title: "Edit expected outcome",
        placeholder: "Describe the expected outcome after this quick win...",
      },
      owner_hint: {
        label: "Suggested owner",
        description: "The role most likely to own this quick win.",
        button_label: "Edit owner",
        modal_title: "Edit suggested owner",
        placeholder: "Example: CX Lead, Insights Lead, Operations Lead...",
      },
      timeline_hint: {
        label: "Timing",
        description: "When this quick win should usually happen in the quick-win sequence.",
        button_label: "Edit timing",
        modal_title: "Edit timing",
        placeholder: "Example: earliest quick win, after first routine is in place...",
      },
    },
  },
};


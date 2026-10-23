/**
 * What the consultant fills in before a guide is generated, and the rules it has to satisfy.
 *
 * Kept apart from the form that collects it, because the same rules are checked twice from two
 * different places: once when stepping forward through the form, and again when the guide is
 * finally submitted. They used to be written out in both, which is how a reworded message ends up
 * showing in only one of the two places it appears.
 */

import { interviewLabels } from "./copy";

/** The interviewee roles offered, plus "Other", which unlocks the two custom-profile fields. */
export const CUSTOM_PROFILE = "Other";

export type InterviewSetup = {
  companyName: string;
  sector: string;
  size: string;
  region: string;
  language: string;
  profile: string;
  customContext: string;
  customProfileName: string;
  customProfileDesc: string;
};

export const EMPTY_SETUP: InterviewSetup = {
  companyName: "",
  sector: "",
  size: "",
  region: "",
  language: "fr",
  profile: "CEO",
  customContext: "",
  customProfileName: "",
  customProfileDesc: "",
};

/** Something the consultant has to fix, and the form step where they can fix it. */
export type SetupProblem = { step: 1 | 2; message: string };

/** Step 1: a guide is written about a named company, so there has to be one. */
export function companyProblem(setup: InterviewSetup, isFrench: boolean): SetupProblem | null {
  const labels = interviewLabels(isFrench);
  if (setup.companyName.trim()) return null;
  return {
    step: 1,
    message: labels.companyRequired,
  };
}

/**
 * Step 2: a custom profile has to describe itself.
 *
 * The stock profiles carry their own prompt context; "Other" has none, so without a name and a
 * description the model is asked to interview a role nobody has defined.
 */
export function profileProblem(setup: InterviewSetup, isFrench: boolean): SetupProblem | null {
  const labels = interviewLabels(isFrench);
  if (setup.profile !== CUSTOM_PROFILE) return null;
  if (!setup.customProfileName.trim()) {
    return {
      step: 2,
      message: labels.customRoleRequired,
    };
  }
  if (!setup.customProfileDesc.trim()) {
    return {
      step: 2,
      message: labels.customDescriptionRequired,
    };
  }
  return null;
}

/** Everything that has to hold before a guide can be generated, in form order. */
export function setupProblem(setup: InterviewSetup, isFrench: boolean): SetupProblem | null {
  return companyProblem(setup, isFrench) ?? profileProblem(setup, isFrench);
}

# Assessment routing baseline

The maturity assessment routes each answer to a capability and a maturity level. A handful of
capability boundaries are genuinely close together, and small prompt or flow changes have
previously moved answers across them.

This document is the catalogue of those boundaries: for each one, a canonical answer and the
routing it must produce. **None of these are automated tests** — they are run by hand against a
live assessment. Treat them as the expected behaviour to check after touching prompts, the
question flow, coverage boundaries, or memory.

## Regression catalog

### 1. Journey visibility Level 1

**Purpose**

Make sure explicit absence of a shared end-to-end view maps to `Journey visibility`, not adjacent capabilities.

**Canonical answer**

`We do not have a shared end-to-end journey view today. Teams only see their own touchpoint, and we do not bring together journey feedback in a regular cross-team review.`

**Expected**

- `analyze_journey_visibility` is covered
- maturity is Level 1
- answer is not remapped to `Channel consistency` or `Feedback collection`

### 2. Feedback collection vs Channel consistency

**Purpose**

Keep capture and logging separate from cross-channel inconsistency and handoff problems.

**Canonical answer A**

`Customers often receive inconsistent information across channels, and handoffs are not managed in a standard way.`

**Expected**

- `analyze_channel_consistency` is covered
- `analyze_feedback_collection` is not covered from this answer alone

**Canonical answer B**

`We collect feedback through email, phone, and CRM cases, and all of it is logged in the same place for weekly review.`

**Expected**

- `analyze_feedback_collection` is covered
- typical maturity is Level 2
- answer is not treated as `Channel consistency`

### 3. Use of insights boundary

**Purpose**

Prevent logging and review hygiene from being mistaken for prioritization logic.

**Canonical answer A**

`Email, phone, and CRM feedback are all logged in one place and reviewed weekly.`

**Expected**

- does **not** cover `analyze_use_of_insights`
- may support `analyze_feedback_collection`

**Canonical answer B**

`We review themes weekly, identify root causes, and prioritize the issues with the biggest customer impact first.`

**Expected**

- `analyze_use_of_insights` is covered
- typical maturity is Level 3

### 4. Acting on pain points Level 1 vs Level 2

**Purpose**

Keep Improve execution maturity thresholds clean and protect the Analyze -> Improve handoff.

**Canonical answer L1**

`Teams usually react to complaints when they come in, but we do not have a shared backlog or a formal way to track who is fixing what.`

**Expected**

- `improve_acting_on_pain_points` is covered
- maturity is Level 1

**Canonical answer L2**

`We track some pain points in a shared backlog, assign owners, and follow up on actions, but prioritization and closure are still not consistent across teams.`

**Expected**

- `improve_acting_on_pain_points` is covered
- maturity is Level 2

**Guard**

- `analyze_feedback_collection` must not steal either answer

### 5. Late Analyze path quality

**Purpose**

Ensure late `Analyze` does not loop back into generic collection questions once collection basics are already known.

**Expected path behavior**

After:

- strong collection answer
- strong use-of-insights answer
- strong channel-consistency answer
- strong journey-visibility answer

the next questions should:

- move across the real remaining gaps coherently
- avoid generic "how do you capture feedback in one place?" loops
- if `Feedback collection` reopens, ask only a narrow remaining discipline such as:
  - tagging
  - categorization
  - routing
  - duplicate handling

### 6. Analyze -> Improve handoff

**Purpose**

Ensure Improve answers are not consumed by stale late-Analyze questions.

**Precondition**

- `Analyze` is mostly resolved
- only residual collection-style gap may remain
- strong collection evidence already exists in memory or recent history

**Expected**

- system advances to `Improve` before pain-point execution answer is submitted
- the question immediately before pain-point execution should already show `axis = Improve`

## Regression pack tiers

### Smoke tier

Run every time you touch:

- prompts
- question flow
- coverage logic
- memory logic
- axis handoff logic

Includes:

1. Journey visibility Level 1
2. Feedback collection vs Channel consistency
3. Use of insights boundary
4. Analyze -> Improve handoff

### Full tier

Run before release or when locking a new baseline.

Includes:

1. Journey visibility Level 1
2. Feedback collection vs Channel consistency
3. Use of insights boundary
4. Acting on pain points Level 1 vs Level 2
5. Late Analyze path quality
6. Analyze -> Improve handoff

## Rules for future changes

When changing this subsystem:

- do not retune broadly without a named failing regression
- prefer the smallest fix that repairs the failing scenario
- rerun the smoke tier after:
  - prompt edits
  - question-flow edits
  - coverage boundary edits
  - memory changes
- rerun the full tier before treating a new behavior as a fresh baseline

## Known minor quirks

These are acceptable for now and are **not** worth active tuning unless they become user-visible problems:

- some Manage transitions are still a little abstract
- `Decision-making` can still occasionally absorb evidence that feels closer to collection or review than true decision influence
- some phrasing remains variable because the question generator is still LLM-driven

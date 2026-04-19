---
name: prd-to-plan
description: Turn a PRD into a multi-phase implementation plan using tracer-bullet vertical slices, saved as a local Markdown file in ./plans/. Use when the user wants to break down a PRD, create an implementation plan, plan phases from a PRD, or mentions tracer bullets.
---

# PRD to Plan

Break a PRD into a phased implementation plan using thin vertical slices. Save the final plan as a Markdown file in `./plans/`.

## Workflow

### 1. Confirm the PRD is in context

Use the PRD already present in the conversation or a user-provided file. If the PRD is missing, ask the user to paste it or point to the file path before planning.

### 2. Explore the codebase

Read enough of the codebase to understand the current architecture, existing patterns, and likely integration boundaries. Focus on the parts that constrain planning: application structure, persistence layer, auth, external services, and testing patterns.

### 3. Identify durable architectural decisions

Before slicing the work, extract the high-level decisions that are unlikely to change during implementation. Put these in the plan header so later phases can reference them consistently.

Common durable decisions:

- Route structures or URL patterns
- Database schema shape
- Key data models
- Authentication and authorization approach
- Third-party service boundaries

If a decision is still unknown, mark it explicitly as a proposed decision or open question instead of pretending it is settled.

### 4. Draft tracer-bullet vertical slices

Break the PRD into phases where each phase is a thin but complete end-to-end slice through the system. Avoid horizontal phases such as "database first" or "frontend first."

Apply these rules:

- Make each slice complete across all relevant layers such as schema, API, UI, and tests.
- Make each slice independently demoable or verifiable.
- Prefer more thin slices over fewer thick ones.
- Exclude specific file names, function names, and implementation details that are likely to change.
- Include durable decisions such as route paths, schema shapes, and stable model names.

### 5. Quiz the user on granularity

Present the proposed phase breakdown as a numbered list before writing the file.

For each phase include:

- **Title**: short descriptive name
- **User stories covered**: the user stories or PRD requirements addressed by that phase

Ask the user:

- Does the granularity feel right: too coarse or too fine?
- Should any phases be merged or split further?

Iterate until the user approves the breakdown.

### 6. Write the plan file

Create `./plans/` if it does not exist. Name the Markdown file after the feature using a stable, lowercase, hyphenated slug such as `./plans/user-onboarding.md`.

Use this template:

```md
# Plan: <Feature Name>

> Source PRD: <brief identifier or link>

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: ...
- **Schema**: ...
- **Key models**: ...
- **Auth**: ...
- **External services**: ...

---

## Phase 1: <Title>

**User stories**: <list from PRD>

### What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

### Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

---

## Phase 2: <Title>

**User stories**: <list from PRD>

### What to build

...

### Acceptance criteria

- [ ] ...
```

Repeat the phase section for as many slices as needed.

## Quality bar

- Keep phases sequenced so each one de-risks or unlocks the next.
- Keep acceptance criteria observable and testable.
- Prefer user-visible behavior over internal implementation milestones.
- Keep the plan concrete enough to execute, but not so specific that it hard-codes volatile implementation details.

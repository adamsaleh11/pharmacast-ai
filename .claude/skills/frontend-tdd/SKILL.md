---
name: frontend-tdd
description: Production frontend implementation and QA workflow for pages, dashboards, forms, feeds, UI features, and component systems. Use when Codex needs to build frontend features from a PRD, implementation plan, or existing codebase context with clean component architecture, complete UI states, responsive behavior, accessibility basics, visual consistency, and a mandatory QA/polish pass. Do not use for backend logic, API design, heavy algorithmic work, or complex validation logic where test-driven development is the better fit.
---

# Frontend Build + QA

## Purpose

Implement frontend features from a PRD or plan with clean architecture, consistent UI, production-level UX quality, and a structured QA/polish pass.

Prioritize:

- clarity of components
- correctness of UI states
- responsiveness
- real-world usability
- visual and structural quality

## Inputs

Use the available source of truth in this order:

1. Approved PRD
2. PRD-to-plan output or implementation plan
3. Existing codebase context
4. Existing design system and component library

If the PRD or plan conflicts with the codebase's established design system, preserve the product requirement while matching the local implementation style.

## Phase 1: Implementation

### Structure First

- Create the component hierarchy before coding UI details.
- Separate page-level layout, reusable components, hooks, and data helpers.
- Keep components small and composable.
- Use existing folders and conventions before adding new structure.

### Strict Component Contracts

Each component must:

- define typed props
- avoid implicit dependencies
- avoid mixing unrelated responsibilities
- be reusable where reuse is natural

Do not add abstractions just to make code look generic. Extract only when it reduces real duplication or clarifies ownership.

### State Management Discipline

- Keep state as local as possible.
- Lift state only when multiple components genuinely need it.
- Avoid messy prop drilling; use context or an existing store only when it clarifies flow.
- Separate UI state from server state.
- Use React Query or the repo's equivalent for async server state.

### Data Fetching And Separation

- Keep fetching/mutation logic out of UI-heavy components.
- Prefer existing API clients, query hooks, DTOs, and route conventions.
- Handle loading, error, empty, and success states explicitly.
- Preserve existing cache invalidation and optimistic update patterns where present.

### Required UI States

Every feature must include:

- loading state, using skeletons/spinners consistent with the app
- empty state, with an obvious next action where applicable
- error state, with graceful recovery or retry where applicable
- success state, including post-action feedback when useful

Do not treat these as optional polish. They are part of the feature.

### Styling And Design Consistency

- Follow the existing design system strictly.
- Use Tailwind and component-library patterns consistently.
- Preserve spacing rhythm, typography hierarchy, color semantics, and density.
- Do not introduce new one-off styles unless the feature truly requires them.
- Avoid visible instructional text that explains the UI instead of making the UI self-evident.

### Responsiveness

- Design for mobile, tablet, and desktop during implementation.
- Use responsive utilities intentionally from the start.
- Prevent overflow, cramped controls, unreadable text, and broken stacking.
- Verify fixed-format controls have stable dimensions so labels, hover states, and dynamic values do not shift layout.

### Accessibility Basics

- Use semantic HTML.
- Associate labels with inputs.
- Make buttons and controls identifiable.
- Preserve keyboard access and visible focus states.
- Avoid interactions that only work with hover or visual position.

### Clean Code Rules

- Remove dead code.
- Remove unused props and imports.
- Avoid console logs.
- Use clear domain names instead of vague names like `data`, `thing`, or `item` when the meaning is known.
- Keep files readable and organized.

## Phase 2: QA + Polish

Run this phase after implementation. Do not skip it.

### UX Validation

- Confirm the feature makes sense to the target user.
- Confirm flows are intuitive.
- Confirm actions are obvious and feedback is timely.

### Visual Consistency Check

- Check spacing alignment.
- Check typography consistency.
- Check button and control treatment.
- Remove visual noise.
- Ensure the feature fits the surrounding product, not just the immediate file.

### Edge Case Review

- Check empty data.
- Check long text.
- Check slow network behavior when practical.
- Check errors and failed mutations.
- Check disabled, pending, and completed action states.

### Responsiveness Audit

- Test relevant breakpoints.
- Fix overflow, stacking issues, clipped content, and spacing collapse.
- Prefer real viewport inspection or screenshots when the app can run locally.

### Component Quality Check

- Remove duplicated logic.
- Confirm props are minimal and clear.
- Confirm component boundaries match responsibilities.
- Keep reusable pieces reusable without over-generalizing.

### Performance Sanity Check

- Avoid unnecessary re-renders.
- Avoid heavy logic in render.
- Memoize only when it solves a visible or measurable issue.
- Lazy-load only when appropriate for the repo and user flow.

## Verification

Use the strongest practical verification available in the repo:

- Run type checks, lint, and focused frontend tests when scripts exist.
- Run the app locally when the feature needs visual inspection.
- Use browser or screenshot checks for layout-sensitive work.
- Report any verification that could not be run and why.

## Output Requirements

The completed feature must:

- match the PRD or plan requirements
- include all UI states
- work across mobile, tablet, and desktop
- follow the existing design system
- remain clean and maintainable
- be production-ready rather than prototype-quality

## Hard Rules

- Do not skip the QA phase.
- Do not improvise beyond the PRD without stating the justification.
- Do not over-engineer abstractions.
- Do not ignore edge states.
- Do not break existing UI consistency.
- Do not prioritize speed over clarity.

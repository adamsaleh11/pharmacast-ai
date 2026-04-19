---
name: write-a-prd
description: Create a concrete PRD through user interview, codebase exploration, and module design. Use when the user wants to write a PRD, create a product requirements document, or plan a new feature in enough detail that it can be converted into an implementation plan.
---

Create a PRD that is specific enough to hand off into planning. Skip steps only when they are clearly unnecessary.

1. Ask the user for a detailed description of the problem, the desired outcome, constraints, deadlines, and any early solution ideas.

2. Explore the repo to verify assumptions, understand the current system, and find the modules, interfaces, and patterns that are likely to be affected.

3. Interview the user rigorously until the problem, scope, edge cases, tradeoffs, and rollout expectations are clear enough to write a concrete document. Resolve dependencies between decisions one by one instead of leaving vague placeholders.

4. Sketch the major modules that will need to be built or modified. Prefer deep modules: units that hide substantial complexity behind simple, stable, testable interfaces.

5. Check that the proposed modules match the user's expectations. Confirm which modules should have explicit testing coverage called out in the PRD.

6. Write the PRD using the template below. Make it concrete, implementation-aware, and easy to translate into a later execution plan.

<prd-template>

## Problem Statement

Describe the problem from the user's perspective. Include the current pain, who is affected, and why this matters now.

## Solution

Describe the proposed solution from the user's perspective. Explain the intended behavior and outcome without drifting into low-level code details.

## User Stories

Write a long, numbered list of user stories that covers the full surface area of the feature.

Each user story should follow this format:

1. As an <actor>, I want a <feature>, so that <benefit>

Example:

1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending.

Cover happy paths, edge cases, permissions, failures, onboarding, migration, and admin or operational workflows when relevant.

## Implementation Decisions

List the implementation decisions that have been made. Include:

- The modules that will be built or modified
- The interfaces of those modules that will change
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific user or system interactions

Do not include specific file paths or code snippets. They become stale quickly and belong in the plan, not the PRD.

## Testing Decisions

List the testing decisions that have been made. Include:

- What makes a good test for this work: test external behavior and contracts, not implementation details
- Which modules or flows should be tested
- Prior art in the codebase for similar tests when available

## Out of Scope

Describe the work that is explicitly not part of this PRD so the plan has a clean boundary.

## Further Notes

Capture assumptions, rollout concerns, dependencies, open questions, or follow-up work that should survive into planning.

</prd-template>

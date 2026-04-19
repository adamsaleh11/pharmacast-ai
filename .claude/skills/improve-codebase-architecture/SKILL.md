---
name: improve-codebase-architecture
description: Explore a codebase to find opportunities for architectural improvement, with emphasis on making the codebase more testable by deepening shallow modules. Use when the user wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, make a codebase more AI-navigable, or turn architectural analysis into a GitHub issue RFC.
---

# Improve Codebase Architecture

Explore the codebase the way an AI agent experiences it, surface architectural friction, and turn promising deep-module refactors into concrete RFCs.

A deep module, in the Ousterhout sense, exposes a small interface that hides substantial implementation complexity. Favor designs that reduce seam complexity, improve testability at the boundary, and make the codebase easier to navigate.

## Process

### 1. Explore the codebase

Explore organically. Do not force a rigid checklist. The friction you experience while tracing concepts is the primary signal.

Prefer spawning one or more `explorer` subagents to investigate different subsystems in parallel. Give each explorer a concrete slice of the codebase or question. Ask them to report:

- Where understanding one concept requires bouncing between many small files
- Which modules are so shallow that the interface is nearly as complex as the implementation
- Where pure functions were extracted for testability but the real risk lives in how callers compose them
- Which tightly-coupled modules create integration risk in their seams
- Which areas are untested or difficult to test at a useful boundary

Do not jump to interface design in this step. First identify where the architecture fights comprehension or testing.

### 2. Present candidates

Present a numbered list of deepening opportunities. For each candidate, include:

- **Cluster**: modules, files, or concepts involved
- **Why they are coupled**: shared types, call patterns, state ownership, sequencing, or co-ownership of a concept
- **Dependency category**: classify it using [reference.md](reference.md)
- **Test impact**: which current unit tests could be replaced by boundary tests at the deeper module interface

Do not propose interfaces yet. End with: `Which of these would you like to explore?`

### 3. Let the user pick a candidate

Do not continue interface design until the user chooses one candidate.

### 4. Frame the problem space

Write a user-facing explanation of the constraints before launching design work. Include:

- Constraints a new interface must satisfy
- Dependencies it must rely on or absorb
- A rough illustrative code sketch that makes the constraints concrete

Treat the sketch as a framing device, not as the proposal. Show it to the user, then continue immediately to parallel design work so the user can think while agents run.

### 5. Design multiple interfaces

Spawn at least 3 `worker` or `explorer` subagents in parallel. Each must produce a meaningfully different interface for the deepened module. Give each agent:

- Relevant file paths and coupling details
- The dependency category
- The complexity that should be hidden inside the deepened module
- A distinct design constraint

Use these design constraints:

- Agent 1: minimize the interface, ideally 1 to 3 entry points
- Agent 2: maximize flexibility across multiple use cases
- Agent 3: optimize for the most common caller and make the default path trivial
- Agent 4: if the dependency category warrants it, design around ports and adapters

Require each design to include:

- Interface signature with types, methods, and parameters
- A usage example from the caller perspective
- The internal complexity hidden behind the boundary
- The dependency strategy, using the categories from [reference.md](reference.md)
- Clear trade-offs

Present the designs sequentially, then compare them in prose. After the comparison, recommend one design explicitly. If a hybrid is stronger, propose the hybrid and explain why.

### 6. Let the user pick an interface

Accept either a direct user choice or explicit approval of your recommendation.

### 7. Create the RFC issue

Create a GitHub issue for the refactor RFC. Use the issue template from [reference.md](reference.md).

Prefer the GitHub connector when available. Otherwise use `gh issue create`. Do not stop for a draft review unless the user explicitly asks for one. After creation, share the issue URL.

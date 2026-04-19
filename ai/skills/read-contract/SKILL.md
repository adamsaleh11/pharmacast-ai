---
name: read-contract
description: Ingest provided implementation handoff contracts, markdown contract files, API specs, or feature documentation before asking implementation questions or starting grill-me. Use when documentation is provided as source-of-truth context for a planned implementation, integration, follow-up feature, or architecture grilling session.
---

# Read Contract

## Mandatory Outcome

Before asking implementation questions or invoking the normal grill-me process, first perform a Handoff Ingestion step whenever handoff documentation is provided.

Read the handoff material and convert it into a precise working understanding of what already exists and what the implementation must respect.

## Handoff Ingestion Process

### 1. Read and Normalize the Handoff

Read the provided handoff contract or documentation and extract the source-of-truth details.

Identify and restate:

- feature summary
- ownership boundaries
- interfaces already implemented
- routes/endpoints already finalized
- DTOs or payload shapes already finalized
- enums/status values already finalized
- files/modules/services already created
- environment/config assumptions
- security/auth assumptions
- known limitations, mocks, TODOs, and undecided items

### 2. Produce a Handoff Understanding Summary

Output a clear section titled:

```markdown
# Handoff Understanding Summary
```

It must contain:

```markdown
## A. What Already Exists

List only concrete implemented or finalized things you can rely on.

## B. What I Must Not Change

List route names, DTO names, interfaces, schemas, behaviors, or contracts that should be treated as fixed unless explicitly changed.

## C. What I Am Responsible For

State exactly what your current task owns.

## D. Dependencies I Will Rely On

List upstream/downstream systems, files, endpoints, contracts, or modules you expect to use.

## E. Gaps / Ambiguities / Risks

List anything unclear, missing, contradictory, mocked, or undecided.

## F. Assumptions I Will Use Unless Corrected

If something is not fully specified, state the exact assumption you will use.

## G. Readiness Verdict

Choose one:

- READY FOR GRILLING
- NEEDS CLARIFICATION BEFORE GRILLING
```

If the verdict is `READY FOR GRILLING`, continue into the normal grill-me process. If the verdict is `NEEDS CLARIFICATION BEFORE GRILLING`, ask only the minimum high-value clarification questions.

### 3. Extract the Integration Contract

Before grilling, explicitly restate the exact integration points relevant to the work.

Include as relevant:

- routes to call
- request payloads to send
- response fields to consume
- events to publish/subscribe to
- components/hooks/functions to reuse
- DB tables/entities/schemas to depend on
- env vars required
- auth/permission requirements
- status/error/loading states to handle

### 4. Conflict Detection

Explicitly check for these problems:

- route/path mismatches
- DTO/payload mismatches
- enum/status mismatches
- auth assumption mismatches
- service ownership confusion
- missing required fields
- mock behavior being treated as final behavior
- undocumented breaking changes

If any are found, list them under:

```markdown
## H. Contract Conflicts Detected
```

If none are found, explicitly say:

```markdown
## H. Contract Conflicts Detected

No contract conflicts detected.
```

### 5. State What Will Be Used Going Forward

At the end of the handoff ingestion step, include:

```markdown
# What I Will Use Going Forward

- the exact contract elements I will treat as fixed
- the exact unclear elements I will ask about
- whether I am ready to proceed to grill-me
```

### 6. Only Then Start Grill-Me

After handoff ingestion is complete, continue with the normal implementation flow:

- ask critical architecture questions
- ask edge-case questions
- ask data-contract questions
- propose implementation plan
- then implement

## Rules

- Do not skip handoff ingestion when documentation is provided.
- Do not immediately start coding.
- Do not immediately start asking general questions.
- First prove understanding of the existing contract.
- Treat the handoff document as source of truth unless it contains conflicts or clear gaps.
- If something is mocked, say `MOCKED`.
- If something is undecided, say `UNDECIDED`.
- If something is missing, say `NOT SPECIFIED`.
- Be exact with field names, route names, DTO names, file paths, and enum values.
- Do not invent compatibility where the contract is unclear.

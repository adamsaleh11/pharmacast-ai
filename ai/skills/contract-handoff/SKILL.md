---
name: contract-handoff
description: Generate a complete Implementation Handoff Contract after completing any implementation task. Use when the user asks for contract-handoff, implementation handoff documentation, completion criteria documentation, source-of-truth engineering docs, or requires creating docs/contracts/feature-slug.md with the final contract shown in chat.
---

# Contract Handoff

## Mandatory Outcome

After completing any implementation task, generate a complete Implementation Handoff Contract and save it as markdown documentation for the rest of the team.

Do both:

- Output the full contract in chat.
- Create or update `docs/contracts/<feature-slug>.md`.

Create `docs/contracts/` if it does not exist. The markdown file must be source-of-truth engineering documentation that another engineer can use without reading prior chat context.

## Workflow

1. Inspect the completed implementation before writing the contract. Use changed files, routes, DTOs, migrations, models, config, tests, and verification output as the source of truth.
2. Choose a stable lowercase hyphen-case `<feature-slug>` from the implementation. If there is no safe slug, ask the user before writing the file.
3. Fill every section with exact names and shapes from the implementation. Do not invent routes, DTOs, enum values, status values, env vars, or ownership details.
4. If a section is not applicable, say so explicitly using `NOT IMPLEMENTED`, `No public interface was added`, or `No integrations were added`, as appropriate.
5. If something is undecided, write `UNDECIDED` and describe the missing decision.
6. If something is mocked, write `MOCKED` and describe the mock and where it lives.
7. Save the contract to `docs/contracts/<feature-slug>.md`.
8. Ensure the markdown file content exactly matches the contract shown in chat.
9. End the response with the final file path, whether it was created or updated, and a 3-line "read this first" note for the next engineer.

## Quality Rules

- Do not be vague.
- Do not say "standard behavior" or "usual handling".
- Use exact field names, exact route names, exact interface names, and exact file paths.
- If something is intentionally omitted, say `NOT IMPLEMENTED`.
- If there are multiple valid integration paths, state which one was actually implemented.
- Write clean markdown that is easy to scan.

## Contract Structure

Use exactly this structure:

```markdown
# Implementation Handoff Contract

## 1. Summary

- What was implemented
- Why it was implemented
- What is in scope
- What is out of scope
- Which repo/service/module owns this implementation

## 2. Files Added or Changed

For each important file:

- file path
- whether it was created, updated, renamed, or deleted
- one-line purpose
- notable implementation details if needed

## 3. Public Interface Contract

Document every interface that another engineer, service, or UI might rely on.

Include anything relevant such as:

- HTTP endpoints
- RPC methods
- CLI commands
- queue jobs
- cron jobs
- exported functions
- reusable components
- hooks
- SDK methods
- event emitters
- webhooks
- file formats
- config contracts

For each interface, provide:

- name
- type
- purpose
- owner
- inputs
- outputs
- required fields
- optional fields
- validation rules
- defaults
- status codes or result states
- error shapes
- example input
- example output

If no public interface was added, say that explicitly.

## 4. Data Contract

Document all data structures introduced or changed.

Include as relevant:

- database tables
- schemas
- DTOs
- entities
- models
- enums
- JSON shapes
- form payloads
- cache keys
- message/event payloads
- files generated or consumed

For each:

- exact name
- fields
- field types
- required vs optional
- allowed values
- defaults
- validation constraints
- migration notes
- backward compatibility notes

## 5. Integration Contract

Document how this implementation interacts with other parts of the system.

Include:

- upstream dependencies
- downstream dependencies
- services called
- endpoints hit
- events consumed
- events published
- files read or written
- environment assumptions
- auth assumptions
- retry behavior
- timeout behavior
- fallback behavior
- idempotency behavior if relevant

If there are no integrations, say that explicitly.

## 6. Usage Instructions for Other Engineers

Write concrete instructions for another engineer who needs to build on top of this work.

Include:

- what they can rely on
- what they should call/import/use
- what inputs they must provide
- what outputs they will receive
- what loading, empty, success, and failure states to handle
- what is finalized
- what is still provisional
- what is mocked or stubbed
- what must not be changed without coordination

## 7. Security and Authorization Notes

Document anything relevant about:

- auth requirements
- permission rules
- tenancy rules
- role checks
- data isolation
- sensitive fields
- sanitization
- forbidden fields
- logging restrictions
- compliance concerns

If none apply, say that explicitly.

## 8. Environment and Configuration

List every environment variable, config key, feature flag, secret, or runtime setting used by this implementation.

For each:

- exact name
- purpose
- required or optional
- default behavior if missing
- dev vs prod notes if relevant

## 9. Testing and Verification

Document:

- tests added or updated
- what was manually verified
- how to run the tests
- how to locally validate the feature
- known gaps in test coverage

## 10. Known Limitations and TODOs

Document:

- unfinished edges
- temporary assumptions
- known bugs
- performance limitations
- mock behavior
- compatibility risks
- follow-up tasks

## 11. Source of Truth Snapshot

This section must be short and highly scannable.

Include:

- final interface names
- final route names if applicable
- final DTO/model names
- final enum/status values
- final event names if applicable
- final file paths of key implementation pieces
- breaking changes from previous version, if any

## 12. Copy-Paste Handoff for the Next Engineer

Write a short section addressed to the next engineer.

It must say:

- what is already done
- exactly what is safe to depend on
- exactly what remains to be built
- any traps, gotchas, or assumptions
- what they should read first in this contract
```

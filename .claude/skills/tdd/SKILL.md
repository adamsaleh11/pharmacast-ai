---
name: tdd
description: Test-driven development with a strict red-green-refactor loop. Use when the user wants to build a feature or fix a bug test-first, mentions TDD or red-green-refactor, asks for integration-style tests, or wants behavior specified through public interfaces instead of implementation details.
---

# Test-Driven Development

## Overview

Use TDD as a sequence of small vertical slices. Drive each change with one failing behavior-level test, add the minimum code to pass, then refactor only while the suite is green.

## Philosophy

Prefer tests that verify behavior through public interfaces instead of implementation details. Let tests read like executable specifications of capabilities the system must provide.

Good tests:

- Exercise real code paths through stable public interfaces
- Describe observable behavior instead of internal sequencing
- Survive refactors that preserve behavior
- Use names that state capabilities, such as `user can checkout with valid cart`

Bad tests:

- Assert on private methods or internal collaborators
- Break on harmless refactors
- Reach through the public API to inspect internals
- Overuse mocks to restage the implementation instead of exercising the system

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidance.

## Avoid Horizontal Slices

Do not write all tests first and all implementation later. Treat RED and GREEN as a repeated vertical slice, not as separate phases.

Wrong:

```text
RED:   test1, test2, test3, test4
GREEN: impl1, impl2, impl3, impl4
```

Right:

```text
RED->GREEN: test1 -> impl1
RED->GREEN: test2 -> impl2
RED->GREEN: test3 -> impl3
```

Writing tests in bulk encourages imagined behavior, brittle structure assertions, and premature commitment to APIs that have not been proven yet.

## Workflow

### 1. Plan the seam

Before editing code:

- Confirm the public interface or observable entry point to drive
- Confirm which behaviors matter most to the user
- Prefer a narrow interface with deep implementation
- Design for testability before adding volume
- List behaviors to test instead of implementation steps

Use [deep-modules.md](deep-modules.md) and [interface-design.md](interface-design.md) when deciding where the test seam should live.

Ask directly for missing product intent. Typical prompts:

- `What public interface should this change affect?`
- `Which behaviors matter most to verify first?`

### 2. Write one tracer bullet

Write one test that proves one important behavior end to end.

Required sequence:

```text
RED:   write one failing test for one behavior
GREEN: add the minimum code required to pass it
```

Use the first passing test as a tracer bullet that proves the path works through the real interface.

### 3. Repeat in small slices

For each next behavior:

```text
RED:   write the next failing test
GREEN: add only enough code to pass
```

Apply these rules:

- Keep one test in flight at a time
- Add no speculative functionality
- Prefer integration-style coverage unless a narrower test is clearly better
- Stop and reshape the interface if the next test becomes awkward for the wrong reason

### 4. Refactor only while green

After the current test set passes:

- Remove duplication
- Deepen modules by moving complexity behind simpler interfaces
- Improve names and boundaries
- Re-run the relevant tests after each refactor step

Never refactor while red. Reach green first, then restructure safely.

See [refactoring.md](refactoring.md) for a compact refactor checklist.

## Checklist Per Cycle

Use this list before moving to the next slice:

- Test describes behavior instead of implementation
- Test drives the public interface only
- Test would survive an internal refactor
- Production code is minimal for the current test
- No future behavior was implemented early

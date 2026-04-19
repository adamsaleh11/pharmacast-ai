# Reference

## Dependency Categories

When assessing a candidate for deepening, classify its dependencies:

### 1. In-process

Pure computation, in-memory state, no I/O. Always deepenable. Merge the modules and test directly.

### 2. Local-substitutable

Dependencies that have local test stand-ins, such as PGLite for Postgres or an in-memory filesystem. Deepenable if the test substitute exists. Test the deepened module with the local stand-in running in the test suite.

### 3. Remote but owned (Ports & Adapters)

Your own services across a network boundary, such as microservices or internal APIs. Define a port at the module boundary. Let the deep module own the logic and inject the transport. Test with an in-memory adapter. Use the real HTTP, gRPC, or queue adapter in production.

Recommendation shape: "Define a shared interface (port), implement an HTTP adapter for production and an in-memory adapter for testing, so the logic can be tested as one deep module even though it is deployed across a network boundary."

### 4. True external (Mock)

Third-party services you do not control, such as Stripe or Twilio. Mock at the boundary. Let the deepened module take the external dependency as an injected port, and provide a mock implementation in tests.

## Testing Strategy

The core principle: **replace, don't layer.**

- Old unit tests on shallow modules are waste once boundary tests exist. Delete them.
- Write new tests at the deepened module interface boundary.
- Assert on observable outcomes through the public interface, not internal state.
- Ensure tests survive internal refactors by describing behavior, not implementation.

## Issue Template

```md
## Problem

Describe the architectural friction:

- Which modules are shallow and tightly coupled
- What integration risk exists in the seams between them
- Why this makes the codebase harder to navigate and maintain

## Proposed Interface

The chosen interface design:

- Interface signature (types, methods, params)
- Usage example showing how callers use it
- What complexity it hides internally

## Dependency Strategy

Which category applies and how dependencies are handled:

- **In-process**: merged directly
- **Local-substitutable**: tested with [specific stand-in]
- **Ports & adapters**: port definition, production adapter, test adapter
- **Mock**: mock boundary for external services

## Testing Strategy

- **New boundary tests to write**: describe the behaviors to verify at the interface
- **Old tests to delete**: list the shallow module tests that become redundant
- **Test environment needs**: any local stand-ins or adapters required

## Implementation Recommendations

Durable architectural guidance that is not coupled to current file paths:

- What the module should own (responsibilities)
- What it should hide (implementation details)
- What it should expose (the interface contract)
- How callers should migrate to the new interface
```

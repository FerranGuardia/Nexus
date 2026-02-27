# Code Audit Research — Functional Analysis, Not Style

Research compiled Feb 2026. Focus: dead code, connection integrity, optimization, magic values.
Explicitly excluded: readability, formatting, organization, docstrings, naming conventions.

---

## The Core Insight

Traditional linters catch style. LLMs catch semantics. The state of the art (2025-2026) is a **hybrid pipeline**:

```
Static/Structural Pass (AST, grep, import graph)  →  fast, deterministic
        ↓
LLM Reasoning Pass (cross-file, semantic)          →  catches what tools miss
        ↓
Validation Pass (verify findings against code)     →  filters hallucinations
        ↓
Actionable Report
```

Key papers: RepoAudit (ICML 2025), IRIS (ICLR 2025), Skylos (hybrid AST+LLM).

---

## 1. Dead Code Detection

### What Counts as Dead Code

| Type | Example | Detection Method |
|------|---------|-----------------|
| Unused imports | `import os` never used | AST definition-use analysis |
| Unreachable branches | Code after `return`/`raise` | Control flow analysis |
| Uncalled functions | `def helper():` never invoked | Call graph reachability |
| Dead variables | `x = compute()` never read | Data-flow (def-use chains) |
| Stale feature flags | `if FEATURE_X:` always True | Constant propagation |
| Commented-out code | `# old_function()` | Heuristic: comments that parse as valid code |
| Orphaned files | `utils_old.py` imported by nothing | Import graph: zero incoming edges |
| Unused exports | `export function foo` never imported | Cross-file import tracing |
| Dead config entries | ENV var set but never read | Config-code cross-reference |

### The Algorithm

1. **Build entry points**: main functions, exported API handlers, test files, framework-registered routes (decorators, config)
2. **Build call/import graph**: trace from entry points through all imports and function calls
3. **Mark reachable**: everything touched from an entry point is alive
4. **Report unreachable**: everything not marked is dead
5. **Framework filter**: suppress false positives from decorators, DI containers, plugin systems, pytest fixtures

### Tools by Language

| Language | Best Tool | Approach |
|----------|-----------|----------|
| Python | **Vulture** (56% precision, 83% recall) | AST-based def-use |
| Python | **Skylos** (76% precision, 100% recall) | AST + optional LLM validation |
| JS/TS | **Knip** | Mark-and-sweep from entry points, 80+ framework plugins |
| Go | **deadcode** (official) | Rapid Type Analysis from `main` |
| Rust | `rustc` built-in | Compiler warnings for unused items |
| Any | **Skylos** | Supports Python, TS, Go |

### What LLMs Add

Traditional tools miss:
- Framework magic (decorators, convention-based loading, annotation registration)
- Dynamic dispatch (`getattr`, `eval`, reflection)
- Semantic dead code: function exists and is called, but its return value is always ignored
- "Zombie code": technically reachable but never exercised in any real user flow

LLMs can reason about whether something is *semantically* dead even if it's structurally reachable. Skylos demonstrated this: LLM validation eliminates **84.6% of false positives** with no recall cost.

### Practical Heuristics (No Tools Needed)

```
1. grep for all `def `/ `function `/ `fn ` definitions → list all functions
2. For each function, grep for its name across the codebase
3. If only found at its definition → candidate dead code
4. Check for framework registration patterns that reference it indirectly
5. Flag commented-out blocks that parse as valid code
6. Find files with zero incoming imports (orphans)
```

---

## 2. Connection Integrity

### What Can Be Mis-Wired

| Connection Type | What Goes Wrong | How to Detect |
|-----------------|-----------------|---------------|
| Route registration | Handler registered but wrong signature | Cross-ref route table vs handler params |
| Event handlers | `.on('event', fn)` but fn doesn't exist or has wrong arity | Resolve all callback references |
| Middleware chain | Middleware registered in wrong order or missing | Trace the chain, compare to expected |
| DI wiring | Provider registered but consumer expects different type | Build dependency graph, check types |
| DB model usage | Schema declares field X but code never reads/writes it | Cross-ref model fields vs query usage |
| Signal/slot | Signal emitted but no listener, or listener for non-existent signal | Match emitters to receivers |
| Config references | Code reads `config.X` but config file doesn't define X | Cross-ref config reads vs definitions |
| Import chains | Module A should import B for side effects but doesn't | Trace initialization order |

### Why This Is LLM Territory

This is where LLMs **massively outperform** traditional tools. Traditional static analysis can verify structural correctness (types match, function exists) but cannot verify:

- Does the handler's logic match what the route URL implies?
- Is the middleware ordering correct for the business requirement?
- Does the event handler actually handle the event it's registered for, or does it handle something else?
- Is the DB model's field used consistently with its intended semantics?

### Systematic Approach

```
For each module:
  1. List all registrations (routes, events, signals, DI bindings, config reads)
  2. For each registration:
     a. Does the target exist? (structural)
     b. Does the target's signature match what the framework expects? (structural)
     c. Does the target's behavior match the registration's semantics? (LLM)
  3. List all config/env reads → verify each has a corresponding definition
  4. List all imports → verify each imported name is actually used
  5. Check for orphan registrations (registered but framework never invokes)
```

### Cross-File Pattern

The critical pattern is **registration-usage cross-reference**:

```
REGISTERED = {routes, events, middleware, DI bindings, config keys}
IMPLEMENTED = {handlers, listeners, middleware fns, providers, config defs}
ACTUALLY_USED = {what the framework/runtime invokes}

Missing:     REGISTERED - IMPLEMENTED     (handler referenced but doesn't exist)
Orphaned:    IMPLEMENTED - REGISTERED     (handler exists but never registered)
Dead:        REGISTERED - ACTUALLY_USED   (registered but framework never calls it)
```

---

## 3. Optimization Opportunities

### The Patterns

| Pattern | Description | Detection Heuristic |
|---------|-------------|---------------------|
| **N+1 queries** | DB query inside a loop over query results | Query call inside `for`/`while` that iterates over prior query |
| **Redundant computation** | Same expression evaluated multiple times | Identical calls with identical args in same scope |
| **Missing memoization** | Pure function called repeatedly with same args | Function with no side effects, called from hot path |
| **Wrong data structure** | `x in list` when `x in set` would be O(1) | Membership test on list inside loop |
| **Loop-invariant code** | Computation in loop that doesn't depend on loop var | All operands defined before loop, not modified inside |
| **Sequential independence** | Sequential `await`s that don't depend on each other | Second call doesn't use result of first |
| **Over-fetching** | `SELECT *` when only 2 fields needed | Query returns N fields, code uses M where M << N |
| **String concat in loop** | `s += x` in a loop instead of join/builder | String concatenation assignment inside loop body |
| **Repeated work** | Same file read/API call/computation in multiple places | Identical I/O operations without caching |

### What LLMs Can Do Here

LLMs excel at recognizing these patterns because they require **understanding data flow across statements**, not just syntax:

```python
# An LLM sees this as N+1 immediately:
users = db.query(User).all()
for user in users:
    orders = db.query(Order).filter(Order.user_id == user.id).all()  # N+1!

# A linter sees two query calls and doesn't connect them.
```

The LLM understands that:
- The loop iterates over DB results
- Each iteration executes another query
- The inner query could be a JOIN or subquery instead

### Systematic Approach

```
For each function:
  1. Identify all I/O operations (DB, network, file, IPC)
  2. Check if any are inside loops → N+1 or repeated I/O
  3. Check for sequential independent I/O → parallelizable
  4. Identify all collections → check for wrong data structure usage
  5. Identify loop bodies → look for invariant expressions to hoist
  6. Check for string concatenation in loops
  7. Look for repeated identical computations across the function

For the module:
  8. Check for computations that could be cached across calls
  9. Look for data loaded but only partially used (over-fetch)
```

---

## 4. Magic Strings & Hardcoded Values

### What to Flag

| Type | Example | Risk |
|------|---------|------|
| Hardcoded URLs | `fetch("https://api.prod.example.com/v2")` | Environment coupling |
| Scattered timeouts | `timeout=30` in 5 different files | Inconsistent behavior |
| Duplicated error messages | `"Invalid input"` in 12 places | Inconsistent UX, hard to i18n |
| Inline config | `if retries > 3:` | Hidden business rule |
| Environment values | `host = "prod-db.internal"` | Won't work in other envs |
| Magic numbers | `if status == 42:` | Opaque meaning |
| Duplicated constants | `MAX_RETRIES = 3` in file A, `max_retries = 3` in file B | Drift risk |
| String-typed enums | `if role == "admin":` in multiple places | Typo-prone, no completion |

### Detection Approach

**Step 1 — Extract all literals:**
Walk the AST (or grep), collect every string/number literal with file:line.

**Step 2 — Frequency analysis:**
Group identical literals. Anything appearing 3+ times across different files is a candidate.

**Step 3 — Pattern matching:**
```
URLs:        https?://[^\s"']+
IPs:         \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}
Ports:       :\d{4,5}
Paths:       /[a-z_/]+\.[a-z]+
Emails:      \w+@\w+\.\w+
Numbers:     Numeric literals not in {0, 1, -1, 2, 100, 1000}
```

**Step 4 — Consistency check:**
For each constant defined somewhere (`MAX_X = 5`), search for the raw value `5` used elsewhere in the same semantic context. If found → inconsistency.

**Step 5 — LLM semantic grouping:**
The LLM can recognize that `"pending"`, `"active"`, `"suspended"`, `"deleted"` scattered across files are all the same enum and should be unified into a single `Status` enum/constants module.

### What LLMs Add

Traditional tools flag `no-magic-numbers` but create noise (flagging `range(10)` and `sleep(1)`). LLMs understand **context**:
- `timeout=30` in a retry function → should be a constant
- `range(10)` in a test → fine
- `"admin"` in an auth check → should be an enum
- `"admin"` in a test assertion → fine

---

## 5. The LLM Advantage & Limitations

### What LLMs Catch That Tools Miss

1. **Semantic dead code**: function is called but its return value is never used meaningfully
2. **Cross-module wiring bugs**: module A exports X for module B, but B imports and ignores it
3. **Business logic errors**: function named `calculate_tax` actually computes shipping
4. **Architectural violations**: one endpoint bypasses auth when all others use it
5. **Implicit contract violations**: docs say "never returns null" but a path returns null
6. **Pattern recognition across languages**: N+1 looks the same in any ORM

### What LLMs Get Wrong (Critical)

Paper: "Do Code LLMs Do Static Analysis?" (May 2025)

- LLMs **cannot reliably build ASTs, call graphs, or data-flow graphs**
- They use **pattern matching and semantic shortcuts**, not structural analysis
- They **hallucinate findings** — reporting bugs that don't exist
- Pre-training on static analysis tasks doesn't improve code intelligence

**Implication**: Never trust an LLM finding without verification. The hybrid approach (static analysis → LLM reasoning → validation) exists because each layer compensates for the others' weaknesses.

### The Validation Step

RepoAudit's validator module is the key innovation:
- Verifies data-flow facts respect control-flow order
- Checks path condition satisfiability
- Catches hallucinated findings before they reach the report

For our skill, this means: **every finding must be backed by a code reference that the LLM re-reads and confirms**.

---

## 6. Designing the Audit Report

### Structure

```
## Executive Summary
- X findings across Y files
- Breakdown by category: dead code (N), connections (N), optimization (N), magic values (N)
- Top 3 highest-impact findings

## Findings

### [CATEGORY] Finding title
- **Severity**: critical / high / medium / low
- **Confidence**: high / medium / low
- **Location**: file:line
- **Evidence**: code snippet showing the issue
- **Impact**: what happens if not fixed
- **Fix**: concrete remediation
```

### Noise Reduction

- **Confidence scoring**: only report high-confidence findings by default
- **Framework awareness**: suppress known false positives (pytest fixtures, decorators, DI)
- **Deduplication**: same magic string in 10 places = 1 finding with 10 locations
- **Context**: show enough surrounding code to evaluate without opening the editor

---

## 7. Architecture for the Audit Skill

Based on RepoAudit + Trail of Bits + HAMY's 9-agent approach:

### Option A: Sequential Deep Scan (Thorough)

```
1. Structural pass — grep/glob for entry points, imports, definitions, literals
2. Build maps — call graph, import graph, constant registry, registration points
3. Per-module LLM pass — feed each module with its maps, ask targeted questions
4. Cross-module LLM pass — check connections between modules
5. Validate — re-read flagged code, confirm each finding
6. Report — grouped by category, sorted by severity
```

### Option B: Parallel Specialist Agents (Fast)

```
Launch 4 agents in parallel:
  Agent 1: Dead code hunter (import graph + definition-use)
  Agent 2: Connection auditor (registration cross-ref)
  Agent 3: Optimization spotter (loop analysis + I/O patterns)
  Agent 4: Magic value detector (literal extraction + frequency)

Coordinator merges results, deduplicates, validates, reports.
```

### Option C: Hybrid (Recommended)

```
Phase 1 — Structural scan (no LLM, just grep/glob):
  - All function/class/method definitions
  - All imports
  - All string/number literals
  - All registration patterns (decorators, .on(), router.add(), etc.)

Phase 2 — 4 parallel specialist agents (LLM reasoning):
  Each receives the structural data + relevant source files
  Each focuses on one category
  Each validates its own findings by re-reading the code

Phase 3 — Coordinator:
  Merges, deduplicates, severity-ranks, generates report
```

---

## Key References

### Papers
- [RepoAudit](https://arxiv.org/html/2501.18160v1) — ICML 2025, autonomous LLM agent for repo-level auditing
- [IRIS](https://arxiv.org/abs/2405.17238) — ICLR 2025, neuro-symbolic LLM + CodeQL
- [LLMSA](https://arxiv.org/html/2412.14399) — Compositional neuro-symbolic static analysis
- [Do Code LLMs Do Static Analysis?](https://arxiv.org/abs/2505.12118) — May 2025, critical limitations paper

### Tools
- [Skylos](https://github.com/duriantaco/skylos) — Hybrid AST+LLM dead code detector (Python, TS, Go)
- [Knip](https://knip.dev/) — JS/TS dead code detector with 80+ framework plugins
- [Vulture](https://github.com/jendrikseipp/vulture) — Python dead code via AST
- [Piranha](https://www.uber.com/blog/piranha/) — Uber's stale feature flag cleaner
- [detect-secrets](https://github.com/Yelp/detect-secrets) — Hardcoded secrets detector

### Practical Examples
- [Trail of Bits Skills](https://github.com/trailofbits/skills) — Production security audit skills for Claude Code
- [HAMY: 9-Agent Code Review](https://hamy.xyz/blog/2026-02_code-reviews-claude-subagents) — Parallel agent architecture
- [Anthropic Security Review Action](https://github.com/anthropics/claude-code-security-review) — CI/CD integration

### Key Takeaway

> "Feed the LLM one function at a time with its interfaces. Ask specific questions.
> Use a validator. Never trust an unverified finding."
> — RepoAudit architecture principle

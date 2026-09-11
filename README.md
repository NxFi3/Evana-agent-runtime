# Evana Agent Runtime

Evana is a local, model-agnostic agent runtime for building long-running, tool-using AI agents that can work on real tasks rather than only producing text.

The project is being developed around a simple principle:

> **The LLM makes decisions; the runtime makes those decisions reliable.**

Evana is not intended to be just a prompt wrapper or a basic `LLM → tool → LLM` loop. The runtime is being designed to manage context, memory, tool execution, environment state, verification, recovery, and eventually long-running/resumable tasks.

---

## Project Goals

Evana aims to provide the infrastructure required for an autonomous agent to:

- understand a user task
- reason about what should happen next
- use tools safely
- observe the result of its actions
- distinguish execution success from actual task success
- recover from failures instead of blindly repeating actions
- maintain useful short-term and long-term memory
- manage large context windows without losing important information
- work across multiple steps and long-running sessions
- preserve enough state to resume interrupted tasks
- support different model providers without coupling the runtime to one model
- eventually support coding, browser, computer-use, and other tool-driven agents through the same runtime

The long-term target is a **general agent runtime / harness**, not a single-purpose coding assistant.

---

## Core Architecture

At a high level, Evana is organized around several cooperating layers:

```text
                         User Task
                            │
                            ▼
                     ┌─────────────┐
                     │    Agent    │
                     │  reasoning  │
                     └──────┬──────┘
                            │
                            ▼
                     ┌─────────────┐
                     │   Harness   │
                     │ / Runtime   │
                     └──────┬──────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
      Context            Memory            Tools
      Manager            System            System
          │                 │                 │
          │                 │                 ▼
          │                 │            Environment
          │                 │                 │
          └─────────────────┴─────────────────┘
                            │
                            ▼
                       Observation
                            │
                            ▼
                       Verification
                            │
                     ┌──────┴──────┐
                     │             │
                  Success       Recovery
```

The Harness is the planned control plane connecting these components. It should orchestrate existing runtime components instead of duplicating them.

---

## Current State

Evana is actively under development. Some components are functional while others are scaffolding for the planned runtime.

### Currently implemented / in active development

- structured LLM messages
- local Ollama provider
- model context-length discovery
- context window management
- token budgeting and safety margins
- trajectory construction from agent/tool events
- context compaction
- memory events and memory items
- SQLite-backed memory infrastructure
- memory retrieval
- memory consolidation pipeline
- embedding and reranking components
- tool registry / dispatch / execution infrastructure
- agent instructions
- an initial agent execution loop
- a real generated test project used to evaluate agent behavior

### Not yet complete

The following are architectural goals rather than completed functionality:

- a dedicated Harness/control-plane implementation
- explicit execution-state management
- robust process lifecycle management
- first-class observation/state representation
- reliable task-level verification
- policy-driven recovery
- checkpoint/resume for long-running tasks
- robust browser/computer-use integration
- mature evaluation and benchmark infrastructure
- parallel/subagent orchestration
- dedicated memory-maintenance orchestration

The README intentionally distinguishes the target architecture from what is already implemented.

---

## Repository Structure

```text
Evana-agent-runtime/
│
├── agentInstructions/
│   └── SystemInstructions.md
│
├── src/
│   ├── Agent/
│   │   ├── Agent.py
│   │   ├── Loop.py
│   │   └── Planner.py
│   │
│   ├── Context/
│   │   ├── ContextBuilder.py
│   │   ├── ContextManager.py
│   │   ├── ContextWindow.py
│   │   ├── Compactor.py
│   │   ├── CompactorPrompt.py
│   │   └── TokenBudget.py
│   │
│   ├── Engine/
│   │   ├── EmbeddingModel.py
│   │   ├── RerankerModel.py
│   │   └── llmManagment/
│   │       ├── LlmProvider.py
│   │       └── ollama.py
│   │
│   ├── Memory/
│   │   ├── DatabaseManager.py
│   │   ├── MemoryConsolidator.py
│   │   ├── MemoryEvent.py
│   │   ├── MemoryItem.py
│   │   ├── MemoryManager.py
│   │   ├── MemoryParser.py
│   │   ├── MemoryPrompt.py
│   │   ├── Retrieval.py
│   │   └── ShortTermMemory/
│   │
│   └── ...
│
├── test_project/
│   └── Generated project used for end-to-end agent/runtime testing
│
└── README.md
```

The repository also contains generated Python cache files in the current development history; these are ignored by `.gitignore` going forward.

---

# Agent Runtime

The Agent is responsible for deciding what should happen next based on the task, available context, memory, observations, and tool results.

The current implementation is intentionally simple and is being evolved toward a clearer separation between:

```text
Agent reasoning
      │
      ▼
Runtime / Harness
      │
      ▼
Tool execution
      │
      ▼
Observation + verification
      │
      ▼
Agent reasoning
```

This separation is important because an LLM response such as `server started` is not itself proof that the user's task succeeded.

---

# Context System

The Context subsystem manages what information is presented to the model at each step.

## ContextWindow

`ContextWindow` represents the structured model context and currently supports:

- system instructions
- task/developer instructions
- plans
- trajectory messages
- user input
- structured message roles

The runtime now passes structured messages to the LLM provider instead of flattening the entire interaction into one text prompt.

## ContextBuilder

`ContextBuilder` converts runtime information and memory events into model-facing messages.

Events are mapped approximately as follows:

| Runtime event | Model message |
|---|---|
| `user_input` | `user` |
| `agent_action` | `assistant` |
| `tool_call` | `assistant` / tool-call message |
| `tool_result` | `tool` |

This provides a foundation for proper tool-call trajectories and future provider-specific message handling.

## ContextManager

`ContextManager` coordinates context construction, trajectory handling, and compaction when the context budget becomes constrained.

## TokenBudget

`TokenBudget` tracks model token usage and available capacity using provider/runtime token accounting. A safety margin is used so the runtime does not intentionally consume the entire context window.

## Compaction

When the trajectory becomes too large, the runtime can compact older information rather than allowing context overflow.

Future work will make compaction more state-aware so that critical facts, unfinished work, tool state, and recovery information survive context transitions.

---

# Memory System

Memory is one of Evana's major subsystems. The goal is not simply to store conversation text, but to manage information across the agent's lifecycle.

The intended lifecycle is roughly:

```text
Raw events
    │
    ▼
Memory decision
    │
    ▼
Candidate memory
    │
    ▼
Deduplication / relevance
    │
    ▼
Durable memory
    │
    ├───────────────┐
    │               │
    ▼               ▼
Retrieval      Memory Maintenance
    │               │
    ▼               ├── duplicate detection
Context             ├── merge / update
                    ├── contradiction handling
                    ├── stale / low-value cleanup
                    └── index consistency
```

The distinction between **write-time consolidation** and **post-storage maintenance** is intentional. Consolidation decides what a new runtime event deserves to become durable memory; maintenance periodically revisits memories that already exist.

## Memory Events

`MemoryEvent` represents runtime events such as user input, agent actions, tool calls, and tool results.

Events are the raw history from which useful durable memories can be derived.

## Memory Items

`MemoryItem` represents durable memory rather than an individual runtime event.

The distinction is important:

```text
Event ≠ Memory

Event:   "The user asked to use PostgreSQL."
Memory:  "The project uses PostgreSQL."
```

## Memory Consolidation

`MemoryConsolidator` is responsible for deciding which information from runtime events deserves to become durable memory.

The current design uses an LLM-based decision stage with structured output, followed by runtime parsing and memory handling.

The system is intended to reduce:

- duplicate memories
- irrelevant events
- transient noise
- unnecessary database growth
- contradictory or low-value information

The memory architecture is still under active development.

## Memory Maintenance

Memory Maintenance is a **planned subsystem and is not implemented yet**.

Its purpose is different from `MemoryConsolidator`. Consolidation operates when new events are converted into candidate durable memories. Maintenance operates on the existing durable-memory store and keeps it healthy over time.

The intended responsibilities include:

- detecting memories that are duplicates or near-duplicates
- merging memories when multiple records represent the same underlying fact
- detecting conflicting or contradictory memories
- updating or superseding stale memories when newer information is available
- identifying low-value, obsolete, or rarely useful memories
- applying controlled decay/pruning policies where appropriate
- maintaining consistency between durable-memory records and retrieval indexes
- rebuilding or repairing retrieval indexes when required
- producing auditable maintenance actions rather than silently changing memory

A future maintenance cycle is expected to look approximately like:

```text
Durable Memory Store
        │
        ▼
Candidate Selection
        │
        ▼
Similarity / Metadata Analysis
        │
        ├──────────────┬───────────────┬───────────────┐
        ▼              ▼               ▼               ▼
     Duplicate     Conflict        Stale/Low       Healthy
        │              │            Value             │
        ▼              ▼               ▼              ▼
      Merge       Resolve/Update     Prune          Keep
        │              │               │              │
        └──────────────┴───────────────┴──────────────┘
                       │
                       ▼
                Index Consistency
```

This subsystem is deliberately described as a future architectural component rather than a completed feature. The current codebase already contains some of the lower-level primitives it will need, such as persistent memory metadata, item updates/deletion, embeddings, and FAISS index insertion/removal, but the maintenance policy and orchestration layer still need to be designed and implemented.

## Retrieval

`Retrieval` provides access to relevant stored memories. The current system combines embedding-based retrieval with lexical FTS/BM25 retrieval, reciprocal-rank fusion, and reranking. FAISS is persisted separately from the SQLite memory store.

Future retrieval work will focus on intent-aware retrieval and better handling of semantic/paraphrased queries rather than relying only on lexical matching.

---

# Tool System

Evana already contains a tool execution layer. The Harness should build on it rather than replace it.

The existing responsibilities include concepts such as:

- tool registration
- tool discovery
- tool dispatch
- tool execution
- standardized tool results

The important architectural boundary is:

```text
Harness
   │
   ▼
Tool Manager / Dispatcher / Registry
   │
   ▼
Concrete Tool
```

The Harness should decide **when and under what policy** a tool is executed. The tool layer should remain responsible for **how that tool is invoked**.

---

# The Harness

The Harness is the next major architectural layer of Evana.

It should not be another LLM wrapper, another tool manager, or another agent loop. Its purpose is to provide reliable execution control around the model and existing runtime components.

The intended lifecycle is:

```text
PLAN
  ↓
ACT
  ↓
OBSERVE
  ↓
VERIFY
  ↓
   ├── SUCCESS → DONE
   │
   └── FAILURE → RECOVER → ACT
```

The exact implementation is intentionally not frozen yet. The design will be based on the actual failure modes observed in end-to-end tasks.

### Responsibilities being considered

- execution state
- action lifecycle
- environment observations
- tool execution policy
- process lifecycle
- task-level verification
- failure classification
- recovery policy
- checkpoints
- resume/restart
- security and permissions
- logging and telemetry
- context/memory coordination

A key distinction is:

```text
Execution success
    ≠
Task success
```

For example:

```text
"node server.js" returned successfully
```

does not necessarily mean:

```text
The website is working correctly.
```

The Harness should eventually make that distinction explicit.

---

# Long-Running Tasks

A major goal of Evana is to support tasks that cannot reliably be completed in one model context or one execution burst.

A future long-running task may look like:

```text
Task
 │
 ├── Context window 1
 │     └── progress + artifacts + state
 │
 ├── Checkpoint
 │
 ├── Context window 2
 │     └── resume from structured state
 │
 ├── Checkpoint
 │
 └── ...
```

This requires more than conversation history. The runtime must preserve structured state such as:

- task objective
- completed work
- unfinished work
- current environment state
- important files/artifacts
- tool/process state
- relevant memories
- failures and recovery attempts
- verification status

This is a planned direction, not yet a completed subsystem.

---

# Coding Agent Direction

One of the primary target workloads for Evana is software engineering.

A coding agent should be able to:

1. inspect an existing repository
2. understand the task
3. plan changes
4. edit files
5. run commands
6. observe outputs
7. run tests/builds
8. diagnose failures
9. modify the implementation
10. re-run verification
11. stop when the task is actually complete

The generated `test_project/` is used as a practical end-to-end test case for this direction.

The point of this project is not merely to see whether an LLM can write code. It is to evaluate whether the **runtime can keep the agent on track when the environment pushes back**.

---

# Computer Use Direction

Evana is intended to remain general enough to support computer-use agents in the future.

A computer-use backend could expose capabilities such as:

```text
observe screen
click
click target
type
keypress
scroll
drag
```

However, the Harness should remain responsible for the higher-level control loop:

```text
Observe
  ↓
Choose action
  ↓
Execute
  ↓
Observe again
  ↓
Verify expected state
  ↓
Recover if necessary
```

This allows coding tools, browser tools, and computer-use tools to share the same runtime concepts without forcing every tool to implement its own agent loop.

---

# Security

Agent autonomy creates security boundaries around actions such as:

- filesystem modification
- shell execution
- network access
- process creation
- external services
- computer interaction

Evana therefore treats security as a runtime concern rather than something that should be delegated entirely to the model.

The final design is expected to support explicit policies, permissions, and auditable execution decisions.

---

# Evaluation Philosophy

Evana should eventually be evaluated at the **task level**, not only by asking whether individual LLM responses look good.

Important metrics may include:

- task success rate
- recovery success rate
- verification accuracy
- tool-call efficiency
- unnecessary action rate
- latency
- token consumption
- context-compaction quality
- memory retrieval quality
- memory write precision/recall
- memory maintenance precision/recall
- duplicate-memory rate
- contradiction resolution rate
- stale-memory/pruning accuracy
- failure rate by category
- successful completion after interruption/resume

The generated test project is an early practical evaluation environment. More formal benchmark infrastructure will be added later.

---

# Design Principles

## 1. Model decisions are not ground truth

The runtime should verify important claims against the environment.

## 2. Do not duplicate existing responsibilities

The Harness should orchestrate existing components such as the tool system, context system, and memory system rather than rebuilding them.

## 3. Prefer explicit state over hidden assumptions

The runtime should know what phase it is in and what it believes the current environment state to be.

## 4. Recover deliberately

A failure should be classified and handled according to a recovery policy instead of triggering unlimited blind retries.

## 5. Context is a resource

History should be managed, compressed, and prioritized rather than appended forever.

## 6. Memory is not history

Durable memory should contain information worth retaining, not every event that happened.

## 7. Build from real failures

Architecture decisions should be validated against actual end-to-end agent failures instead of being added only because they sound useful.

## 8. Keep the runtime model-agnostic

The runtime should not depend on the reasoning style of a single model. Local Ollama models are the current development environment, but the architecture should remain provider-independent.

---

# Development Roadmap

The roadmap is intentionally incremental.

### Phase 1 — Foundation

- [x] structured context messages
- [x] context window
- [x] token budgeting
- [x] context compaction foundation
- [x] memory event/item abstractions
- [x] memory storage foundation
- [x] memory retrieval foundation
- [x] memory consolidation foundation
- [x] tool execution infrastructure
- [x] local LLM provider

### Phase 2 — Reliable Runtime / Harness

- [ ] define runtime state model
- [ ] define action/observation contracts
- [ ] separate execution success from task success
- [ ] define task completion criteria
- [ ] implement controlled execution lifecycle
- [ ] process lifecycle management
- [ ] failure classification
- [ ] recovery policies
- [ ] checkpoint/resume foundation

### Phase 3 — Strong Agent Execution

- [ ] improve planning/execution separation
- [ ] verification loops
- [ ] structured task state
- [ ] better context-state integration
- [ ] robust interruption handling
- [ ] observability and telemetry

### Phase 4 — Advanced Agents

- [ ] browser interaction
- [ ] computer-use backend
- [ ] subagents
- [ ] parallel execution
- [ ] isolated task/worktree execution
- [ ] advanced long-running task orchestration

### Phase 5 — Research & Evaluation

- [ ] reproducible benchmark suite
- [ ] ablation studies
- [ ] memory benchmarks
- [ ] retrieval benchmarks
- [ ] memory maintenance benchmarks
- [ ] harness/recovery benchmarks
- [ ] long-horizon task evaluation

---

# Current Development Focus

The immediate priority is **not** to add every advanced agent feature.

The current priority is to understand and implement the smallest correct Harness that can reliably control the existing Evana components.

For the memory subsystem, the current foundation is already in place: events can be accumulated, the consolidation path can create durable memories, persistent metadata is stored in SQLite, embeddings are persisted, and the retrieval index can be updated. The next architectural step is to make the memory lifecycle more complete by adding a dedicated maintenance layer over already-stored memories.

Memory Maintenance will remain explicitly marked as planned until its policies, orchestration, safety checks, and tests are actually implemented.

The project should continue to evolve from real runtime failures and measurable behavior rather than from adding abstractions only because they sound useful.

# Evana Agent Runtime

> **The LLM makes decisions. The runtime makes those decisions reliable.**

Evana is an **open-source, local-first, model-agnostic runtime for building stateful, tool-using LLM agents**.

The goal is not to build another `LLM → tool → LLM` wrapper. Evana is being developed as a runtime layer for the difficult parts of real agent execution:

- context management
- memory
- tool execution
- execution state
- environment interaction
- verification
- failure handling and recovery
- long-running tasks

🚧 **Evana is actively under development.** Some components are implemented, while the Agent Loop, memory lifecycle, evaluation, and future Harness are still evolving.

---

## Why Evana?

A model can decide:

```text
"I should run the server."
```

A runtime has to deal with what happens next:

```text
Model decision
      ↓
Tool execution
      ↓
Observation
      ↓
Did it actually work?
      ↓
      ├── YES → continue
      │
      └── NO  → understand failure → recover → continue
```

The central idea is:

> **An LLM response is not ground truth about the environment.**

For example, `node server.js` exiting successfully does not necessarily mean that the application is actually working.

Evana is being designed around the boundary between **model reasoning** and **reliable runtime execution**.

---

# Current Status

### Implemented / active

- structured LLM message handling
- local Ollama provider
- model context-length discovery
- context-window management
- token budgeting and safety margins
- trajectory/event handling
- context compaction
- memory events and durable memory items
- SQLite-backed memory infrastructure
- embedding-based retrieval
- lexical retrieval
- reciprocal-rank fusion
- reranking
- memory consolidation foundation
- tool registration and execution infrastructure
- agent instructions
- initial Agent execution loop
- generated test project for end-to-end experiments

### In active development

- reliable Agent execution loop
- stronger separation between reasoning and execution
- structured execution state
- context/memory coordination
- memory lifecycle and maintenance
- task-level verification
- failure handling and recovery
- evaluation and benchmarking

### Planned

- dedicated Runtime/Harness control plane
- checkpoint/resume
- process lifecycle management
- browser/computer-use integration
- parallel/subagent orchestration
- mature task-level evaluation
- long-running autonomous tasks

The distinction between **implemented**, **in development**, and **planned** is intentional.

---

# Architecture

The long-term architecture is centered around a runtime that coordinates the model with the environment.

```text
                         User Task
                            │
                            ▼
                     ┌─────────────┐
                     │    Agent    │
                     │  Reasoning  │
                     └──────┬──────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │    Runtime /        │
                 │    Harness          │
                 └──────────┬──────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
      Context            Memory            Tools
      System             System            System
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
                  Success       Failure
                                    │
                                    ▼
                                Recovery
```

The **Runtime/Harness** shown above is the long-term architectural direction. The current codebase is being built toward this separation incrementally.

---

# Core Components

## Agent

The Agent is responsible for model-driven reasoning:

```text
Task
 ↓
Context + Memory + Tool information
 ↓
LLM
 ↓
Next action
```

The current Agent implementation is evolving, with the immediate focus on making the execution loop reliable and keeping responsibilities separated between model and runtime.

---

# Context System

The Context subsystem controls what information is presented to the model at each step.

### ContextWindow

Represents structured model context containing information such as:

- system instructions
- task/developer instructions
- plans
- user input
- trajectory messages
- tool interactions

Evana uses structured messages rather than flattening the entire interaction into one prompt.

### ContextBuilder

Converts runtime events and relevant information into model-facing messages.

| Runtime event | Model representation |
|---|---|
| `user_input` | `user` |
| `agent_action` | `assistant` |
| `tool_call` | tool-call message |
| `tool_result` | `tool` |

### ContextManager

Coordinates context construction, trajectory management, token limits, and compaction.

### TokenBudget

Tracks available context capacity and keeps a safety margin so the runtime does not intentionally consume the entire model context window.

### Compaction

When a trajectory becomes too large, Evana can compact older information instead of allowing context overflow.

Future work will make compaction increasingly state-aware so important facts, unfinished work, tool state, and recovery information survive context transitions.

---

# Memory System

Memory is one of the major architectural areas of Evana. The goal is **not** to permanently store every conversation event.

Evana separates runtime events from durable memories:

```text
Runtime Events
      │
      ▼
Memory Decision
      │
      ▼
Candidate Memory
      │
      ▼
Durable Memory
      │
      ├───────────────┐
      │               │
      ▼               ▼
 Retrieval       Maintenance
      │               │
      ▼               ▼
   Context       Memory Store
```

## Memory Events

`MemoryEvent` represents raw runtime events such as user input, agent actions, tool calls, and tool results.

## Memory Items

`MemoryItem` represents durable information worth retaining.

```text
Event ≠ Memory

Event:
"The user asked to use PostgreSQL."

Memory:
"The project uses PostgreSQL."
```

## Memory Consolidation

`MemoryConsolidator` decides whether information from runtime events should become durable memory.

The current design uses an LLM-based decision stage with structured output followed by runtime-side parsing and memory handling.

The intended purpose is to reduce:

- irrelevant events
- transient noise
- duplicate memories
- unnecessary database growth
- low-value information

The memory pipeline is still under active development.

## Memory Maintenance

Memory Maintenance is **planned and is not yet implemented as a complete subsystem**.

It is intentionally different from consolidation:

```text
Consolidation
New events → candidate durable memories

Maintenance
Existing memories → analyze → merge/update/prune/keep
```

The planned maintenance layer may eventually handle:

- duplicate detection
- merging
- contradiction detection
- stale-memory handling
- superseding old information
- low-value memory pruning
- retrieval-index consistency
- auditable memory changes

This is future work, not a completed feature.

---

# Retrieval

Evana's retrieval layer combines multiple signals rather than relying on a single search mechanism.

```text
Query
 │
 ├── Semantic Retrieval
 │
 └── Lexical Retrieval
          │
          ▼
      Rank Fusion
          │
          ▼
       Reranking
          │
          ▼
   Relevant Memories
```

The current implementation uses embedding-based retrieval together with lexical retrieval, rank fusion, and reranking.

Future work includes better handling of semantic/paraphrased queries and intent-aware retrieval.

---

# Tool System

Evana contains a tool execution layer responsible for:

- tool registration
- tool discovery
- dispatch
- execution
- standardized results

The architectural boundary is:

```text
Agent / Runtime
      │
      ▼
Tool Manager
      │
      ▼
Concrete Tool
      │
      ▼
Environment
```

The long-term runtime should decide **when and under what policy** a tool should execute. The tool layer should remain responsible for **how the tool is invoked**.

---

# Agent Execution

The current development focus is the Agent execution loop.

The intended interaction is:

```text
Task
 ↓
Build Context
 ↓
LLM Decision
 ↓
Tool / Action
 ↓
Observe Result
 ↓
Update State
 ↓
Build Next Context
 ↓
LLM Decision
 ↓
...
```

The goal is to avoid treating the LLM as the entire runtime. The runtime should be able to track what actually happened independently from what the model claimed happened.

---

# Runtime / Harness

The **Harness** is the next major architectural layer and is currently a planned direction rather than a finished subsystem.

It should not become another LLM wrapper, tool manager, prompt layer, or copy of the Agent loop. Its purpose is reliable execution control around existing runtime components.

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
 ┌─────────────┐
 │             │
SUCCESS      FAILURE
 │             │
 ▼             ▼
DONE         RECOVER
               │
               ▼
              ACT
```

Potential responsibilities include:

- execution state
- action lifecycle
- environment observations
- tool execution policy
- process lifecycle
- task verification
- failure classification
- recovery policies
- checkpoints
- resume/restart
- security and permissions
- logging and telemetry
- context/memory coordination

The exact implementation is intentionally not frozen yet.

---

# Long-Running Tasks

A major long-term goal is supporting tasks that cannot reliably be completed inside one context window or one execution burst.

```text
Task
 │
 ├── Context Window 1
 │       └── progress + artifacts + state
 │
 ├── Checkpoint
 │
 ├── Context Window 2
 │       └── resume from structured state
 │
 ├── Checkpoint
 │
 └── ...
```

The runtime eventually needs to preserve structured state such as:

- task objective
- completed work
- unfinished work
- relevant memories
- environment state
- artifacts
- tool/process state
- failures and recovery attempts
- verification status

This is a planned capability.

---

# Coding Agent Direction

Software engineering is one of the primary target workloads for Evana.

A future coding agent should be able to:

1. inspect a repository
2. understand the task
3. plan changes
4. edit files
5. execute commands
6. observe results
7. run tests
8. diagnose failures
9. modify the implementation
10. verify the result
11. stop only when the task is actually complete

The repository contains a generated `test_project/` used for practical end-to-end experiments.

The goal is not simply:

> Can the LLM generate code?

The more important question is:

> **Can the runtime keep the agent on track when the environment pushes back?**

---

# Computer-Use Direction

Evana is intended to remain general enough to support browser and computer-use agents in the future.

A future computer-use backend could expose operations such as:

```text
observe
click
type
keypress
scroll
drag
```

The runtime should still own the higher-level lifecycle:

```text
Observe
   ↓
Choose Action
   ↓
Execute
   ↓
Observe Again
   ↓
Verify
   ↓
Recover if Necessary
```

This is future work.

---

# Security

Agent autonomy introduces security boundaries around operations such as:

- filesystem modification
- shell execution
- network access
- process creation
- external services
- computer interaction

Evana treats these as **runtime concerns**, rather than assuming the model will always make safe decisions.

The long-term design is expected to include explicit permissions, execution policies, auditable actions, controlled tool access, and runtime-level safety boundaries.

---

# Evaluation

Evana is intended to be evaluated at the **task level**, rather than only by inspecting individual LLM responses.

Potential metrics include:

### Agent execution

- task success rate
- recovery success rate
- verification accuracy
- unnecessary action rate
- tool-call efficiency
- latency
- token consumption

### Context

- compaction quality
- important-state retention
- context efficiency

### Memory

- retrieval quality
- memory write precision/recall
- duplicate-memory rate
- contradiction handling
- stale-memory handling
- maintenance accuracy

### Reliability

- failure rate by category
- successful recovery after failure
- successful completion after interruption
- checkpoint/resume success rate

Formal benchmark infrastructure is still under development.

---

# Repository Structure

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
│   └── Generated project for end-to-end testing
│
└── README.md
```

---

# Design Principles

### 1. Model decisions are not ground truth

The runtime should verify important claims against the environment.

### 2. Memory is not history

Not every event deserves to become durable memory.

### 3. Context is a resource

The runtime should manage, prioritize, and compact context instead of endlessly appending history.

### 4. Separate responsibilities

The Agent reasons.

The runtime coordinates.

The tool system executes.

The environment produces observations.

The verification layer determines whether the desired state was actually reached.

### 5. Recover deliberately

Failures should be classified and handled rather than triggering unlimited blind retries.

### 6. Prefer explicit state

Important execution state should be represented explicitly rather than hidden inside prompts.

### 7. Build from real failures

Architecture should be driven by failures observed during actual end-to-end tasks.

### 8. Stay model-agnostic

Ollama is the current local development environment, but the runtime should not be coupled to a single model or provider.

---

# Roadmap

## Phase 1 — Foundation

- [x] Structured context messages
- [x] Context window management
- [x] Token budgeting
- [x] Context compaction foundation
- [x] Memory event/item abstractions
- [x] Memory storage foundation
- [x] Retrieval foundation
- [x] Memory consolidation foundation
- [x] Tool execution infrastructure
- [x] Local LLM provider

## Phase 2 — Reliable Agent Execution

- [ ] Improve Agent execution loop
- [ ] Define structured runtime state
- [ ] Define action/observation contracts
- [ ] Separate execution success from task success
- [ ] Define task completion criteria
- [ ] Improve failure handling
- [ ] Controlled recovery

## Phase 3 — Runtime / Harness

- [ ] Harness/control-plane foundation
- [ ] Process lifecycle management
- [ ] Task-level verification
- [ ] Failure classification
- [ ] Recovery policies
- [ ] Checkpoint/resume
- [ ] Runtime observability

## Phase 4 — Memory

- [ ] Complete memory lifecycle
- [ ] Improve semantic retrieval
- [ ] Intent-aware retrieval
- [ ] Memory maintenance
- [ ] Duplicate/merge handling
- [ ] Contradiction handling
- [ ] Stale-memory handling
- [ ] Retrieval-index maintenance

## Phase 5 — Advanced Agents

- [ ] Coding-agent evaluation
- [ ] Browser tools
- [ ] Computer-use integration
- [ ] Long-running tasks
- [ ] Parallel/subagent execution
- [ ] Formal benchmarks

---

# Development Philosophy

Evana is intentionally being built incrementally.

Instead of implementing every proposed subsystem immediately, the architecture is being tested against actual agent behavior.

```text
Build
 ↓
Run real task
 ↓
Observe failure
 ↓
Identify missing runtime capability
 ↓
Design solution
 ↓
Implement
 ↓
Evaluate
 ↓
Repeat
```

The goal is to avoid building a large collection of abstractions that sound useful but are not validated by real agent workloads.

---

# Contributing

Evana is currently an active development project.

Feedback is especially valuable around:

- agent execution architecture
- memory design
- retrieval
- context management
- tool/runtime boundaries
- task verification
- failure recovery
- evaluation methodology

If you find an architectural issue, unexpected behavior, or a better approach, opening an issue or discussion is welcome.

---

# Project Status

**Status:** 🚧 Active Development

Evana is not presented as a finished autonomous-agent framework.

The current goal is to build and validate a reliable foundation for stateful, tool-using agents, one subsystem at a time.

> **The objective is not to make the LLM look autonomous.**  
> **The objective is to build a runtime that can make autonomous behavior reliable.**

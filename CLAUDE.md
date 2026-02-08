# CLAUDE.md

## Project Sprint Workflow

When taking on a project with a requirements document, follow this workflow exactly. Do NOT skip stages or begin coding until the final unified plan is approved.

### Stage 1: Read Requirements

- Read the full requirements document provided by the user.
- Identify key goals, constraints, deliverables, and open questions.

### Stage 2: Research (research-before-planning agent)

- Launch the `research-before-planning` agent.
- Pass it the full requirements context: goals, constraints, technologies mentioned, and any domain-specific terms.
- The agent researches best practices, proven patterns, common pitfalls, and relevant documentation.
- Collect the agent's findings before proceeding.

### Stage 3: Architecture (sr-architect-review agent)

- Launch the `sr-architect-review` agent.
- Pass it: the original requirements AND the research findings from Stage 2.
- The agent produces architecture decisions: tech stack choices, component structure, data flow, integration patterns, and trade-offs.
- Collect the architecture plan before proceeding.

### Stage 4: Implementation Planning (Plan Mode)

- Enter Plan Mode.
- Use as input: the original requirements, research findings (Stage 2), and architecture plan (Stage 3).
- Produce a step-by-step implementation plan: file-by-file changes, ordering, dependencies, and test strategy.
- Exit Plan Mode when the implementation plan is complete.

### Stage 5: Unified Presentation

- Combine all artifacts into a single unified view:
  - **Research Summary** — key findings, best practices, and risks identified.
  - **Architecture Plan** — structural decisions, component diagram (text), data flow, and rationale.
  - **Implementation Plan** — ordered steps, files to create/modify, and test approach.
- Present this unified view to the user for approval.
- Do NOT begin any coding until the user explicitly approves.

### Handling Conflicts

- If the architecture plan and implementation plan conflict, flag the specific conflicts to the user and wait for direction.
- Do not silently reconcile disagreements — the user decides.

### Context Passing

- Each agent starts fresh. At every handoff, pass the full accumulated context (requirements + all prior stage outputs) so no information is lost.

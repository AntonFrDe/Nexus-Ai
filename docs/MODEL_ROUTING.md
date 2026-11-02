# Model routing

**Status: design only.** Nothing here is implemented. It records the intended routing policy so that
Milestones 3 to 5 keep the contracts it needs. Model names are targets, not verified identifiers.

## Principles

- Routing is a NEXUS policy, not a model feature. A profile means different things per runtime.
- Identifiers stay abstract and resolve against the models each account can really reach.
- A subscription is not an API credential. Claude and Google subscriptions go through their native
  runtimes, never through LiteLLM.
- Paid API fallback is off by default and needs explicit approval.
- Escalation relies on verifiable events. An agent's stated confidence is never evidence of success.

## Profiles

| Profile | Target | Use |
|---|---|---|
| `fast` | Local model, low effort, one pass | Extraction, classification, documentation, small edits |
| `balanced` (default) | Sonnet or local, medium to high effort, tests after changes | Development, fixes, repository analysis |
| `deep` | Opus or best available, maximum effort, independent check, approval required | Architecture, security, hard debugging |
| `review` | A different model from the author | Independent review |

## Roles

| Role | Target | Effort |
|---|---|---|
| Architect | Opus | Max |
| Planner, lead developer, bug fixing | Sonnet | High |
| Secondary developer, code analysis, unit tests | Local coding model | Normal |
| Documentary research | Gemini, if available | High |
| Independent reviewer | Gemini or Sonnet | High |
| Complex debugging | Opus | Max |
| Documentation | Local general model | Normal |
| Classification, JSON extraction, session summaries | Local general model | Low |
| Security audit | Sonnet with deterministic tools | High |

## Configuration (draft)

```yaml
routing:
  default_profile: balanced
  profiles:
    fast:
      primary: { provider: ollama, model: local-coder }
      temperature: 0.2
      max_iterations: 2
    balanced:
      primary: { runtime: claude-code, model: sonnet, effort: high }
      fallback: { provider: ollama, model: local-coder }
    deep:
      primary: { runtime: claude-code, model: opus, effort: max }
      require_approval: true
    review:
      primary: { runtime: antigravity, model: gemini, effort: high }
      fallback: { runtime: claude-code, model: sonnet }
  escalation:
    max_failed_attempts: 2
    escalate_on: [repeated_test_failure, unresolved_critical_bug]
  concurrency:
    max_heavy_local_models: 1
    max_claude_sessions: 1
    max_google_sessions: 1
  budget:
    allow_paid_api_fallback: false
    require_approval_for_paid_api: true
```

## Open problems

1. **Review independence.** Falling back from Gemini to Sonnet reviews Sonnet's own work. A fallback
   must be refused, or the result marked as not independent, when the reviewer matches the author.
2. **Silent downgrade.** `balanced` falling back to a local model changes quality, so the execution
   record must show which model really ran.
3. **Concurrency.** One Claude session cannot run frontend and backend agents in parallel. Workflow A
   either runs them in sequence or gives one to a local model.
4. **Unverifiable triggers.** `architectural_conflict` and `cross_module_refactor` are judgments,
   not events. They are left out above until a deterministic signal exists; diff scope could serve
   for the second.
5. **`fast` iterations.** One pass and `max_iterations: 2` disagree. The limit should mean retries.
6. **Subscription access.** Whether the Claude Agent SDK or a Claude Code runtime may use subscription
   authentication, and whether the student Google plan reaches Antigravity from a program, must be
   checked against current official terms and documentation before Milestone 5.

## Effect on the roadmap

| Milestone | Addition |
|---|---|
| 3 | Done in part: attempts and failures are recorded. The model used and per-resource limits come with Milestone 4 |
| 4 | Abstract model IDs resolved per account, availability checks, Ollama first, budget rules |
| 5 | `claude-code` and `antigravity` runtimes with declared capabilities, role and profile definitions, worktree isolation for writing agents |
| 5 or later | Router itself, and the Model Router node gaining profile support |
| After 5 | The six reference workflows: development, research, code audit, data processing, documentation, NEXUS maintenance |
| 7 | Personal benchmark: about 20 real tasks per model, measuring test pass rate, corrections, time, tokens, cost and review quality |

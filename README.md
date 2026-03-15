# agent-loop

Reusable control layer for local agent-driven implementation workflows.

## Layout

```text
skills/
  implementation-review-loop/
    SKILL.md                    # Skill definition (uvx --from で実行)
    pyproject.toml              # Self-contained build config
    src/agent_loop/             # Package source
      core/                     # Core logic (contracts, providers, run-loop)
      cli/                      # Click CLI commands
      assets/                   # Schemas, templates, prompts
pyproject.toml                  # Dev wrapper (tests, mypy, editable install)
tests/
docs/
  implementation-plans/
  plan-reviews/
```

## Installation

Requires Python 3.11+.

```bash
# Development (editable install from repo root)
uv pip install -e .

# Standalone via skill directory (no install needed)
uvx --from skills/implementation-review-loop agent-loop --help
```

## Bootstrap Usage

`init`, `plan new`, `plan review`, `code review`, `doctor`, `loop init`, and `loop run` already run natively in this repository.

```bash
agent-loop init --repo ../consumer-repo
agent-loop plan new --slug bootstrap --title "Bootstrap"
agent-loop plan review --plan docs/implementation-plans/<your-plan>.md
agent-loop code review --plan docs/implementation-plans/<your-plan>.md
agent-loop doctor
agent-loop loop init --plan docs/implementation-plans/<your-plan>.md
agent-loop loop run --plan docs/implementation-plans/<your-plan>.md
```

`init` defaults to `provider: codex`. To scaffold a repository that uses Claude for the default implementer/reviewer, pass `--provider claude`.

## Using With Another Repository

Install the package and pass the target repository with `--repo`.

```bash
TARGET_REPO=../consumer-repo

agent-loop init --repo "$TARGET_REPO" --mode compat-loop
agent-loop init --repo "$TARGET_REPO" --mode compat-loop --provider claude
agent-loop doctor --repo "$TARGET_REPO"
agent-loop plan new --repo "$TARGET_REPO" --slug bootstrap --title "Bootstrap"
agent-loop plan review --repo "$TARGET_REPO" --plan docs/implementation-plans/<plan-file>.md
agent-loop code review --repo "$TARGET_REPO" --plan docs/implementation-plans/<plan-file>.md
agent-loop loop init --repo "$TARGET_REPO" --plan docs/implementation-plans/<plan-file>.md
agent-loop loop run --repo "$TARGET_REPO" --plan docs/implementation-plans/<plan-file>.md
```

`init` creates the `.agent-loop/` config and plan templates in the target repository. In `compat-loop` mode it also creates `.agent-loop/checks.json`, reviewer prompts, and `.loop/runs/`. The selected `execution.provider` controls which default agent runner executes implementer and reviewer prompts.

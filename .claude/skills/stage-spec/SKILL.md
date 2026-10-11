---
name: stage-spec
description: Write a stage spec (plan/NN_<slug>.md) that satisfies AGENTS.md "Required plan before delegation", then hand it to the implementer. Main agent only. Use when starting a stage, e.g. "/stage-spec 05 groups_api".
---

# Stage spec

Arguments: `<NN> <slug>`.

## 1. Investigate (read-only)

- Read the `plan/00_index.md` row, the decisions in `plan/PLAN.md` that the stage touches, and the acceptance criteria in `docs/SPECIFICATION.md`.
- Locate every helper the stage will reuse. Record `path:line`, taken from `grep -n`, never from memory.
- Check versions and APIs of any new dependency against the installed package or the registry before naming them.
- No probe code in the repo. Version checks go in the scratchpad only.

## 2. Write `plan/NN_<slug>.md`

Frontmatter: `status: in_progress`, `completion_date: null`, `implementation_notes: ""`.

The sections are mandatory, in this order:
1. **Goal, non-goals** (and cause, for a bug).
2. **Owned files**: a table of files and actions, the existing callers with `path:line`, the helpers to reuse with `path:line`, and the allowed imports.
3. **Signatures, types, behavior**: exact signatures, defaults, check order and error messages, plus status codes for the API.
4. **Edit recipe, in order**: numbered steps, per file.
5. **Edge cases**: a table of concrete inputs and expected outputs.
6. **Tests**: each test's name, setup, action and exact assertion, plus the focused Tier 1 commands. Name tests for acceptance criterion N `test_acN_<behavior>`.
7. **Stop conditions**: what the implementer must stop and report instead of working around.

Before delegating, check against this list:
- [ ] No "TBD", "handle edge cases", "as appropriate" or choices left to the implementer.
- [ ] Every expected value was computed by hand and cross-checked.
- [ ] Every `path:line` reference was verified with `grep -n` after the last commit.
- [ ] No ready-to-apply patches; signatures, data definitions and pseudocode only.

## 3. Delegate

- Set the index row to `in_progress`.
- Spawn `Agent(subagent_type="implementer")` with a self-contained assignment:
  - the spec path;
  - the owned files;
  - the dirty main-owned files to preserve;
  - the Tier 1 checks;
  - the stop conditions;
  - "no commit, push or subagents";
  - the report format.
- Then wait for the completion notification. No polling.

---
status: accepted
completion_date: 2026-11-14
implementation_notes: "Addendum 08c-A also fixed the same stale-at-mount default in PaymentForm (To) and the checkbox layout. Accepted: redundant `seen` array in the 08c test; edits applied by scripted string replace."
---

# 08c: Bug — equal split skips members added after the group page loaded

## 1. Goal, non-goals, cause

**Symptom (main's browser E2E run, 2026-11-14).** alice creates "Trip", adds bob and carol on the group page, then adds "Dinner" 90.00 with the default equal split. The request sends `participants: [1]`; Dinner is split to alice only, so AC1 (alice +60.00, bob −30.00, carol −30.00) fails in the real UI. All 44 frontend tests were green.

**Cause.** `src/components/ExpenseForm.tsx` stores the *included* members in `checked: Set<number>`, initialised once (lazy `useState`) from `members` at mount. Members added later are not in the set, so their checkboxes render unchecked and they are left out. The stage 08 tests always mounted the form with the final member list, so they never hit this path.

**Goal.** New members are included by default. Store the *excluded* members instead: participants = active members in join order minus `excluded`.

**Non-goals.** No change to exact/percent inputs, API, or any other component.

## 2. Owned files

| File | Action |
|------|--------|
| `frontend/src/components/ExpenseForm.tsx` | modify: `checked` → `excluded` |
| `frontend/src/components/Expenses.test.tsx` | modify: add one regression test |
| `docs/evidence/08c-equal-split-regression-before.log`, `docs/evidence/08c-equal-split-regression-after.log` | create (test run output) |

## 3. Behavior

- State `excluded: Set<number>`.
  - Create mode / `resetToCreate`: `new Set()`.
  - Edit mode with `split_type === 'equal'`: ids of `members` that are **not** among `editing.shares` user ids.
  - Edit mode, other split types: `new Set()`.
- Checkbox per member: `checked={!excluded.has(id)}`; toggling adds/removes the id from a copy of `excluded`.
- Equal request: `participants` = `members` ids, in `members` order, not in `excluded`.
- Everything else unchanged.

## 4. Edit recipe, in order

1. **Test first.** In `Expenses.test.tsx` add `ac1 equal split includes members added after the page loaded`:
   - `setToken('t')`; routes: `...groupRoutes({ group: {id:1,name:'Trip',members:[ALICE],former_members:[]} })`, `'POST /api/groups/1/members'` → 201 `{id:1,name:'Trip',members:[ALICE,BOB],former_members:[]}`, `'POST /api/groups/1/expenses'` = `vi.fn<Handler>()` returning 201 with any valid `Expense`.
   - `renderApp('/groups/1')`; wait for heading `Trip`; fill `Add member by username` = `bob`, click `Add member`; wait until the Members region contains `bob`.
   - Fill `Description` `Dinner`, `Amount` `90.00`; click `Add expense`.
   - `waitFor` the POST handler called once; its JSON body equals `{description:'Dinner',amount:'90.00',payer_id:1,split:{type:'equal',participants:[1,2]}}`.
2. Run on the **unfixed** code, from `frontend/`: `npx vitest --run src/components/Expenses.test.tsx -t "added after the page loaded" > ../docs/evidence/08c-equal-split-regression-before.log 2>&1; echo $?`. Expected: exit 1, the body has `participants: [1]`. If it passes, stop and report.
3. Apply section 3 to `ExpenseForm.tsx`.
4. Same command into `08c-equal-split-regression-after.log`. Expected exit 0.
5. Tier 1: `npm run test -- --run`, `npm run lint`, `npx prettier --check src`, `npm run typecheck`.

## 5. Edge cases

| Situation | Expected participants |
|-----------|----------------------|
| mount with [alice], add bob, submit | `[1, 2]` |
| uncheck carol, submit | `[1, 2]` (existing test) |
| edit equal expense with shares 1,2 among members 1,2,3 | carol unchecked; submit → `[1, 2]` |

## 6. Stop conditions

- Step 2 passes on unfixed code.
- Any existing test needs an assertion change.
- A file outside section 2 needs editing.

## Addendum 08c-A (2026-11-14)

Main's second browser run (screenshot `docs/evidence/e2e-group-page.png`) confirms the fix and shows two leftovers.

1. **Same defect class in `PaymentForm.tsx`.** `toId` is computed once at mount (`:32`). If the page opened with only alice, `To` stays `alice` after bob is added (From = To = alice). Change `toId` state to `number | null`, initial `null`. Effective recipient: `toId ?? defaultTo(members, fromId)` — use it for the `<select value>` and the request. `setToId` keeps setting a number. After a successful record, keep the current behaviour (clear amount and error only).
   Regression test in `src/components/Payments.test.tsx`: `defaults the recipient to another member added after the page loaded` — routes `groupRoutes({ group: {id:1,name:'Trip',members:[ALICE],former_members:[]} })`, `'POST /api/groups/1/members'` → 201 with `[ALICE, BOB]`, `'POST /api/groups/1/payments'` = `vi.fn<Handler>()` → 201 any valid `Payment`. Add `bob` via the UI; wait for `bob` in the Members region; fill `Payment amount` `5.00`; click `Record payment`; body equals `{from_id:1,to_id:2,amount:'5.00'}`. No before/after logs needed.
2. **Checkbox labels stack vertically** (`label` is `flex-direction: column` in `src/index.css:55`). Add a rule `label:has(> input[type='checkbox'])` with `flex-direction: row; align-items: center; gap: 4px;`, and give `fieldset` `display: flex; flex-wrap: wrap; gap: 8px 16px; border: 1px solid #e4e7eb; border-radius: 6px;`.

Owned files for this addendum: `frontend/src/components/PaymentForm.tsx`, `frontend/src/components/Payments.test.tsx`, `frontend/src/index.css`. Then Tier 1 (four commands). Do not write logs into `docs/evidence/`.

## Acceptance receipt (2026-11-14)

Regression evidence: `docs/evidence/08c-equal-split-regression-before.log` (exit 1, `participants: [1]` vs `[1, 2]`), `…-after.log` (exit 0).

Tier 2 gate, `frontend/`, logs `.logs/08c-*.log` (after 08c-A):

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | 0 | clean |
| `npm run lint` | 0 | clean |
| `npm run test -- --run` | 0 | 9 files, 46 tests passed |
| `npm run build` | 0 | built |
| `npx prettier --check .` | 0 | clean |

Browser run (Playwright, real backend + Vite): AC1 balances `60.00 / -30.00 / -30.00`; AC2 shares `33.34, 33.33, 33.33`; settle-up `bob pays alice 63.33`, `carol pays alice 63.33`; AC7 refusal shows `126.66`; payment `To` defaults to bob; after a backend restart on the same database the balances and expenses are unchanged (AC8). Screenshot `docs/evidence/e2e-group-page.png`.

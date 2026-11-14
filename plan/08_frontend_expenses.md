---
status: in_progress
completion_date: null
implementation_notes: ""
---

# 08: Frontend — expenses, balances, settle-up, payments

> **Working-method comparison (PLAN D14).** The settle-up panel (`SettleUpPanel`, 3.6) is also built by direct prompting on `compare/08-direct`. Both versions are judged with `src/components/SettleUpPanel.test.tsx` from this spec and the checklist in `docs/AI_USAGE.md` "Working methods".

## 1. Goal, non-goals

**Goal.** On the group page (stage 07), scenarios 2–4 of `docs/SPECIFICATION.md`:
- add an expense with equal, exact or percent split; edit and delete own expenses (creator only); list all expenses, naming former members;
- show every member's balance and the suggested settle-up transfers; record a suggested transfer with one click (AC6);
- record a custom payment and list payments.
Server messages (AC3, AC4 422s) are shown verbatim through the existing `ApiError` message.

**Non-goals.** Client-side money validation (the server is the authority, AC3/AC4); pagination; charts; editing payments.

## 2. Owned files

All under `frontend/`.

| File | Action |
|------|--------|
| `src/api.ts` | modify: add ledger types and endpoint functions (3.1) |
| `src/components/BalancesPanel.tsx` | create |
| `src/components/SettleUpPanel.tsx` | create |
| `src/components/ExpenseForm.tsx` | create |
| `src/components/ExpenseList.tsx` | create |
| `src/components/PaymentForm.tsx` | create |
| `src/components/PaymentList.tsx` | create |
| `src/pages/GroupPage.tsx` | modify: queries + sections (3.8) |
| `src/test/utils.tsx` | modify: add `groupRoutes` (6) |
| `src/pages/GroupPage.test.tsx` | modify: spread `groupRoutes()` into every test's routes |
| `src/components/BalancesPanel.test.tsx`, `src/components/SettleUpPanel.test.tsx`, `src/components/Expenses.test.tsx`, `src/components/Payments.test.tsx` | create |

Reuse (stage 07): `request`, `send`, `ApiError`, `User`, `GroupDetail` in `src/api.ts`; `useAuth` in `src/auth-context.ts`; `mockFetch`, `jsonResponse`, `renderApp` in `src/test/utils.tsx`; CSS classes `.positive`, `.negative`, `table` styles in `src/index.css`.

Backend contract (prefix `/api/groups/{groupId}`):

| Call | Body | Success |
|------|------|---------|
| `GET /expenses` | — | `Expense[]` in creation order |
| `POST /expenses` | `ExpenseRequest` | 201 `Expense`; 422 `{detail: string}` or pydantic list |
| `PUT /expenses/{id}` | `ExpenseRequest` | 200 `Expense`; 403 `"only the creator can modify this expense"` |
| `DELETE /expenses/{id}` | — | 204 |
| `GET /payments` | — | `Payment[]` |
| `POST /payments` | `{from_id, to_id, amount}` | 201 `Payment`; 422 |
| `GET /balances` | — | `{members: MemberBalance[], transfers: Transfer[]}` |

## 3. Signatures, types, behavior

### 3.1 `src/api.ts` additions

```
export type SplitType = 'equal' | 'exact' | 'percent'
export interface Share { user_id: number; amount: string; percent: string | null }
export interface Expense { id: number; description: string; amount: string; payer_id: number; created_by: number; split_type: SplitType; shares: Share[] }
export type SplitRequest =
  | { type: 'equal'; participants: number[] }
  | { type: 'exact'; shares: { user_id: number; amount: string }[] }
  | { type: 'percent'; shares: { user_id: number; percent: string }[] }
export interface ExpenseRequest { description: string; amount: string; payer_id: number; split: SplitRequest }
export interface Payment { id: number; from_id: number; to_id: number; amount: string; created_by: number }
export interface PaymentRequest { from_id: number; to_id: number; amount: string }
export interface MemberBalance { user_id: number; username: string; balance: string; active: boolean }
export interface Transfer { from_id: number; from_username: string; to_id: number; to_username: string; amount: string }
export interface Balances { members: MemberBalance[]; transfers: Transfer[] }

export function listExpenses(groupId: number): Promise<Expense[]>
export function createExpense(groupId: number, body: ExpenseRequest): Promise<Expense>
export function updateExpense(groupId: number, expenseId: number, body: ExpenseRequest): Promise<Expense>
export function deleteExpense(groupId: number, expenseId: number): Promise<void>
export function listPayments(groupId: number): Promise<Payment[]>
export function recordPayment(groupId: number, body: PaymentRequest): Promise<Payment>
export function getBalances(groupId: number): Promise<Balances>
```

Query keys (used everywhere): `['expenses', groupId]`, `['payments', groupId]`, `['balances', groupId]`. After any successful expense create/update/delete or payment record, invalidate **all three**.

Name lookup: `GroupPage` builds `names: Map<number, string>` from `members` and `former_members`; unknown id → `` `user #${id}` ``. Components receive a `nameOf: (id: number) => string` prop.

### 3.2 `BalancesPanel`

`export function BalancesPanel({ balances }: { balances: Balances })`.
`<section aria-label="Balances">`, `<h3>Balances</h3>`, `<table>` with header cells `Member`, `Balance`. One row per `balances.members` entry: first cell `username`, plus `' (former)'` when `active` is false; second cell `balance`, `className` `positive` if the string does not start with `-` and is not `0.00`, `negative` if it starts with `-`, none for `0.00`.

### 3.3 `ExpenseForm`

```
export function ExpenseForm(props: {
  groupId: number
  members: User[]            // active members, join order
  currentUserId: number
  editing: Expense | null    // null = create mode
  onDone: () => void         // called after a successful save and on Cancel
})
```
State: `description`, `amount`, `payerId` (number), `splitType: SplitType`, `checked: Set<number>` (equal), `values: Record<number, string>` (exact/percent), `error: string | null`.
- Initial / reset values in create mode: empty strings, `payerId = currentUserId` if it is in `members`, else `members[0].id`; `splitType 'equal'`; all member ids checked; `values {}`.
- When `editing` changes (effect keyed on `editing?.id`): load `description`, `amount`, `payer_id`, `split_type`; equal → `checked` = share user ids; exact → `values[user_id] = share.amount`; percent → `values[user_id] = share.percent ?? ''`. When it becomes `null`, reset to create defaults.
- Markup: `<form aria-label={editing ? 'Edit expense' : 'Add expense'}>`, `<h3>` with the same text.
  - `<label>Description <input required maxLength={200} /></label>`
  - `<label>Amount <input inputMode="decimal" required placeholder="0.00" /></label>`
  - `<label>Paid by <select>` options per member (value id, text username)
  - `<label>Split <select>` options `equal` → `Equal`, `exact` → `Exact amounts`, `percent` → `Percentages`
  - `<fieldset><legend>Participants</legend>` — equal: per member `<label><input type="checkbox" /> {username}</label>`; exact: per member `<label>{username} amount <input inputMode="decimal" /></label>`; percent: per member `<label>{username} % <input inputMode="decimal" /></label>`.
  - submit `<button>` `Add expense` / `Save changes`; in edit mode also `<button type="button">Cancel</button>` → `onDone()`.
  - `<p role="alert">` when `error`.
- Build the request: `description.trim()`, `amount.trim()`, `payer_id: payerId`. Equal → `participants` = member ids in `members` order that are checked. Exact → `shares` = members in order whose `values[id].trim()` is non-empty, `{user_id, amount: trimmed}`. Percent → same with `percent`.
- Submit: `useMutation`: `editing ? updateExpense(groupId, editing.id, body) : createExpense(groupId, body)`. Success → invalidate the three keys, clear `error`, reset to create defaults, `onDone()`. Error → `error = e.message`. Submit button disabled while pending.

### 3.4 `ExpenseList`

```
export function ExpenseList(props: { groupId: number; expenses: Expense[]; currentUserId: number; nameOf: (id: number) => string; onEdit: (e: Expense) => void })
```
`<section aria-label="Expenses">`, `<h3>Expenses</h3>`. Empty → `<p>No expenses yet.</p>`. Else `<table>` header `Description`, `Amount`, `Paid by`, `Shares`, `` (empty, actions). Row: `description`; `amount`; `nameOf(payer_id)`; shares text = `shares.map(s => `${nameOf(s.user_id)} ${s.amount}` + (s.percent !== null ? ` (${s.percent}%)` : '')).join(', ')`; actions only when `created_by === currentUserId`: `<button type="button">Edit</button>` → `onEdit(expense)`, `<button type="button">Delete</button>` → mutation `deleteExpense` → invalidate the three keys; error → `<p role="alert">` under the table.

### 3.5 `PaymentForm`

```
export function PaymentForm(props: { groupId: number; members: User[]; currentUserId: number })
```
`<form aria-label="Record payment">`, `<h3>Record payment</h3>`, `<label>From <select>`, `<label>To <select>` (active members; defaults: From = current user if present else first member, To = first member whose id differs from From, or the same if only one member), `<label>Payment amount <input inputMode="decimal" required /></label>`, submit `Record payment`. Mutation `recordPayment(groupId, {from_id, to_id, amount: amount.trim()})`; success → invalidate the three keys, clear amount and error; error → `<p role="alert">`.

### 3.6 `SettleUpPanel` (D14 target)

```
export function SettleUpPanel(props: { groupId: number; transfers: Transfer[] })
```
`<section aria-label="Settle up">`, `<h3>Settle up</h3>`. Empty → `<p>Everyone is settled up.</p>`. Else `<ul>`, each `<li>` containing `<span>` with the single string `` `${from_username} pays ${to_username} ${amount}` `` and `<button type="button">Record</button>`. Click → mutation `recordPayment(groupId, {from_id, to_id, amount})`; success → invalidate the three keys; error → `<p role="alert">` below the list. All Record buttons disabled while a record is pending.

### 3.7 `PaymentList`

```
export function PaymentList(props: { payments: Payment[]; nameOf: (id: number) => string })
```
`<section aria-label="Payments">`, `<h3>Payments</h3>`. Empty → `<p>No payments yet.</p>`. Else `<ul>` of `<li>` with the single string `` `${nameOf(from_id)} paid ${nameOf(to_id)} ${amount}` ``.

### 3.8 `GroupPage` changes

- Add queries for expenses, payments and balances (keys in 3.1), each `enabled` only once the group query succeeded.
- State `editing: Expense | null` (initial `null`).
- Section order after the existing Members section: `BalancesPanel`, `SettleUpPanel`, `ExpenseForm` (inside a `<section>`), `ExpenseList` (`onEdit` sets `editing`; also `window.scrollTo?.(0, 0)` is **not** used), `PaymentForm` (inside a `<section>`), `PaymentList`. While a ledger query is pending show `<p>Loading…</p>` in place of the component that needs it; on error show `<p role="alert">{message}</p>` in its place.
- The leave button and its alert stay where stage 07 put them. Successful leave additionally removes the three ledger queries for this group.
- `currentUserId = useAuth().user` id (the page is only reachable when logged in; if `user` is null render nothing).

## 4. Edit recipe, in order

1. `src/api.ts` (3.1).
2. Components 3.2–3.7, each a named export, one per file.
3. `src/pages/GroupPage.tsx` (3.8).
4. `src/test/utils.tsx`: `groupRoutes`; update `GroupPage.test.tsx`; new test files.

## 5. Edge cases

| Input | Expected |
|-------|----------|
| equal, carol unchecked, 90.00 | body `split: {type:'equal', participants:[1,2]}` |
| exact with carol blank | carol omitted from `shares` |
| server 422 `"exact shares sum to 80.00, expected 90.00"` (any string) | alert shows it verbatim; form keeps values |
| expense created by bob, viewer alice | no Edit/Delete on that row |
| share user 4 only in `former_members` (`dave`) | shares text contains `dave 30.00` |
| share user 9 unknown | `user #9 …` |
| transfers `[]` | `Everyone is settled up.` |
| balance `0.00` | no colour class |
| member inactive with balance `30.00` | `dave (former)`, class `positive` |

## 6. Tests

### Utilities

`src/test/utils.tsx` adds:
```
export const ALICE: User = { id: 1, username: 'alice' }  // likewise BOB (2), CAROL (3)
export function groupRoutes(overrides?: Partial<{ group: GroupDetail; expenses: Expense[]; payments: Payment[]; balances: Balances }>): Record<string, Handler>
```
Returns handlers for `'GET /api/auth/me'` (ALICE), `'GET /api/groups/1'` (default `{id:1,name:'Trip',members:[ALICE,BOB,CAROL],former_members:[]}`), `'GET /api/groups/1/expenses'` (default `[]`), `'GET /api/groups/1/payments'` (default `[]`), `'GET /api/groups/1/balances'` (default `{members: the three with balance '0.00', active true, transfers: []}`). Tests call `setToken('t')` and `mockFetch({...groupRoutes(...), ...extra})`, then `renderApp('/groups/1')`.

Existing `GroupPage.test.tsx` tests: replace their per-test `me`/group routes with `groupRoutes({ group: <their body> })` spread; assertions unchanged.

Use `fireEvent` (`change`, `click`, `submit` via the button) only. Read a handler's JSON body with `JSON.parse(String(init?.body))`. Wait with `findBy*`/`waitFor`.

### `src/components/BalancesPanel.test.tsx`
- `ac1 shows balances with signs`: balances members alice `60.00`, bob `-30.00`, carol `-30.00`, transfers `[]`. Within section `Balances`: row cell `60.00` has class `positive`; first `-30.00` cell has class `negative`.
- shows former members: members add `{user_id:4, username:'dave', balance:'30.00', active:false}`; text `dave (former)`.
- zero has no colour: alice `0.00` cell has neither class.

### `src/components/SettleUpPanel.test.tsx` (shared with D14)
- `ac6 lists suggested transfers`: transfers `[{from_id:2,from_username:'bob',to_id:1,to_username:'alice',amount:'45.00'},{from_id:3,from_username:'carol',to_id:1,to_username:'alice',amount:'15.00'}]`. `findByText('bob pays alice 45.00')`, `getByText('carol pays alice 15.00')`; two `Record` buttons.
- `ac6 shows settled state`: transfers `[]` → `findByText('Everyone is settled up.')`.
- `ac6 record posts the suggested payment and refreshes balances`: same transfers; `'POST /api/groups/1/payments'` → 201 `{id:1,from_id:2,to_id:1,amount:'45.00',created_by:1}`; balances handler is a `vi.fn` returning the default first; click first `Record`; POST body equals `{from_id:2,to_id:1,amount:'45.00'}`; `waitFor` balances handler called 2 times.
- shows record error: POST → 422 `{detail:'user 2 is not a member of this group'}`; click `Record`; alert with that text.

### `src/components/Expenses.test.tsx`
- `ac1 equal split sends all members`: POST expenses handler `vi.fn` → 201 any valid `Expense`. Fill `Description` `Dinner`, `Amount` `90.00`; click `Add expense`; body equals `{description:'Dinner',amount:'90.00',payer_id:1,split:{type:'equal',participants:[1,2,3]}}`.
- equal split without an unchecked member: uncheck label `carol`; participants `[1,2]`.
- `ac3 exact split sends entered shares`: select `Split` → `exact`; `alice amount` `50.00`, `bob amount` `40.00`; Description `Dinner`, Amount `90.00`; body `split` equals `{type:'exact',shares:[{user_id:1,amount:'50.00'},{user_id:2,amount:'40.00'}]}`.
- `ac3 percent split sends entered percentages`: `percent`; `alice %` `50`, `bob %` `50`; `split` equals `{type:'percent',shares:[{user_id:1,percent:'50'},{user_id:2,percent:'50'}]}`.
- `ac3 shows the server rejection`: POST → 422 `{detail:'exact shares sum to 80.00, expected 90.00'}`; alert text equal; `Description` input still has value `Dinner`.
- `ac4 shows pydantic messages`: POST → 422 `{detail:[{msg:'Field required'}]}`; alert `Field required`.
- lists expenses with names and creator-only actions: expenses `[E1, E2]` where `E1 = {id:1,description:'Dinner',amount:'90.00',payer_id:1,created_by:1,split_type:'equal',shares:[{user_id:1,amount:'30.00',percent:null},{user_id:2,amount:'30.00',percent:null},{user_id:4,amount:'30.00',percent:null}]}`, `E2 = {id:2,description:'Taxi',amount:'12.00',payer_id:2,created_by:2,split_type:'percent',shares:[{user_id:2,amount:'6.00',percent:'50.00'},{user_id:3,amount:'6.00',percent:'50.00'}]}`; group `former_members:[{id:4,username:'dave'}]`. `findByText('Dinner')`; text `alice 30.00, bob 30.00, dave 30.00`; text `bob 6.00 (50.00%), carol 6.00 (50.00%)`; exactly one `Edit` and one `Delete` button.
- delete removes and refreshes: expenses handler `vi.fn` returns `[E1]` then `[]`; `'DELETE /api/groups/1/expenses/1'` → 204; click `Delete`; `findByText('No expenses yet.')`.
- edit loads the expense and sends PUT: expenses `[E1]` (shares users 1,2,3 instead of 4); click `Edit`; heading `Edit expense`; `Description` value `Dinner`; change `Amount` to `99.00`; click `Save changes`; `'PUT /api/groups/1/expenses/1'` body equals `{description:'Dinner',amount:'99.00',payer_id:1,split:{type:'equal',participants:[1,2,3]}}`; afterwards heading `Add expense`.

### `src/components/Payments.test.tsx`
- records a custom payment: POST payments → 201; select `From` → `2`, `To` → `1`, `Payment amount` `30.00`; click `Record payment`; body `{from_id:2,to_id:1,amount:'30.00'}`.
- lists payments: payments `[{id:1,from_id:2,to_id:1,amount:'30.00',created_by:2}]` → `findByText('bob paid alice 30.00')`; empty → `No payments yet.`
- shows payment error: POST → 422 `{detail:'payment sender and recipient must differ'}` → alert text.

### Tier 1 commands (in `frontend/`)
```
npm run test -- --run
npx eslint src
npx prettier --check src
npm run typecheck
```

## 7. Stop conditions

- A stage 07 test needs an assertion change (only its route setup may change).
- Any cast other than the existing one in `request`, `any`, or `@ts-ignore` seems needed.
- Duplicate accessible names make a query in section 6 ambiguous.
- Any backend change seems needed.

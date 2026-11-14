---
status: accepted
completion_date: 2026-11-14
implementation_notes: "One addendum (09b-A) after main reviewed screenshots: removed tabular-nums, login order, header alignment, button widths, stacked expenses on phones, leave-button indent. Accepted CSS-only deviations listed in the reports (members list selectors, hover overrides, minmax grid, clip pattern)."
---

# 09b: UI redesign (visual only)

## 1. Goal, non-goals

**Goal.** The user called the UI "trash". Make it clean and easy to use, with its own look, following the `frontend-design` skill. The behaviour stays the same.

**Brief, as main understood it.**
- **Subject:** a shared money ledger for flatmates or a trip.
- **Audience:** friends who want to know "who owes whom" fast.
- **Primary job:** see the balances at a glance, then add an expense or settle up.

**Design plan.**
- **Colour** (CSS custom properties on `:root`):

  | Token | Hex | Use |
  |-------|-----|-----|
  | `--paper` | `#F4F6F3` | page background, a cool green-grey (not cream) |
  | `--surface` | `#FFFFFF` | form panel and tables |
  | `--ink` | `#1C2B33` | text, primary buttons, header |
  | `--muted` | `#5D6B72` | secondary text, labels |
  | `--line` | `#D6DDD9` | borders, rules |
  | `--owed` | `#1E7552` | positive balances (jade) |
  | `--owes` | `#A8395A` | negative balances and errors (raspberry) |
  | `--side` | `#E7EDE9` | the balances side panel |

- **Type:** one family, **Schibsted Grotesk** (Google Fonts, weights 400/500/700). Fallback: `system-ui, sans-serif`. Every amount uses `font-variant-numeric: tabular-nums`. Scale: body 16px/1.5; h1 wordmark 1.25rem/700; page title h2 2rem/700 with letter-spacing −0.01em; section h3 1.0625rem/700. No all-caps, no monospace, no eyebrow labels.
- **Layout:**
  - Group page: on desktop (≥ 900px) a two-column grid. The main column on the left (`minmax(0, 1fr)`) holds the expense form, expenses and payments. The side column on the right (340px) is one tinted panel with balances, settle-up, record payment, members and leave group.
  - Below 900px, one column, with the side panel **first**, because balances are the first thing a user wants.
  - All content is left-aligned. Page max width 1080px; the login and groups pages are max 560px.

  ```
  SplitLedger                               Signed in as alice  [Log out]
  ───────────────────────────────────────────────────────────────────────
  Your groups
  Trip                                      3 members
  ┌ main ─────────────────────────────┐   ┌ side (tinted) ───────────────┐
  │ [Add expense form panel]          │   │ Balances                      │
  │ Expenses table                    │   │  alice  ░░░░|████▌  60.00     │
  │ Payments list                     │   │  bob    ▐███|░░░░  -30.00     │
  └───────────────────────────────────┘   │ Settle up                     │
                                          │ Record payment                │
                                          │ Members, add member           │
                                          │ Leave group                   │
                                          └───────────────────────────────┘
  ```
- **Principles:**
  - **One bold element: the balance bars.** Each member's balance is drawn as a bar from a centre zero line: jade to the right when owed, raspberry to the left when owing. Everything else stays quiet.
  - No identical card grid. Only two panels exist: the white expense form panel and the tinted side panel. The other sections are separated by space and a single top rule.
  - Secondary actions (Edit, Cancel, Record) are outlined. Destructive ones (Delete, Leave group) are raspberry text with no fill.
  - Visible keyboard focus everywhere; `prefers-reduced-motion` respected. The only motion is a 150ms bar width transition, disabled under reduced motion.

**Review against generic defaults** (main, before delegating):
- Cream with terracotta, black with acid green, and broadsheet looks are not used.
- First draft: every section was a white rounded card with a shadow (the SaaS kit). Changed to two panels only, no shadows.
- First draft: a monospace font for amounts. Changed to tabular figures of the same family.

**Non-goals.**
- No change to any visible text, `aria-label`, label text, button name, role, route or behaviour. One exception: a new back link (3.3).
- No new npm dependency. No icons, dark mode or animation library.

## 2. Owned files

All under `frontend/`.

| File | Change |
|------|--------|
| `index.html` | Google Fonts `<link rel="preconnect">` ×2 and the stylesheet `<link>` for Schibsted Grotesk 400;500;700 with `display=swap` |
| `src/index.css` | rewrite per section 4 |
| `src/App.tsx` | class names only |
| `src/pages/LoginPage.tsx`, `src/pages/GroupsPage.tsx` | class names only |
| `src/pages/GroupPage.tsx` | layout wrappers, the back link, the member count (3.3) |
| `src/components/BalancesPanel.tsx` | the bar column (3.4) |
| `src/components/ExpenseList.tsx`, `ExpenseForm.tsx`, `PaymentForm.tsx`, `PaymentList.tsx`, `SettleUpPanel.tsx` | class names and wrappers only |

Tests must **not** change. All 46 must pass unchanged. That is the proof that only visuals changed.

## 3. Markup changes

### 3.1 `App.tsx`
- `<header className="topbar">`. Wrap its contents in `<div className="topbar-inner">`, max width 1080px.
- The user `div` gets `className="session"`.
- The Log out button gets `className="button-quiet"`.

### 3.2 `LoginPage.tsx`, `GroupsPage.tsx`
- The root wrapper becomes `<div className="narrow">`.
- **LoginPage:** the `section` gets `className="panel"`. Above its `<h2>`, add `<p className="lede">Split shared costs with your group and see who owes whom.</p>`. The mode-switch button gets `className="button-link"`.
- **GroupsPage:** the group list `<ul className="group-list">`, where each `Link` fills its row. The create-group section gets `className="panel"`.

### 3.3 `GroupPage.tsx`
- The loaded view becomes:
  ```
  <div className="group-page">
    <div className="group-head">
      <Link to="/" className="back-link">Your groups</Link>
      <h2>{name}</h2>
      <p className="muted">{n} member(s)</p>
    </div>
    <div className="group-grid">
      <aside className="side">
        …Balances, Settle up, PaymentForm section, Members section,
          Former members section, add-member section, leave section…
      </aside>
      <div className="main-col">
        …ExpenseForm section (className="panel"), ExpenseList, PaymentList…
      </div>
    </div>
  </div>
  ```
- The member count is `` `${n} member${n === 1 ? '' : 's'}` `` with `n = detail.members.length`.
- Keep every section's existing `aria-label`, and keep its existing loading and error branches.
- Leave group: the button gets `className="button-danger"`, and its section gets `className="leave"`.
- The 404 branch is unchanged.
- In the DOM, `aside` comes before `main-col`. On desktop the grid puts `aside` in column 2 (`grid-column: 2; grid-row: 1`).

### 3.4 `BalancesPanel.tsx`
- Add a third column.
  - Header: `<th aria-hidden="true" className="bar-head" />`.
  - Each row: `<td aria-hidden="true" className="bar-cell">` holding `<div className="track"><div className="half left">{neg fill}</div><div className="half right">{pos fill}</div></div>`.
- **Fill:** `<span className="fill owes"|"fill owed" style={{ width: `${pct}%` }} />`, with `pct = Math.round(Math.abs(value) / maxAbs * 100)`.
  - `value = Number(member.balance)`. It is only used for drawing; money logic stays on the server.
  - `maxAbs` = the largest `Math.abs(Number(balance))` over the members. When it is 0, render no fills.
  - A negative value fills the left half; a positive value fills the right half; zero renders nothing.
- Column order: Member, Balance, bar. The existing `positive` and `negative` classes stay on the balance `<td>`.
- Wrap the table in `<div className="table-wrap">`.

### 3.5 Other components
- **`ExpenseList`:**
  - wrap the table in `<div className="table-wrap">`;
  - amount `<td>`/`<th>` gets `className="num"`;
  - the shares cell gets `className="muted small"`;
  - the actions cell gets `className="actions"`;
  - Edit gets `className="button-secondary"`, Delete gets `className="button-danger"`.
- **`ExpenseForm`:**
  - fields are wrapped in `<div className="field-row">` groups: Description, Amount and Paid by in row 1; Split and the participants fieldset in row 2; the buttons in `<div className="form-actions">`;
  - Cancel gets `className="button-secondary"`.
- **`PaymentForm`:** a `field-row` with From and To, a second `field-row` with Payment amount, then `form-actions`.
- **`SettleUpPanel`:** `<ul className="transfers">`; each `<li>` gets `className="transfer"`; Record gets `className="button-secondary"`.
- **`PaymentList`:** `<ul className="plain-list">`.

## 4. `index.css` rules

- **Base.**
  - Tokens on `:root`.
  - `*, *::before, *::after { box-sizing: border-box }`.
  - `body`: margin 0; background `--paper`; colour `--ink`; font 16px/1.5 Schibsted Grotesk.
  - `h2`, `h3`: margin 0 0 12px.
  - `a`: colour `--ink`, underline offset 3px.
- **`.topbar`:** background `--ink`; text `#fff`; `.topbar-inner` is flex, space-between, padding `14px 24px`, max-width 1080px, margin auto. The wordmark link is white with no underline. `.session` is flex with gap 12px, align center, colour `#C9D4CF`.
- **`main`:** max-width 1080px, margin `32px auto 64px`, padding `0 24px`. `.narrow`: max-width 560px.
- **`.panel`:** background `--surface`; border `1px solid --line`; radius 12px; padding 24px; margin-bottom 24px. **No shadows anywhere.**
- **Sections without `.panel`:** no border, no background; padding `20px 0`; `border-top: 1px solid --line`. The first section in a column has no top border (`:first-child`).
- **Forms:**
  - `form`: flex column, gap 16px.
  - `.field-row`: flex wrap, gap 12px; children `flex: 1 1 160px`.
  - `label`: flex column, gap 6px, font-size 0.875rem, weight 500, colour `--muted`.
  - `input, select`: font inherit; colour `--ink`; background `#fff`; border `1px solid --line`; radius 8px; padding `10px 12px`; min-height 44px.
  - `fieldset`: border `1px solid --line`, radius 8px, padding `10px 12px`, flex wrap, gap `8px 18px`, margin 0. `legend`: font-size 0.875rem, colour `--muted`, padding `0 4px`.
  - Checkbox labels: row, gap 8px, colour `--ink`, weight 400. Checkbox `accent-color: --owed`, 18px square.
  - `.form-actions`: flex, gap 8px.
- **Buttons:**
  - base `button`: font inherit, weight 600, radius 8px, padding `10px 16px`, min-height 44px, border `1px solid --ink`, background `--ink`, colour `#fff`, cursor pointer.
  - `:hover`: background `#2B3E48`.
  - `:disabled`: opacity 0.5, cursor not-allowed.
  - `.button-secondary`: background transparent, colour `--ink`, border `--line`; hover border `--ink`.
  - `.button-danger`: background transparent, colour `--owes`, border `transparent`; hover background `#F6E7EC`.
  - `.button-quiet`: transparent, white text, border `#3C4F59`.
  - `.button-link`: no border or background, colour `--ink`, underline, padding 0, min-height auto, weight 500.
  - Small buttons inside tables and transfers: padding `6px 12px`, min-height 36px.
- **Focus:** `:focus-visible { outline: 3px solid #7FB8A0; outline-offset: 2px }` on `a`, `button`, `input`, `select`.
- **Alerts:** `[role='alert']`: colour `--owes`; background `#F9EEF2`; border-left `3px solid --owes`; padding `8px 12px`; radius 6px; margin `8px 0 0`.
- **Tables:**
  - `.table-wrap`: overflow-x auto.
  - `table`: width 100%, border-collapse collapse.
  - `th`: font-size 0.8125rem, weight 500, colour `--muted`, text-align left, border-bottom `1px solid --line`, padding `8px`.
  - `td`: padding `10px 8px`, border-bottom `1px solid --line`, vertical-align middle.
  - `.num`: text-align right, tabular nums. `.actions`: text-align right, white-space nowrap; its buttons have margin-left 6px.
- **Text utilities:** `.muted`: colour `--muted`. `.small`: font-size 0.875rem. `.lede`: colour `--muted`, margin `0 0 16px`.
- **Balances:**
  - `.positive`: colour `--owed`, weight 700. `.negative`: colour `--owes`, weight 700. Both tabular nums.
  - The balance `td` (2nd column) is right-aligned.
  - `.bar-cell`: width 45%.
  - `.track`: display grid, 2 equal columns; height 10px; background `#D9E2DD`; radius 999px; overflow hidden; position relative.
  - `.track::after`: a 2px-wide `--ink` centre line at 50%, full height.
  - `.half.left`: flex, justify-content flex-end. `.half.right`: flex, justify-content flex-start.
  - `.fill`: height 100%, display block, transition `width 150ms ease-out`. `.fill.owed`: background `--owed`. `.fill.owes`: background `--owes`.
- **Group page:**
  - `.group-head`: margin-bottom 24px. `.back-link`: font-size 0.875rem, colour `--muted`.
  - `.group-head h2`: font-size 2rem, letter-spacing −0.01em, margin `4px 0 2px`.
  - `.group-grid`: display grid, gap 32px, single column.
  - `@media (min-width: 900px)`: `.group-grid { grid-template-columns: minmax(0, 1fr) 340px }`; `.side { grid-column: 2; grid-row: 1; align-self: start; position: sticky; top: 24px }`; `.main-col { grid-column: 1; grid-row: 1 }`.
  - `.side`: background `--side`, radius 12px, padding `8px 20px 20px`. Its sections use the top-rule style with a rule colour of `#CFD9D3`.
  - `.leave`: the button aligns left.
- **Lists:**
  - `.transfers`, `.plain-list`, `.group-list`, and the members lists: list-style none, padding 0, margin 0.
  - `.transfer`: flex, space-between, align center, gap 12px, padding `10px 0`, border-bottom `1px solid #CFD9D3`, tabular nums.
  - `.group-list li a`: display block; padding `14px 16px`; border `1px solid --line`; radius 10px; background `--surface`; margin-bottom 8px; no underline; weight 600; hover border `--ink`.
  - Members `ul` items: padding `4px 0`.
- **Motion:** `@media (prefers-reduced-motion: reduce) { .fill { transition: none } }`.
- **Mobile** (`max-width: 600px`): `main` padding `0 16px`; `.topbar-inner` padding `12px 16px`; `.session` font-size 0.875rem. The `Signed in as …` text stays visible.

## 5. Edge cases

| Input | Expected |
|-------|----------|
| all balances `0.00` | no fills; track and centre line still drawn |
| one member only | a bar at most 100% of a half |
| balances `60.00`, `-30.00`, `-30.00` | alice right fill 100%, bob and carol left fills 50% |
| width 375px | one column; balances panel first; tables scroll horizontally inside `.table-wrap`; no page-level horizontal scroll |

## 6. Checks

Tier 1 (in `frontend/`), each as its own call:
```
npm run test -- --run      # all 46 existing tests, unchanged
npm run lint
npx prettier --check src index.html
npm run typecheck
```

## 7. Stop conditions

- Any test fails, or seems to need a change.
- Any visible text, label, `aria-label` or button name would change (other than the back link and member count in 3.3).
- `style` needs a cast, or a CSS custom property needs a cast in TSX.
- A new npm dependency seems needed.

## Addendum 09b-A (2026-11-14, main's screenshot review)

Screenshots at 1280px and 375px showed six problems. Fix all of them; CSS changes go in `index.css`.

1. **Spaced-out amounts.** In Schibsted Grotesk, `tabular-nums` gives the period a full digit width, so `90.00` reads as `90 . 00`. Remove `font-variant-numeric: tabular-nums` everywhere. Right alignment stays.
2. **Login page order.** In `LoginPage.tsx`, move `<p className="lede">` from above the `<h2>` to directly below it. Give `.button-link` `margin-top: 4px` and `align-self: flex-start`.
3. **Header alignment.** Right-align `th:nth-child(2)` wherever `td:nth-child(2)` is right-aligned, so the Balance and Amount headers line up with their numbers.
4. **Button width.** `form > button, .form-actions { align-self: flex-start }`. No full-width buttons anywhere; the login and create-group buttons included.
5. **Expenses on phones.**
   - In `ExpenseList.tsx`, add `className="expenses-table"` to the `<table>`, and `data-label="Paid by"` to the payer `<td>`. These are markup attributes only; the visible text does not change.
   - In `@media (max-width: 600px)`:
     - `.expenses-table thead` is visually hidden (clip pattern, not `display: none`);
     - `.expenses-table tr` is `display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; padding: 12px 0; border-bottom: 1px solid var(--line)`;
     - `.expenses-table td` is `display: block; border: 0; padding: 0`;
     - the description cell is weight 600;
     - the shares cell and the actions cell are `grid-column: 1 / -1`, and the actions cell is left-aligned with `margin-top: 6px`, and its first button gets no left margin;
     - `.expenses-table td[data-label]::before { content: attr(data-label) " "; color: var(--muted) }`.
6. **Leave group indent.** `.leave .button-danger` gets `padding-left: 0; padding-right: 0`. Its hover is `background: transparent; text-decoration: underline`.

Then run the four Tier 1 commands again. All 46 tests must stay unchanged.

## Acceptance receipt (2026-11-14)

- `make check` exit 0 (`.logs/09b-make-check.log`): backend 241 passed, 100% coverage; frontend 46 tests passed **unchanged**, plus lint, typecheck and build.
- Browser review at 1280px and 375px, no horizontal page scroll (`scrollWidth` 375). Screenshots: `docs/evidence/e2e-group-page.png` (desktop) and `docs/evidence/ui-expenses-mobile.png` (expenses on a phone).

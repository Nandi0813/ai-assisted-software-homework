---
status: accepted
completion_date: 2026-11-14
implementation_notes: "Accepted: prettier reformat, eslint no-useless-assignment fix in call(), non-Error fallback String(e) in LoginPage, extra section wrappers and Loading text in GroupPage."
---

# 07: Frontend — auth, groups, members, leave

## 1. Goal, non-goals

**Goal.** A usable React UI for scenarios 1 and 5 of `docs/SPECIFICATION.md`:
- register and log in (token kept in memory with `sessionStorage` fallback, PLAN D8), log out;
- list own groups, create a group;
- open a group: see members and former members, add a member by username, leave the group. A refused leave (HTTP 409) shows the server message with the outstanding amount (AC7 UI part).
- Server error messages are shown to the user verbatim (`detail` string, or the joined pydantic messages for 422 lists).

**Non-goals.** Expenses, payments, balances, settle-up (stage 08). No global state library, no CSS framework, no i18n, no frontend coverage gate.

## 2. Owned files

All under `frontend/`.

| File | Action |
|------|--------|
| `package.json`, `package-lock.json` | modify via `npm install --save-exact react-router@8.5.1 @tanstack/react-query@5.105.0` only |
| `src/api.ts` | create: types, `ApiError`, token store, `errorMessage`, endpoint functions |
| `src/auth-context.ts` | create: `AuthState` type, `AuthContext`, `useAuth` |
| `src/AuthProvider.tsx` | create |
| `src/App.tsx` | rewrite: header + routes |
| `src/main.tsx` | modify: providers, CSS import |
| `src/index.css` | create |
| `src/pages/LoginPage.tsx` | create |
| `src/pages/GroupsPage.tsx` | create |
| `src/pages/GroupPage.tsx` | create |
| `src/test/setup.ts` | modify: reset token + storage + fetch stub after each test |
| `src/test/utils.tsx` | create: `renderApp`, `mockFetch`, `jsonResponse` |
| `src/App.test.tsx` | rewrite |
| `src/api.test.ts` | create |
| `src/pages/LoginPage.test.tsx`, `src/pages/GroupsPage.test.tsx`, `src/pages/GroupPage.test.tsx` | create |

Versions verified in the scratchpad: `react-router@8.5.1` exports `BrowserRouter`, `MemoryRouter`, `Routes`, `Route`, `Link`, `Navigate`, `useNavigate`, `useParams` (import from `'react-router'`); `@tanstack/react-query@5.105.0` exports `QueryClient`, `QueryClientProvider`, `useQuery`, `useMutation`, `useQueryClient`.

Backend contract (all under `/api`, JSON unless noted; the dev proxy in `vite.config.ts` forwards `/api`):

| Call | Request | Success |
|------|---------|---------|
| `POST /auth/register` | `{username, password}` | 201 `{id, username}`; 409 `"username already taken"`; 422 list |
| `POST /auth/login` | form-urlencoded `username`, `password` | 200 `{access_token, token_type}`; 401 `"incorrect username or password"` |
| `GET /auth/me` | bearer | 200 `{id, username}`; 401 |
| `GET /groups` | bearer | 200 `[{id, name}]` |
| `POST /groups` | `{name}` | 201 `GroupDetail` |
| `GET /groups/{id}` | bearer | 200 `GroupDetail`; 404 `"group not found"` |
| `POST /groups/{id}/members` | `{username}` | 201 `GroupDetail`; 404 `"user not found"`; 409 `"user is already a member"` |
| `POST /groups/{id}/leave` | bearer | 204; 409 `"cannot leave the group with an outstanding balance of -30.00"` |

`GroupDetail = {id, name, members: User[], former_members: User[]}` (stage 06b).

## 3. Signatures, types, behavior

### 3.1 `src/api.ts`

```
export interface User { id: number; username: string }
export interface GroupSummary { id: number; name: string }
export interface GroupDetail { id: number; name: string; members: User[]; former_members: User[] }

export class ApiError extends Error { readonly status: number; constructor(status: number, message: string) }
  // set this.name = 'ApiError'

export function getToken(): string | null
export function setToken(value: string | null): void
export function errorMessage(body: unknown, status: number): string
export async function request<T>(path: string, options?: RequestOptions): Promise<T>
export async function send(path: string, options?: RequestOptions): Promise<void>

interface RequestOptions { method?: string; json?: unknown; form?: URLSearchParams }

export function register(username: string, password: string): Promise<User>
export function login(username: string, password: string): Promise<void>
export function me(): Promise<User>
export function listGroups(): Promise<GroupSummary[]>
export function getGroup(groupId: number): Promise<GroupDetail>
export function createGroup(name: string): Promise<GroupDetail>
export function addMember(groupId: number, username: string): Promise<GroupDetail>
export function leaveGroup(groupId: number): Promise<void>
```

Token store: key `'splitledger.token'`. A module-level `let token` initialised from `sessionStorage.getItem(key)`. `setToken` updates the variable and `sessionStorage` (`setItem` or `removeItem`). Every `sessionStorage` access is inside `try/catch` that ignores the error (storage may be unavailable).

`errorMessage(body, status)`:
1. `body` is an object with `detail` of type string → that string.
2. `detail` is an array → each element that is an object with a string `msg` contributes `msg`; join with `'; '`. If none qualify, fall through.
3. Otherwise → `` `Request failed (${status})` ``.
Narrow with `typeof`/`Array.isArray`/`in` checks only; no `as any`.

Shared fetch (private `call(path, options): Promise<Response>`):
- URL `` `/api${path}` ``, method `options.method ?? 'GET'`.
- Headers: `Authorization: Bearer <token>` when a token exists. With `json`: `Content-Type: application/json` and `body: JSON.stringify(json)`. With `form`: `body: form` (browser sets the content type).
- `!response.ok`: read the body with `response.json()` inside `try/catch` (fallback `null`); if status is 401, `setToken(null)`; throw `new ApiError(status, errorMessage(body, status))`.
- `request<T>` returns `(await response.json()) as T` — the single allowed cast, comment `// trusted: shape fixed by backend schemas`. `send` ignores the body.

`login`: `request<{ access_token: string }>('/auth/login', { method: 'POST', form: URLSearchParams{username, password} })`, then `setToken(access_token)`.

### 3.2 `src/auth-context.ts`

```
export interface AuthState {
  user: User | null
  loading: boolean
  login(username: string, password: string): Promise<void>
  register(username: string, password: string): Promise<void>
  logout(): void
}
export const AuthContext = createContext<AuthState | null>(null)
export function useAuth(): AuthState   // throws Error('useAuth must be used inside AuthProvider') when null
```

### 3.3 `src/AuthProvider.tsx`

`export function AuthProvider({ children }: { children: ReactNode })`.
- State `user: User | null` (initial `null`), `loading: boolean` (initial `getToken() !== null`).
- Effect on mount: if a token exists, `me()` → `setUser`; on error `setToken(null)`; finally `setLoading(false)`. Ignore results after unmount (cancelled flag).
- `login(u, p)`: `await api.login(u, p)`; `setUser(await me())`.
- `register(u, p)`: `await api.register(u, p)`; then `login(u, p)`.
- `logout()`: `setToken(null)`; `setUser(null)`; `queryClient.clear()` via `useQueryClient()`.
- Value memoised with `useMemo`.

### 3.4 `src/App.tsx`

`export default function App()`:
- `<header>`: `<h1>` with text `SplitLedger` wrapped in `<Link to="/">`. When a user is logged in: text `Signed in as {username}` and a `<button>` `Log out`.
- `<main>`: `loading` → `<p>Loading…</p>`. No user → `<LoginPage />` (any URL). User → `<Routes>`: `/` → `GroupsPage`; `/groups/:groupId` → `GroupPage`; `*` → `<Navigate to="/" replace />`.

### 3.5 `src/main.tsx`

Import `./index.css`. One `new QueryClient()` at module level. Tree: `StrictMode` > `QueryClientProvider` > `BrowserRouter` > `AuthProvider` > `App`.

### 3.6 `src/pages/LoginPage.tsx`

- State `mode: 'login' | 'register'`, `username`, `password`, `error: string | null`, `busy: boolean`.
- `<h2>`: `Log in` or `Create account`.
- `<form>` with `<label>Username <input autoComplete="username" required /></label>` and `<label>Password <input type="password" required autoComplete="current-password"|"new-password" /></label>`, submit button text `Log in` or `Create account` (disabled while busy).
- Submit: `preventDefault`; clear error; `busy`; call `auth.login` or `auth.register`; on `ApiError` (or any `Error`) set `error = e.message`; finally `busy = false`.
- Error: `<p role="alert">{error}</p>` when set.
- Switch button (`type="button"`): `Need an account? Register` / `Have an account? Log in`; switching clears the error.
- In register mode a hint `<p>` below the form: `3–32 letters, digits or _; password at least 8 characters.`

### 3.7 `src/pages/GroupsPage.tsx`

- `useQuery({ queryKey: ['groups'], queryFn: listGroups })`.
- `<h2>Your groups</h2>`. Pending → `Loading…`. Error → `<p role="alert">` with message. Empty → `<p>No groups yet.</p>`. Else `<ul>` of `<li><Link to={`/groups/${id}`}>{name}</Link></li>`.
- Create form: `<label>New group name <input required maxLength={64} /></label>` + `<button type="submit">Create group</button>`. `useMutation(createGroup)`: on success invalidate `['groups']`, clear the input, `navigate(`/groups/${group.id}`)`. Error → `<p role="alert">`.

### 3.8 `src/pages/GroupPage.tsx`

- `groupId = Number(useParams().groupId)`. `useQuery({ queryKey: ['group', groupId], queryFn: () => getGroup(groupId) })`.
- Error with `ApiError` status 404 → `<p role="alert">Group not found.</p>` and `<Link to="/">Back to groups</Link>`. Other errors → message in an alert.
- Loaded: `<h2>{name}</h2>`; `<section aria-label="Members">` with `<h3>Members</h3>` and `<ul>` of usernames. If `former_members.length > 0`: `<h3>Former members</h3>` and `<ul>` of usernames.
- Add member form: `<label>Add member by username <input required /></label>` + `<button type="submit">Add member</button>`. Mutation `addMember(groupId, username)`: on success `queryClient.setQueryData(['group', groupId], detail)`, clear input; error → `<p role="alert">`.
- `<button type="button">Leave group</button>`. Mutation `leaveGroup(groupId)`: on success `queryClient.removeQueries({ queryKey: ['group', groupId] })`, invalidate `['groups']`, `navigate('/')`. On error show `<p role="alert">{message}</p>` next to the button (AC7: shows the outstanding amount).
- Export the component as `default`? No: named exports for all pages (`export function GroupPage()`), same for `LoginPage`, `GroupsPage`.

### 3.9 `src/index.css`

Plain, readable layout: system font stack; `body` margin 0, background `#f6f7f9`, colour `#1f2933`; `header` flex row, space-between, padding `12px 24px`, white background, bottom border `#e4e7eb`; `main` `max-width: 720px`, `margin: 24px auto`, `padding: 0 16px`; `section` white card, border `1px solid #e4e7eb`, radius `8px`, padding `16px`, margin-bottom `16px`; `form` flex wrap with gap `8px`, align end; `label` flex column, font-size `0.9rem`; `input, select, button` font inherit, padding `6px 10px`; `button` background `#2563eb`, white text, no border, radius `6px`, cursor pointer; `button:disabled` opacity `0.6`; `[role="alert"]` colour `#b91c1c`; `.positive` colour `#15803d`; `.negative` colour `#b91c1c`; `table` width 100%, collapse; `th, td` left aligned, padding `4px 8px`, bottom border `#e4e7eb`. Header `h1` font-size `1.25rem`, margin 0, link inherits colour without underline.

## 4. Edit recipe, in order

1. In `frontend/`: `npm install --save-exact react-router@8.5.1 @tanstack/react-query@5.105.0`.
2. `src/api.ts` (3.1). 3. `src/auth-context.ts` (3.2). 4. `src/AuthProvider.tsx` (3.3).
5. Pages (3.6–3.8). 6. `src/App.tsx` (3.4). 7. `src/index.css` (3.9), `src/main.tsx` (3.5).
8. Test utilities and tests (section 6).

## 5. Edge cases

| Input | Expected UI |
|-------|-------------|
| login → 401 `{"detail":"incorrect username or password"}` | alert `incorrect username or password`; still on login form |
| register → 422 `{"detail":[{"msg":"Value error, username must be 3-32 characters of letters, digits or underscore"}]}` | alert with exactly that `msg` |
| register → 409 `{"detail":"username already taken"}` | alert `username already taken` |
| stored token, `/auth/me` → 401 | token cleared, login form shown |
| `GET /groups` → `[]` | `No groups yet.` |
| `GET /groups/7` → 404 | `Group not found.` + `Back to groups` link |
| leave → 409 with outstanding balance detail | alert `cannot leave the group with an outstanding balance of -30.00`; still on group page |
| leave → 204 | navigates to `/`, shows `Your groups` |
| add member → 404 `user not found` | alert `user not found` |
| `errorMessage(null, 500)` | `Request failed (500)` |
| `errorMessage({detail: [{msg:'a'},{msg:'b'}]}, 422)` | `a; b` |
| `errorMessage({detail: [{loc: []}]}, 422)` | `Request failed (422)` |

## 6. Tests

### Utilities

`src/test/setup.ts` (keep existing lines) adds `afterEach`: `setToken(null)`, `sessionStorage.clear()`, `vi.unstubAllGlobals()`.

`src/test/utils.tsx`:
```
export type Handler = (init: RequestInit | undefined) => Response
export function jsonResponse(status: number, body?: unknown): Response
  // body undefined → new Response(null, {status}); else JSON body with content-type application/json
export function mockFetch(routes: Record<string, Handler>): Mock
  // vi.fn((input: RequestInfo | URL, init?: RequestInit) => ...) stubbed as global 'fetch'.
  // key = `${init?.method ?? 'GET'} ${String(input)}`, e.g. 'GET /api/groups'.
  // Unknown key → throw new Error(`unexpected fetch ${key}`). Returns Promise.resolve(handler(init)).
export function renderApp(path: string): RenderResult
  // new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // QueryClientProvider > MemoryRouter initialEntries={[path]} > AuthProvider > App
```
`Mock` imported as a type from `vitest`. `jsonResponse(204)` must not pass a body.

Logged-in setup used below (`loggedIn()` helper inside each test file that needs it, typed `(): void`): `setToken('t')`, and include route `'GET /api/auth/me': () => jsonResponse(200, { id: 1, username: 'alice' })`.

### `src/api.test.ts`
- `errorMessage` returns the string detail: `({detail:'boom'}, 400)` → `'boom'`.
- joins pydantic messages: `({detail:[{msg:'a'},{msg:'b'}]}, 422)` → `'a; b'`.
- falls back: `(null, 500)` → `'Request failed (500)'`; `({detail:[{loc:[]}]}, 422)` → `'Request failed (422)'`.
- `request` sends the bearer token: `setToken('abc')`; mockFetch `'GET /api/groups'` → 200 `[]`; await `listGroups()`; assert the handler's `init.headers` has `Authorization: 'Bearer abc'` (read via `new Headers(init?.headers).get('Authorization')`).
- 401 clears the token: `setToken('abc')`; `'GET /api/auth/me'` → 401 `{detail:'not authenticated'}`; `me()` rejects with `ApiError` whose `status` is 401 and message `'not authenticated'`; `getToken()` is `null`.
- `login` posts a form and stores the token: `'POST /api/auth/login'` → 200 `{access_token:'tok', token_type:'bearer'}`; `await login('alice','pw123456')`; handler `init.body` is a `URLSearchParams` with `username=alice`; `getToken()` is `'tok'`; `sessionStorage.getItem('splitledger.token')` is `'tok'`.

### `src/App.test.tsx`
- shows the login form when signed out: `mockFetch({})`; `renderApp('/')`; heading level 1 `SplitLedger`; heading `Log in`; button `Log in`.
- shows groups when a token is stored: `loggedIn()`, `'GET /api/groups'` → `[]`; `findByText('Signed in as alice')`; `findByRole('heading', {name: 'Your groups'})`.
- log out returns to the login form: same as above, then click `Log out`; heading `Log in` visible; `getToken()` null.
- invalid stored token shows the login form: `setToken('bad')`; `'GET /api/auth/me'` → 401; `findByRole('heading', {name:'Log in'})`; `getToken()` null.

### `src/pages/LoginPage.test.tsx` (use `@testing-library/user-event`? No — use `fireEvent` from `@testing-library/react` only; no new dependency)
- logs in: routes login → 200 token, me → alice, `GET /api/groups` → `[]`. Fill `Username` `alice`, `Password` `pw123456`, click `Log in`; `findByText('Signed in as alice')`.
- shows the login error: login → 401 `{detail:'incorrect username or password'}`; submit; `findByRole('alert')` has text `incorrect username or password`.
- registers then logs in: click `Need an account? Register`; heading `Create account`; routes register → 201 `{id:1, username:'alice'}`, login, me, groups as above; submit `Create account`; `findByText('Signed in as alice')`; the register handler was called once.
- shows the validation message on 422: register → 422 `{detail:[{msg:'Value error, username must be 3-32 characters of letters, digits or underscore'}]}`; alert with that exact text.

### `src/pages/GroupsPage.test.tsx`
- lists groups as links: `loggedIn()`; groups → `[{id:1,name:'Trip'},{id:2,name:'Flat'}]`; `renderApp('/')`; links `Trip` (href `/groups/1`) and `Flat` (href `/groups/2`).
- shows the empty state: groups → `[]`; `findByText('No groups yet.')`.
- creates a group and opens it: groups → `[]`; `'POST /api/groups'` → 201 `{id:3,name:'Ski',members:[{id:1,username:'alice'}],former_members:[]}`; `'GET /api/groups/3'` → 200 same body. Fill `New group name` `Ski`, click `Create group`; `findByRole('heading', {name:'Ski'})`; POST handler body JSON equals `{name:'Ski'}`.

### `src/pages/GroupPage.test.tsx`
Group body `G = {id:1,name:'Trip',members:[{id:1,username:'alice'},{id:2,username:'bob'}],former_members:[]}`.
- shows members: `GET /api/groups/1` → G; `renderApp('/groups/1')`; heading `Trip`; text `alice`, `bob`; no text `Former members`.
- shows former members: G with `former_members:[{id:3,username:'carol'}]`; texts `Former members`, `carol`.
- shows not found: `GET /api/groups/1` → 404 `{detail:'group not found'}`; `findByText('Group not found.')`; link `Back to groups`.
- adds a member: `POST /api/groups/1/members` → 201 G with an extra member `{id:3,username:'carol'}`; fill `Add member by username` `carol`, click `Add member`; `findByText('carol')`; handler body JSON `{username:'carol'}`.
- shows add-member error: POST members → 404 `{detail:'user not found'}`; alert `user not found`.
- `ac7 shows the outstanding amount when leaving is refused`: `POST /api/groups/1/leave` → 409 `{detail:'cannot leave the group with an outstanding balance of -30.00'}`; click `Leave group`; alert text `cannot leave the group with an outstanding balance of -30.00`; heading `Trip` still shown.
- leaving returns to the group list: leave → 204; `GET /api/groups` → `[]`; click `Leave group`; `findByRole('heading', {name:'Your groups'})`.

Query elements by role/label/text only (`getByLabelText('Username')` etc.). Use `findBy*` for anything after a fetch.

### Tier 1 commands (in `frontend/`)
```
npm run test -- --run
npx eslint src
npx prettier --check src package.json
npm run typecheck
```
(The whole `src` is small and fully owned by this stage, so the full frontend test run is the focused run.)

## 7. Stop conditions

- An export listed in section 2 is missing from the pinned packages, or `npm install` changes any other dependency's major version.
- TypeScript needs `any`, `@ts-ignore`, or a cast other than the one in 3.1.
- A test can only pass by changing a text, label or route defined above.
- Any backend file needs a change.

## Acceptance receipt (2026-11-14)

Tier 2 gate, `frontend/`, logs in `.logs/07-*.log`:

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | 0 | clean |
| `npm run lint` | 0 | clean |
| `npm run test -- --run` | 0 | 5 files, 24 tests passed |
| `npm run build` | 0 | built, 300.17 kB JS (93.87 kB gzip) |
| `npx prettier --check .` | 0 | all files formatted |

`npm audit --omit=dev`: 0 vulnerabilities (the 11 reported at install are dev-only).
Review: diff matches sections 3–6; only cast is the allowed `as T` in `request`.

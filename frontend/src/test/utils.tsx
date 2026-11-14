import { render, type RenderResult } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { vi, type Mock } from 'vitest'
import App from '../App'
import { AuthProvider } from '../AuthProvider'
import type { Balances, Expense, GroupDetail, Payment, User } from '../api'

export type Handler = (init: RequestInit | undefined) => Response

export const ALICE: User = { id: 1, username: 'alice' }
export const BOB: User = { id: 2, username: 'bob' }
export const CAROL: User = { id: 3, username: 'carol' }

interface GroupRoutesOverrides {
  group: GroupDetail
  expenses: Expense[]
  payments: Payment[]
  balances: Balances
}

export function groupRoutes(
  overrides: Partial<GroupRoutesOverrides> = {},
): Record<string, Handler> {
  const group: GroupDetail = overrides.group ?? {
    id: 1,
    name: 'Trip',
    members: [ALICE, BOB, CAROL],
    former_members: [],
  }
  const expenses: Expense[] = overrides.expenses ?? []
  const payments: Payment[] = overrides.payments ?? []
  const balances: Balances = overrides.balances ?? {
    members: [ALICE, BOB, CAROL].map((u) => ({
      user_id: u.id,
      username: u.username,
      balance: '0.00',
      active: true,
    })),
    transfers: [],
  }
  return {
    'GET /api/auth/me': () => jsonResponse(200, ALICE),
    'GET /api/groups/1': () => jsonResponse(200, group),
    'GET /api/groups/1/expenses': () => jsonResponse(200, expenses),
    'GET /api/groups/1/payments': () => jsonResponse(200, payments),
    'GET /api/groups/1/balances': () => jsonResponse(200, balances),
  }
}

export function jsonResponse(status: number, body?: unknown): Response {
  if (body === undefined) {
    return new Response(null, { status })
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function mockFetch(routes: Record<string, Handler>): Mock {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const handler = routes[key]
    if (handler === undefined) {
      throw new Error(`unexpected fetch ${key}`)
    }
    return Promise.resolve(handler(init))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderApp(path: string): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

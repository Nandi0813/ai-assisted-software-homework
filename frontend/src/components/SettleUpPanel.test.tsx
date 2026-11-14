import { describe, it, expect } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type Balances, type Transfer } from '../api'
import { jsonResponse, mockFetch } from '../test/utils'
import { SettleUpPanel } from './SettleUpPanel'

function renderPanel(): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <SettleUpPanel groupId={1} />
    </QueryClientProvider>,
  )
}

const BOB_TO_ALICE: Transfer = {
  from_id: 2,
  from_username: 'bob',
  to_id: 1,
  to_username: 'alice',
  amount: '30.00',
}
const CAROL_TO_ALICE: Transfer = {
  from_id: 3,
  from_username: 'carol',
  to_id: 1,
  to_username: 'alice',
  amount: '15.50',
}

describe('SettleUpPanel', () => {
  it('shows everyone settled when there are no transfers', async () => {
    mockFetch({
      'GET /api/groups/1/balances': () =>
        jsonResponse(200, { members: [], transfers: [] }),
    })
    renderPanel()
    expect(
      await screen.findByText('Everyone is settled up.'),
    ).toBeInTheDocument()
  })

  it('records each suggested transfer until everyone is settled', async () => {
    // fake ledger: recording a transfer removes it, as the backend recomputes
    let transfers = [BOB_TO_ALICE, CAROL_TO_ALICE]
    const posted: unknown[] = []
    mockFetch({
      'GET /api/groups/1/balances': () =>
        jsonResponse(200, { members: [], transfers } satisfies Balances),
      'POST /api/groups/1/payments': (init) => {
        const body = JSON.parse(String(init?.body)) as Transfer
        posted.push(body)
        transfers = transfers.filter((t) => t.from_id !== body.from_id)
        return jsonResponse(201, { id: posted.length, ...body, created_by: 1 })
      },
    })
    renderPanel()
    expect(await screen.findByText(/bob pays alice 30\.00/)).toBeInTheDocument()
    expect(screen.getByText(/carol pays alice 15\.50/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Record bob → alice' }))
    expect(await screen.findByText(/carol pays alice/)).toBeInTheDocument()
    expect(screen.queryByText(/bob pays alice/)).not.toBeInTheDocument()

    fireEvent.click(
      screen.getByRole('button', { name: 'Record carol → alice' }),
    )
    expect(
      await screen.findByText('Everyone is settled up.'),
    ).toBeInTheDocument()
    expect(posted).toEqual([
      { from_id: 2, to_id: 1, amount: '30.00' },
      { from_id: 3, to_id: 1, amount: '15.50' },
    ])
  })

  it('shows an error when recording fails', async () => {
    mockFetch({
      'GET /api/groups/1/balances': () =>
        jsonResponse(200, { members: [], transfers: [BOB_TO_ALICE] }),
      'POST /api/groups/1/payments': () =>
        jsonResponse(422, { detail: 'invalid payment' }),
    })
    renderPanel()
    fireEvent.click(
      await screen.findByRole('button', { name: 'Record bob → alice' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'invalid payment',
    )
  })

  it('shows an error when balances fail to load', async () => {
    mockFetch({
      'GET /api/groups/1/balances': () => jsonResponse(500, { detail: 'boom' }),
    })
    renderPanel()
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })
})

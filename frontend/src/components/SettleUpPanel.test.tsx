import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { setToken, type Transfer } from '../api'
import { groupRoutes, jsonResponse, mockFetch, renderApp } from '../test/utils'

function loggedIn(): void {
  setToken('t')
}

const TRANSFERS: Transfer[] = [
  {
    from_id: 2,
    from_username: 'bob',
    to_id: 1,
    to_username: 'alice',
    amount: '45.00',
  },
  {
    from_id: 3,
    from_username: 'carol',
    to_id: 1,
    to_username: 'alice',
    amount: '15.00',
  },
]

describe('SettleUpPanel', () => {
  it('ac6 lists suggested transfers', async () => {
    loggedIn()
    mockFetch(groupRoutes({ balances: { members: [], transfers: TRANSFERS } }))
    renderApp('/groups/1')
    expect(await screen.findByText('bob pays alice 45.00')).toBeInTheDocument()
    expect(screen.getByText('carol pays alice 15.00')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Record' })).toHaveLength(2)
  })

  it('ac6 shows settled state', async () => {
    loggedIn()
    mockFetch(groupRoutes({ balances: { members: [], transfers: [] } }))
    renderApp('/groups/1')
    expect(
      await screen.findByText('Everyone is settled up.'),
    ).toBeInTheDocument()
  })

  it('ac6 record posts the suggested payment and refreshes balances', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    const balances = vi.fn(() =>
      jsonResponse(200, { members: [], transfers: TRANSFERS }),
    )
    mockFetch({
      ...groupRoutes(),
      'GET /api/groups/1/balances': balances,
      'POST /api/groups/1/payments': (init) => {
        seen.push(init)
        return jsonResponse(201, {
          id: 1,
          from_id: 2,
          to_id: 1,
          amount: '45.00',
          created_by: 1,
        })
      },
    })
    renderApp('/groups/1')
    await screen.findByText('bob pays alice 45.00')
    const [first] = screen.getAllByRole('button', { name: 'Record' })
    if (first === undefined) throw new Error('no Record button')
    fireEvent.click(first)
    await waitFor(() => expect(balances).toHaveBeenCalledTimes(2))
    expect(JSON.parse(String(seen[0]?.body))).toEqual({
      from_id: 2,
      to_id: 1,
      amount: '45.00',
    })
  })

  it('shows record error', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes({ balances: { members: [], transfers: TRANSFERS } }),
      'POST /api/groups/1/payments': () =>
        jsonResponse(422, { detail: 'user 2 is not a member of this group' }),
    })
    renderApp('/groups/1')
    await screen.findByText('bob pays alice 45.00')
    const [first] = screen.getAllByRole('button', { name: 'Record' })
    if (first === undefined) throw new Error('no Record button')
    fireEvent.click(first)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'user 2 is not a member of this group',
    )
  })
})

import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import { setToken } from '../api'
import { groupRoutes, mockFetch, renderApp } from '../test/utils'

function loggedIn(): void {
  setToken('t')
}

describe('BalancesPanel', () => {
  it('ac1 shows balances with signs', async () => {
    loggedIn()
    mockFetch(
      groupRoutes({
        balances: {
          members: [
            { user_id: 1, username: 'alice', balance: '60.00', active: true },
            { user_id: 2, username: 'bob', balance: '-30.00', active: true },
            { user_id: 3, username: 'carol', balance: '-30.00', active: true },
          ],
          transfers: [],
        },
      }),
    )
    renderApp('/groups/1')
    const section = await screen.findByRole('region', { name: 'Balances' })
    expect(within(section).getByText('60.00')).toHaveClass('positive')
    expect(within(section).getAllByText('-30.00')[0]).toHaveClass('negative')
  })

  it('shows former members', async () => {
    loggedIn()
    mockFetch(
      groupRoutes({
        balances: {
          members: [
            { user_id: 1, username: 'alice', balance: '0.00', active: true },
            { user_id: 4, username: 'dave', balance: '30.00', active: false },
          ],
          transfers: [],
        },
      }),
    )
    renderApp('/groups/1')
    expect(await screen.findByText('dave (former)')).toBeInTheDocument()
  })

  it('zero has no colour', async () => {
    loggedIn()
    mockFetch(
      groupRoutes({
        balances: {
          members: [
            { user_id: 1, username: 'alice', balance: '0.00', active: true },
            { user_id: 2, username: 'bob', balance: '-30.00', active: true },
            { user_id: 3, username: 'carol', balance: '30.00', active: true },
          ],
          transfers: [],
        },
      }),
    )
    renderApp('/groups/1')
    const section = await screen.findByRole('region', { name: 'Balances' })
    const zero = within(section).getByText('0.00')
    expect(zero).not.toHaveClass('positive')
    expect(zero).not.toHaveClass('negative')
  })
})

import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent, waitFor, within } from '@testing-library/react'
import { setToken } from '../api'
import {
  ALICE,
  BOB,
  groupRoutes,
  jsonResponse,
  mockFetch,
  renderApp,
  type Handler,
} from '../test/utils'

function loggedIn(): void {
  setToken('t')
}

describe('Payments', () => {
  it('records a custom payment', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/payments': (init) => {
        seen.push(init)
        return jsonResponse(201, {
          id: 1,
          from_id: 2,
          to_id: 1,
          amount: '30.00',
          created_by: 2,
        })
      },
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('From'), {
      target: { value: '2' },
    })
    fireEvent.change(screen.getByLabelText('To'), {
      target: { value: '1' },
    })
    fireEvent.change(screen.getByLabelText('Payment amount'), {
      target: { value: '30.00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    await waitFor(() => expect(seen).toHaveLength(1))
    expect(JSON.parse(String(seen[0]?.body))).toEqual({
      from_id: 2,
      to_id: 1,
      amount: '30.00',
    })
  })

  it('defaults the recipient to another member added after the page loaded', async () => {
    loggedIn()
    const created = vi.fn<Handler>(() =>
      jsonResponse(201, {
        id: 1,
        from_id: 1,
        to_id: 2,
        amount: '5.00',
        created_by: 1,
      }),
    )
    mockFetch({
      ...groupRoutes({
        group: { id: 1, name: 'Trip', members: [ALICE], former_members: [] },
      }),
      'POST /api/groups/1/members': () =>
        jsonResponse(201, {
          id: 1,
          name: 'Trip',
          members: [ALICE, BOB],
          former_members: [],
        }),
      'POST /api/groups/1/payments': created,
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('Add member by username'), {
      target: { value: 'bob' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add member' }))
    await waitFor(() =>
      expect(
        within(screen.getByRole('region', { name: 'Members' })).getByText(
          'bob',
        ),
      ).toBeInTheDocument(),
    )
    fireEvent.change(screen.getByLabelText('Payment amount'), {
      target: { value: '5.00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    await waitFor(() => expect(created).toHaveBeenCalledTimes(1))
    expect(JSON.parse(String(created.mock.calls[0]?.[0]?.body))).toEqual({
      from_id: 1,
      to_id: 2,
      amount: '5.00',
    })
  })

  it('lists payments', async () => {
    loggedIn()
    mockFetch(
      groupRoutes({
        payments: [
          { id: 1, from_id: 2, to_id: 1, amount: '30.00', created_by: 2 },
        ],
      }),
    )
    renderApp('/groups/1')
    expect(await screen.findByText('bob paid alice 30.00')).toBeInTheDocument()
  })

  it('lists the empty state', async () => {
    loggedIn()
    mockFetch(groupRoutes())
    renderApp('/groups/1')
    expect(await screen.findByText('No payments yet.')).toBeInTheDocument()
  })

  it('shows payment error', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/payments': () =>
        jsonResponse(422, {
          detail: 'payment sender and recipient must differ',
        }),
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('Payment amount'), {
      target: { value: '30.00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'payment sender and recipient must differ',
    )
  })
})

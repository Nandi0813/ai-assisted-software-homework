import { describe, it, expect } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { setToken } from '../api'
import { groupRoutes, jsonResponse, mockFetch, renderApp } from '../test/utils'

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

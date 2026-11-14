import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { setToken, type Expense } from '../api'
import {
  ALICE,
  BOB,
  CAROL,
  groupRoutes,
  jsonResponse,
  mockFetch,
  renderApp,
  type Handler,
} from '../test/utils'

function loggedIn(): void {
  setToken('t')
}

function fillDinner(amount: string): void {
  fireEvent.change(screen.getByLabelText('Description'), {
    target: { value: 'Dinner' },
  })
  fireEvent.change(screen.getByLabelText('Amount'), {
    target: { value: amount },
  })
}

const E1: Expense = {
  id: 1,
  description: 'Dinner',
  amount: '90.00',
  payer_id: 1,
  created_by: 1,
  split_type: 'equal',
  shares: [
    { user_id: 1, amount: '30.00', percent: null },
    { user_id: 2, amount: '30.00', percent: null },
    { user_id: 4, amount: '30.00', percent: null },
  ],
}

const E2: Expense = {
  id: 2,
  description: 'Taxi',
  amount: '12.00',
  payer_id: 2,
  created_by: 2,
  split_type: 'percent',
  shares: [
    { user_id: 2, amount: '6.00', percent: '50.00' },
    { user_id: 3, amount: '6.00', percent: '50.00' },
  ],
}

const CREATED: Expense = { ...E1, id: 3 }

describe('Expenses', () => {
  it('ac1 equal split sends all members', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/expenses': (init) => {
        seen.push(init)
        return jsonResponse(201, CREATED)
      },
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fillDinner('90.00')
    fireEvent.click(screen.getByRole('button', { name: 'Add expense' }))
    await waitFor(() => expect(seen).toHaveLength(1))
    expect(JSON.parse(String(seen[0]?.body))).toEqual({
      description: 'Dinner',
      amount: '90.00',
      payer_id: 1,
      split: { type: 'equal', participants: [1, 2, 3] },
    })
  })

  it('equal split without an unchecked member', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/expenses': (init) => {
        seen.push(init)
        return jsonResponse(201, CREATED)
      },
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.click(screen.getByLabelText('carol'))
    fillDinner('90.00')
    fireEvent.click(screen.getByRole('button', { name: 'Add expense' }))
    await waitFor(() => expect(seen).toHaveLength(1))
    expect(JSON.parse(String(seen[0]?.body))).toEqual({
      description: 'Dinner',
      amount: '90.00',
      payer_id: 1,
      split: { type: 'equal', participants: [1, 2] },
    })
  })

  it('ac3 exact split sends entered shares', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/expenses': (init) => {
        seen.push(init)
        return jsonResponse(201, CREATED)
      },
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('Split'), {
      target: { value: 'exact' },
    })
    fireEvent.change(screen.getByLabelText('alice amount'), {
      target: { value: '50.00' },
    })
    fireEvent.change(screen.getByLabelText('bob amount'), {
      target: { value: '40.00' },
    })
    fillDinner('90.00')
    fireEvent.click(screen.getByRole('button', { name: 'Add expense' }))
    await waitFor(() => expect(seen).toHaveLength(1))
    expect(JSON.parse(String(seen[0]?.body)).split).toEqual({
      type: 'exact',
      shares: [
        { user_id: 1, amount: '50.00' },
        { user_id: 2, amount: '40.00' },
      ],
    })
  })

  it('ac3 percent split sends entered percentages', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/expenses': (init) => {
        seen.push(init)
        return jsonResponse(201, CREATED)
      },
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('Split'), {
      target: { value: 'percent' },
    })
    fireEvent.change(screen.getByLabelText('alice %'), {
      target: { value: '50' },
    })
    fireEvent.change(screen.getByLabelText('bob %'), {
      target: { value: '50' },
    })
    fillDinner('90.00')
    fireEvent.click(screen.getByRole('button', { name: 'Add expense' }))
    await waitFor(() => expect(seen).toHaveLength(1))
    expect(JSON.parse(String(seen[0]?.body)).split).toEqual({
      type: 'percent',
      shares: [
        { user_id: 1, percent: '50' },
        { user_id: 2, percent: '50' },
      ],
    })
  })

  it('ac3 shows the server rejection', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/expenses': () =>
        jsonResponse(422, {
          detail: 'exact shares sum to 80.00, expected 90.00',
        }),
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fillDinner('90.00')
    fireEvent.click(screen.getByRole('button', { name: 'Add expense' }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toBe('exact shares sum to 80.00, expected 90.00')
    expect(screen.getByLabelText('Description')).toHaveValue('Dinner')
  })

  it('ac4 shows pydantic messages', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes(),
      'POST /api/groups/1/expenses': () =>
        jsonResponse(422, { detail: [{ msg: 'Field required' }] }),
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fillDinner('90.00')
    fireEvent.click(screen.getByRole('button', { name: 'Add expense' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Field required')
  })

  it('lists expenses with names and creator-only actions', async () => {
    loggedIn()
    mockFetch(
      groupRoutes({
        group: {
          id: 1,
          name: 'Trip',
          members: [ALICE, BOB, CAROL],
          former_members: [{ id: 4, username: 'dave' }],
        },
        expenses: [E1, E2],
      }),
    )
    renderApp('/groups/1')
    expect(await screen.findByText('Dinner')).toBeInTheDocument()
    expect(
      screen.getByText('alice 30.00, bob 30.00, dave 30.00'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('bob 6.00 (50.00%), carol 6.00 (50.00%)'),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Edit' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'Delete' })).toHaveLength(1)
  })

  it('delete removes and refreshes', async () => {
    loggedIn()
    const list = vi
      .fn<Handler>()
      .mockReturnValueOnce(jsonResponse(200, [E1]))
      .mockReturnValue(jsonResponse(200, []))
    mockFetch({
      ...groupRoutes(),
      'GET /api/groups/1/expenses': list,
      'DELETE /api/groups/1/expenses/1': () => jsonResponse(204),
    })
    renderApp('/groups/1')
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('No expenses yet.')).toBeInTheDocument()
  })

  it('edit loads the expense and sends PUT', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    const edited: Expense = {
      ...E1,
      shares: [
        { user_id: 1, amount: '30.00', percent: null },
        { user_id: 2, amount: '30.00', percent: null },
        { user_id: 3, amount: '30.00', percent: null },
      ],
    }
    mockFetch({
      ...groupRoutes({ expenses: [edited] }),
      'PUT /api/groups/1/expenses/1': (init) => {
        seen.push(init)
        return jsonResponse(200, { ...edited, amount: '99.00' })
      },
    })
    renderApp('/groups/1')
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(
      await screen.findByRole('heading', { name: 'Edit expense' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toHaveValue('Dinner')
    fireEvent.change(screen.getByLabelText('Amount'), {
      target: { value: '99.00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(seen).toHaveLength(1))
    expect(JSON.parse(String(seen[0]?.body))).toEqual({
      description: 'Dinner',
      amount: '99.00',
      payer_id: 1,
      split: { type: 'equal', participants: [1, 2, 3] },
    })
    expect(
      await screen.findByRole('heading', { name: 'Add expense' }),
    ).toBeInTheDocument()
  })
})

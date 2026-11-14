import { describe, it, expect } from 'vitest'
import { screen, fireEvent, within } from '@testing-library/react'
import { setToken } from '../api'
import {
  groupRoutes,
  jsonResponse,
  mockFetch,
  renderApp,
  type Handler,
} from '../test/utils'

function loggedIn(): void {
  setToken('t')
}

const ALICE = { id: 1, username: 'alice' }
const BOB = { id: 2, username: 'bob' }
const CAROL = { id: 3, username: 'carol' }
const G = {
  id: 1,
  name: 'Trip',
  members: [ALICE, BOB],
  former_members: [],
}

describe('GroupPage', () => {
  it('shows members', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes({ group: G }),
    })
    renderApp('/groups/1')
    expect(
      await screen.findByRole('heading', { name: 'Trip' }),
    ).toBeInTheDocument()
    const members = within(screen.getByRole('region', { name: 'Members' }))
    expect(members.getByText('alice')).toBeInTheDocument()
    expect(members.getByText('bob')).toBeInTheDocument()
    expect(screen.queryByText('Former members')).not.toBeInTheDocument()
  })

  it('shows former members', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes({ group: { ...G, former_members: [CAROL] } }),
    })
    renderApp('/groups/1')
    expect(await screen.findByText('Former members')).toBeInTheDocument()
    expect(screen.getByText('carol')).toBeInTheDocument()
  })

  it('shows not found', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes(),
      'GET /api/groups/1': () =>
        jsonResponse(404, { detail: 'group not found' }),
    })
    renderApp('/groups/1')
    expect(await screen.findByText('Group not found.')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Back to groups' }),
    ).toBeInTheDocument()
  })

  it('adds a member', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    const add: Handler = (init) => {
      seen.push(init)
      return jsonResponse(201, { ...G, members: [ALICE, BOB, CAROL] })
    }
    mockFetch({
      ...groupRoutes({ group: G }),
      'POST /api/groups/1/members': add,
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('Add member by username'), {
      target: { value: 'carol' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add member' }))
    expect(await screen.findByText('carol')).toBeInTheDocument()
    expect(JSON.parse(String(seen[0]?.body))).toEqual({ username: 'carol' })
  })

  it('shows add-member error', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes({ group: G }),
      'POST /api/groups/1/members': () =>
        jsonResponse(404, { detail: 'user not found' }),
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.change(screen.getByLabelText('Add member by username'), {
      target: { value: 'nobody' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add member' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('user not found')
  })

  it('ac7 shows the outstanding amount when leaving is refused', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes({ group: G }),
      'POST /api/groups/1/leave': () =>
        jsonResponse(409, {
          detail:
            'cannot leave the group with an outstanding balance of -30.00',
        }),
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.click(screen.getByRole('button', { name: 'Leave group' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'cannot leave the group with an outstanding balance of -30.00',
    )
    expect(screen.getByRole('heading', { name: 'Trip' })).toBeInTheDocument()
  })

  it('leaving returns to the group list', async () => {
    loggedIn()
    mockFetch({
      ...groupRoutes({ group: G }),
      'POST /api/groups/1/leave': () => jsonResponse(204),
      'GET /api/groups': () => jsonResponse(200, []),
    })
    renderApp('/groups/1')
    await screen.findByRole('heading', { name: 'Trip' })
    fireEvent.click(screen.getByRole('button', { name: 'Leave group' }))
    expect(
      await screen.findByRole('heading', { name: 'Your groups' }),
    ).toBeInTheDocument()
  })
})

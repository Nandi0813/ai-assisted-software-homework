import { describe, it, expect } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { setToken } from '../api'
import { jsonResponse, mockFetch, renderApp, type Handler } from '../test/utils'

function loggedIn(): void {
  setToken('t')
}

const ALICE = { id: 1, username: 'alice' }

describe('GroupsPage', () => {
  it('lists groups as links', async () => {
    loggedIn()
    mockFetch({
      'GET /api/auth/me': () => jsonResponse(200, ALICE),
      'GET /api/groups': () =>
        jsonResponse(200, [
          { id: 1, name: 'Trip' },
          { id: 2, name: 'Flat' },
        ]),
    })
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Trip' })).toHaveAttribute(
      'href',
      '/groups/1',
    )
    expect(screen.getByRole('link', { name: 'Flat' })).toHaveAttribute(
      'href',
      '/groups/2',
    )
  })

  it('shows the empty state', async () => {
    loggedIn()
    mockFetch({
      'GET /api/auth/me': () => jsonResponse(200, ALICE),
      'GET /api/groups': () => jsonResponse(200, []),
    })
    renderApp('/')
    expect(await screen.findByText('No groups yet.')).toBeInTheDocument()
  })

  it('creates a group and opens it', async () => {
    loggedIn()
    const seen: Array<RequestInit | undefined> = []
    const create: Handler = (init) => {
      seen.push(init)
      return jsonResponse(201, {
        id: 3,
        name: 'Ski',
        members: [ALICE],
        former_members: [],
      })
    }
    const detail = () =>
      jsonResponse(200, {
        id: 3,
        name: 'Ski',
        members: [ALICE],
        former_members: [],
      })
    mockFetch({
      'GET /api/auth/me': () => jsonResponse(200, ALICE),
      'GET /api/groups': () => jsonResponse(200, []),
      'POST /api/groups': create,
      'GET /api/groups/3': detail,
    })
    renderApp('/')
    await screen.findByText('No groups yet.')
    fireEvent.change(screen.getByLabelText('New group name'), {
      target: { value: 'Ski' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create group' }))
    expect(
      await screen.findByRole('heading', { name: 'Ski' }),
    ).toBeInTheDocument()
    expect(JSON.parse(String(seen[0]?.body))).toEqual({ name: 'Ski' })
  })
})

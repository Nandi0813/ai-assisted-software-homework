import { describe, it, expect } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { getToken, setToken } from './api'
import { jsonResponse, mockFetch, renderApp } from './test/utils'

function loggedIn(): void {
  setToken('t')
}

describe('App', () => {
  it('shows the login form when signed out', () => {
    mockFetch({})
    renderApp('/')
    expect(
      screen.getByRole('heading', { level: 1, name: 'SplitLedger' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument()
  })

  it('shows groups when a token is stored', async () => {
    loggedIn()
    mockFetch({
      'GET /api/auth/me': () => jsonResponse(200, { id: 1, username: 'alice' }),
      'GET /api/groups': () => jsonResponse(200, []),
    })
    renderApp('/')
    expect(await screen.findByText('Signed in as alice')).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Your groups' }),
    ).toBeInTheDocument()
  })

  it('log out returns to the login form', async () => {
    loggedIn()
    mockFetch({
      'GET /api/auth/me': () => jsonResponse(200, { id: 1, username: 'alice' }),
      'GET /api/groups': () => jsonResponse(200, []),
    })
    renderApp('/')
    await screen.findByText('Signed in as alice')
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(getToken()).toBeNull()
  })

  it('invalid stored token shows the login form', async () => {
    setToken('bad')
    mockFetch({
      'GET /api/auth/me': () =>
        jsonResponse(401, { detail: 'not authenticated' }),
    })
    renderApp('/')
    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(getToken()).toBeNull()
  })
})

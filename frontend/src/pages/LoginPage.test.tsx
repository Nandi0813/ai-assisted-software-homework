import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { jsonResponse, mockFetch, renderApp } from '../test/utils'

const ALICE = { id: 1, username: 'alice' }

function fillAndSubmit(submitName: string): void {
  fireEvent.change(screen.getByLabelText('Username'), {
    target: { value: 'alice' },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'pw123456' },
  })
  fireEvent.click(screen.getByRole('button', { name: submitName }))
}

describe('LoginPage', () => {
  it('logs in', async () => {
    mockFetch({
      'POST /api/auth/login': () =>
        jsonResponse(200, { access_token: 'tok', token_type: 'bearer' }),
      'GET /api/auth/me': () => jsonResponse(200, ALICE),
      'GET /api/groups': () => jsonResponse(200, []),
    })
    renderApp('/')
    fillAndSubmit('Log in')
    expect(await screen.findByText('Signed in as alice')).toBeInTheDocument()
  })

  it('shows the login error', async () => {
    mockFetch({
      'POST /api/auth/login': () =>
        jsonResponse(401, { detail: 'incorrect username or password' }),
    })
    renderApp('/')
    fillAndSubmit('Log in')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'incorrect username or password',
    )
  })

  it('registers then logs in', async () => {
    const register = vi.fn(() => jsonResponse(201, ALICE))
    mockFetch({
      'POST /api/auth/register': register,
      'POST /api/auth/login': () =>
        jsonResponse(200, { access_token: 'tok', token_type: 'bearer' }),
      'GET /api/auth/me': () => jsonResponse(200, ALICE),
      'GET /api/groups': () => jsonResponse(200, []),
    })
    renderApp('/')
    fireEvent.click(
      screen.getByRole('button', { name: 'Need an account? Register' }),
    )
    expect(
      screen.getByRole('heading', { name: 'Create account' }),
    ).toBeInTheDocument()
    fillAndSubmit('Create account')
    expect(await screen.findByText('Signed in as alice')).toBeInTheDocument()
    expect(register).toHaveBeenCalledTimes(1)
  })

  it('shows the validation message on 422', async () => {
    mockFetch({
      'POST /api/auth/register': () =>
        jsonResponse(422, {
          detail: [
            {
              msg: 'Value error, username must be 3-32 characters of letters, digits or underscore',
            },
          ],
        }),
    })
    renderApp('/')
    fireEvent.click(
      screen.getByRole('button', { name: 'Need an account? Register' }),
    )
    fillAndSubmit('Create account')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Value error, username must be 3-32 characters of letters, digits or underscore',
    )
  })
})

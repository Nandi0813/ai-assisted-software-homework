import { describe, it, expect } from 'vitest'
import {
  ApiError,
  errorMessage,
  getToken,
  listGroups,
  login,
  me,
  setToken,
} from './api'
import { jsonResponse, mockFetch, type Handler } from './test/utils'

describe('errorMessage', () => {
  it('returns the string detail', () => {
    expect(errorMessage({ detail: 'boom' }, 400)).toBe('boom')
  })

  it('joins pydantic messages', () => {
    expect(errorMessage({ detail: [{ msg: 'a' }, { msg: 'b' }] }, 422)).toBe(
      'a; b',
    )
  })

  it('falls back when there is no usable message', () => {
    expect(errorMessage(null, 500)).toBe('Request failed (500)')
    expect(errorMessage({ detail: [{ loc: [] }] }, 422)).toBe(
      'Request failed (422)',
    )
  })
})

describe('request', () => {
  it('sends the bearer token', async () => {
    setToken('abc')
    const seen: Array<RequestInit | undefined> = []
    const handler: Handler = (init) => {
      seen.push(init)
      return jsonResponse(200, [])
    }
    mockFetch({ 'GET /api/groups': handler })
    await listGroups()
    expect(new Headers(seen[0]?.headers).get('Authorization')).toBe(
      'Bearer abc',
    )
  })

  it('clears the token on 401', async () => {
    setToken('abc')
    mockFetch({
      'GET /api/auth/me': () =>
        jsonResponse(401, { detail: 'not authenticated' }),
    })
    await expect(me()).rejects.toBeInstanceOf(ApiError)
    await expect(me()).rejects.toMatchObject({
      status: 401,
      message: 'not authenticated',
    })
    expect(getToken()).toBeNull()
  })
})

describe('login', () => {
  it('posts a form and stores the token', async () => {
    const seen: Array<RequestInit | undefined> = []
    const handler: Handler = (init) => {
      seen.push(init)
      return jsonResponse(200, { access_token: 'tok', token_type: 'bearer' })
    }
    mockFetch({ 'POST /api/auth/login': handler })
    await login('alice', 'pw123456')
    expect(seen[0]?.body).toBeInstanceOf(URLSearchParams)
    expect(String(seen[0]?.body)).toBe('username=alice&password=pw123456')
    expect(getToken()).toBe('tok')
    expect(sessionStorage.getItem('splitledger.token')).toBe('tok')
  })
})

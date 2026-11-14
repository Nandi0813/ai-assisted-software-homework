export interface User {
  id: number
  username: string
}

export interface GroupSummary {
  id: number
  name: string
}

export interface GroupDetail {
  id: number
  name: string
  members: User[]
  former_members: User[]
}

const TOKEN_KEY = 'splitledger.token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

let token: string | null = readStoredToken()

export function getToken(): string | null {
  return token
}

export function setToken(value: string | null): void {
  token = value
  try {
    if (value === null) {
      sessionStorage.removeItem(TOKEN_KEY)
    } else {
      sessionStorage.setItem(TOKEN_KEY, value)
    }
  } catch {
    // storage may be unavailable; the in-memory token still applies
  }
}

export function errorMessage(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = body.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item: unknown) =>
        typeof item === 'object' &&
        item !== null &&
        'msg' in item &&
        typeof item.msg === 'string'
          ? [item.msg]
          : [],
      )
      if (messages.length > 0) {
        return messages.join('; ')
      }
    }
  }
  return `Request failed (${status})`
}

interface RequestOptions {
  method?: string
  json?: unknown
  form?: URLSearchParams
}

async function call(
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const headers = new Headers()
  if (token !== null) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.json)
  } else if (options.form !== undefined) {
    body = options.form
  }
  const response = await fetch(`/api${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
  })
  if (!response.ok) {
    let parsed: unknown
    try {
      parsed = await response.json()
    } catch {
      parsed = null
    }
    if (response.status === 401) {
      setToken(null)
    }
    throw new ApiError(response.status, errorMessage(parsed, response.status))
  }
  return response
}

export async function request<T>(
  path: string,
  options?: RequestOptions,
): Promise<T> {
  const response = await call(path, options)
  return (await response.json()) as T // trusted: shape fixed by backend schemas
}

export async function send(
  path: string,
  options?: RequestOptions,
): Promise<void> {
  await call(path, options)
}

export function register(username: string, password: string): Promise<User> {
  return request<User>('/auth/register', {
    method: 'POST',
    json: { username, password },
  })
}

export async function login(username: string, password: string): Promise<void> {
  const form = new URLSearchParams({ username, password })
  const data = await request<{ access_token: string }>('/auth/login', {
    method: 'POST',
    form,
  })
  setToken(data.access_token)
}

export function me(): Promise<User> {
  return request<User>('/auth/me')
}

export function listGroups(): Promise<GroupSummary[]> {
  return request<GroupSummary[]>('/groups')
}

export function getGroup(groupId: number): Promise<GroupDetail> {
  return request<GroupDetail>(`/groups/${groupId}`)
}

export function createGroup(name: string): Promise<GroupDetail> {
  return request<GroupDetail>('/groups', { method: 'POST', json: { name } })
}

export function addMember(
  groupId: number,
  username: string,
): Promise<GroupDetail> {
  return request<GroupDetail>(`/groups/${groupId}/members`, {
    method: 'POST',
    json: { username },
  })
}

export function leaveGroup(groupId: number): Promise<void> {
  return send(`/groups/${groupId}/leave`, { method: 'POST' })
}

export interface MemberBalance {
  user_id: number
  username: string
  balance: string
  active: boolean
}

export interface Transfer {
  from_id: number
  from_username: string
  to_id: number
  to_username: string
  amount: string
}

export interface Balances {
  members: MemberBalance[]
  transfers: Transfer[]
}

export function getBalances(groupId: number): Promise<Balances> {
  return request<Balances>(`/groups/${groupId}/balances`)
}

export function recordPayment(
  groupId: number,
  payment: { from_id: number; to_id: number; amount: string },
): Promise<void> {
  return send(`/groups/${groupId}/payments`, { method: 'POST', json: payment })
}

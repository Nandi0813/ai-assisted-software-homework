import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import type { User } from './api'
import { AuthContext, type AuthState } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState<boolean>(api.getToken() !== null)

  useEffect(() => {
    if (api.getToken() === null) {
      return
    }
    let cancelled = false
    api
      .me()
      .then((current) => {
        if (!cancelled) setUser(current)
      })
      .catch(() => {
        if (!cancelled) api.setToken(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo<AuthState>(() => {
    const login = async (username: string, password: string) => {
      await api.login(username, password)
      setUser(await api.me())
    }
    const register = async (username: string, password: string) => {
      await api.register(username, password)
      await login(username, password)
    }
    const logout = () => {
      api.setToken(null)
      setUser(null)
      queryClient.clear()
    }
    return { user, loading, login, register, logout }
  }, [user, loading, queryClient])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

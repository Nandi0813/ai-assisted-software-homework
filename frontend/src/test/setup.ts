import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { setToken } from '../api'

afterEach(cleanup)

afterEach(() => {
  setToken(null)
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

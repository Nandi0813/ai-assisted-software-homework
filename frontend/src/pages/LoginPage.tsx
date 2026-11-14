import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth-context'

export function LoginPage() {
  const auth = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const registering = mode === 'register'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (registering) {
        await auth.register(username, password)
      } else {
        await auth.login(username, password)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    setMode(registering ? 'login' : 'register')
    setError(null)
  }

  const submitLabel = registering ? 'Create account' : 'Log in'

  return (
    <div className="narrow">
      <section className="panel">
        <h2>{submitLabel}</h2>
        <p className="lede">
          Split shared costs with your group and see who owes whom.
        </p>
        <form onSubmit={handleSubmit}>
          <label>
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={registering ? 'new-password' : 'current-password'}
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            {submitLabel}
          </button>
        </form>
        {registering && (
          <p>3–32 letters, digits or _; password at least 8 characters.</p>
        )}
        {error !== null && <p role="alert">{error}</p>}
        <button type="button" className="button-link" onClick={switchMode}>
          {registering
            ? 'Have an account? Log in'
            : 'Need an account? Register'}
        </button>
      </section>
    </div>
  )
}

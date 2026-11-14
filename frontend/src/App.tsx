import { Link, Navigate, Route, Routes } from 'react-router'
import { useAuth } from './auth-context'
import { GroupPage } from './pages/GroupPage'
import { GroupsPage } from './pages/GroupsPage'
import { LoginPage } from './pages/LoginPage'

export default function App() {
  const auth = useAuth()

  return (
    <>
      <header>
        <h1>
          <Link to="/">SplitLedger</Link>
        </h1>
        {auth.user !== null && (
          <div>
            <span>{`Signed in as ${auth.user.username}`}</span>
            <button type="button" onClick={auth.logout}>
              Log out
            </button>
          </div>
        )}
      </header>
      <main>
        {auth.loading ? (
          <p>Loading…</p>
        ) : auth.user === null ? (
          <LoginPage />
        ) : (
          <Routes>
            <Route path="/" element={<GroupsPage />} />
            <Route path="/groups/:groupId" element={<GroupPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
    </>
  )
}

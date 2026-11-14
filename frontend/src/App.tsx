import { Link, Navigate, Route, Routes } from 'react-router'
import { useAuth } from './auth-context'
import { GroupPage } from './pages/GroupPage'
import { GroupsPage } from './pages/GroupsPage'
import { LoginPage } from './pages/LoginPage'

export default function App() {
  const auth = useAuth()

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <h1>
            <Link to="/">SplitLedger</Link>
          </h1>
          {auth.user !== null && (
            <div className="session">
              <span>{`Signed in as ${auth.user.username}`}</span>
              <button
                type="button"
                className="button-quiet"
                onClick={auth.logout}
              >
                Log out
              </button>
            </div>
          )}
        </div>
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

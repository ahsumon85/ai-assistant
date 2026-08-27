import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { useAuth } from './auth'

export default function Layout() {
  const { user, logout } = useAuth()

  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>JobFlow</h1>
        <NavLink to="/" end>Dashboard</NavLink>
        <NavLink to="/jobs">Jobs</NavLink>
        <NavLink to="/applications">Applications</NavLink>
        <NavLink to="/candidate">My Profile</NavLink>
        <NavLink to="/settings">Settings</NavLink>
        <div style={{ flex: 1 }} />
        <div style={{ color: 'var(--muted)', fontSize: '0.8rem', padding: '0.75rem' }}>
          {user.email}
        </div>
        <button className="btn btn-ghost" onClick={logout} style={{ width: '100%' }}>
          Log out
        </button>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}

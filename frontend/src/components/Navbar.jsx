// Top navigation. Only shown when authenticated.

import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const { user, isAuthenticated, isAdmin, logout } = useAuth()
  const navigate = useNavigate()

  if (!isAuthenticated) return null

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">Watchtower</div>
      <div className="navbar-links">
        <NavLink to="/dashboard">Watchlists</NavLink>
        <NavLink to="/alerts">Alerts</NavLink>
        {isAdmin && <NavLink to="/admin">Admin</NavLink>}
      </div>
      <div className="navbar-user">
        <span className="navbar-email">{user?.email}</span>
        {isAdmin && <span className="badge badge-admin">admin</span>}
        <button className="btn btn-ghost" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </nav>
  )
}

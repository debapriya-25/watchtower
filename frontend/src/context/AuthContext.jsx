// Authentication state: current user + login/register/logout.
// Tokens live in localStorage (managed by api/client.js); this context holds
// the user object and exposes auth helpers + role flags.

import { createContext, useContext, useEffect, useState } from 'react'
import { AuthAPI } from '../api/endpoints'
import {
  clearAuth,
  getStoredUser,
  setStoredUser,
  setTokens,
} from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser())

  // The API client dispatches `auth:logout` when a token refresh fails.
  useEffect(() => {
    const handler = () => setUser(null)
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  function persist(data) {
    setTokens(data.tokens.access_token, data.tokens.refresh_token)
    setStoredUser(data.user)
    setUser(data.user)
  }

  async function login(email, password) {
    const data = await AuthAPI.login({ email, password })
    persist(data)
    return data.user
  }

  async function register(email, password, fullName) {
    const data = await AuthAPI.register({
      email,
      password,
      full_name: fullName || undefined,
    })
    persist(data)
    return data.user
  }

  function logout() {
    clearAuth()
    setUser(null)
  }

  const value = {
    user,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

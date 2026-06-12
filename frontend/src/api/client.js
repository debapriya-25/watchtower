// Axios instance + helpers for the Watchtower API.
//
// Responsibilities:
//   * attach the JWT access token to every request,
//   * transparently refresh the access token on a 401 (rotating refresh token),
//   * unwrap the standard `{ success, data, error }` envelope,
//   * normalise API errors into plain Error objects with `.code`/`.status`.

import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const ACCESS_KEY = 'wt_access'
const REFRESH_KEY = 'wt_refresh'
const USER_KEY = 'wt_user'

export const api = axios.create({ baseURL })

// --- token storage --------------------------------------------------------
export const getAccessToken = () => localStorage.getItem(ACCESS_KEY)
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY)

export function setTokens(access, refresh) {
  if (access) localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function setStoredUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export function clearAuth() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
}

// --- request: attach bearer token ----------------------------------------
api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// --- response: refresh-on-401 (single in-flight refresh) ------------------
let refreshPromise = null

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {}
    const status = error.response?.status
    const url = original.url || ''
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/register')

    if (status === 401 && !original._retry && getRefreshToken() && !isAuthCall) {
      original._retry = true
      try {
        if (!refreshPromise) {
          refreshPromise = axios.post(`${baseURL}/auth/refresh`, {
            refresh_token: getRefreshToken(),
          })
        }
        const res = await refreshPromise
        refreshPromise = null
        const tokens = res.data?.data
        setTokens(tokens.access_token, tokens.refresh_token)
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${tokens.access_token}`
        return api(original)
      } catch (refreshErr) {
        refreshPromise = null
        clearAuth()
        // Let the AuthContext drop the session and ProtectedRoute redirect.
        window.dispatchEvent(new Event('auth:logout'))
        return Promise.reject(refreshErr)
      }
    }
    return Promise.reject(error)
  },
)

// --- envelope unwrap + error normalisation --------------------------------
function normalizeError(error) {
  const envelope = error.response?.data
  const err = new Error(
    envelope?.error?.message || error.message || 'Request failed',
  )
  err.code = envelope?.error?.code
  err.status = error.response?.status
  err.details = envelope?.error?.details
  return err
}

/** Await an axios request and return the unwrapped `data`, or throw a clean Error. */
export async function call(request) {
  try {
    const response = await request
    return response.data?.data
  } catch (error) {
    throw normalizeError(error)
  }
}

// Thin, typed-ish wrappers over the Watchtower API. Each function returns the
// already-unwrapped `data` (or throws a normalised Error).

import { api, call } from './client'

export const AuthAPI = {
  register: (body) => call(api.post('/auth/register', body)),
  login: (body) => call(api.post('/auth/login', body)),
  me: () => call(api.get('/auth/me')),
}

export const TokensAPI = {
  list: (page = 1, size = 100) =>
    call(api.get('/api/v1/tokens', { params: { page, size } })),
  price: (tokenId) => call(api.get(`/api/v1/tokens/${tokenId}/price`)),
}

export const WatchlistsAPI = {
  list: () => call(api.get('/api/v1/watchlists')),
  get: (id) => call(api.get(`/api/v1/watchlists/${id}`)),
  create: (name) => call(api.post('/api/v1/watchlists', { name })),
  rename: (id, name) => call(api.patch(`/api/v1/watchlists/${id}`, { name })),
  remove: (id) => call(api.delete(`/api/v1/watchlists/${id}`)),
  addToken: (id, tokenId) =>
    call(api.post(`/api/v1/watchlists/${id}/tokens`, { token_id: tokenId })),
  removeToken: (id, tokenId) =>
    call(api.delete(`/api/v1/watchlists/${id}/tokens/${tokenId}`)),
}

export const AlertsAPI = {
  list: () => call(api.get('/api/v1/alerts')),
  create: (body) => call(api.post('/api/v1/alerts', body)),
  update: (id, body) => call(api.patch(`/api/v1/alerts/${id}`, body)),
  remove: (id) => call(api.delete(`/api/v1/alerts/${id}`)),
  activate: (id) => call(api.post(`/api/v1/alerts/${id}/activate`)),
  deactivate: (id) => call(api.post(`/api/v1/alerts/${id}/deactivate`)),
}

export const AdminAPI = {
  users: (page = 1, size = 50) =>
    call(api.get('/api/v1/admin/users', { params: { page, size } })),
  setActive: (id, isActive) =>
    call(api.patch(`/api/v1/admin/users/${id}`, { is_active: isActive })),
}

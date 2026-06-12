import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { WatchlistsAPI } from '../api/endpoints'
import { useToast } from '../context/ToastContext'

export default function Dashboard() {
  const toast = useToast()
  const [watchlists, setWatchlists] = useState([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const data = await WatchlistsAPI.list()
      setWatchlists(data.items)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      const created = await WatchlistsAPI.create(name.trim())
      // List is ordered oldest-first → append. `created` is a detail object;
      // derive the summary shape the list renders (item_count).
      setWatchlists((prev) => [
        ...prev,
        { ...created, item_count: created.items.length },
      ])
      toast.success('Watchlist created')
      setName('')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleRename(wl) {
    const next = window.prompt('Rename watchlist', wl.name)
    if (!next || next.trim() === wl.name) return
    try {
      const updated = await WatchlistsAPI.rename(wl.id, next.trim())
      setWatchlists((prev) =>
        prev.map((w) =>
          w.id === updated.id
            ? { ...w, name: updated.name, updated_at: updated.updated_at }
            : w,
        ),
      )
      toast.success('Watchlist renamed')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDelete(wl) {
    if (!window.confirm(`Delete watchlist "${wl.name}"?`)) return
    try {
      await WatchlistsAPI.remove(wl.id)
      setWatchlists((prev) => prev.filter((w) => w.id !== wl.id))
      toast.success('Watchlist deleted')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>My Watchlists</h1>
      </div>

      <form className="card inline-form" onSubmit={handleCreate}>
        <label>
          New watchlist
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. DeFi blue chips"
            maxLength={120}
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={creating}>
          {creating ? 'Creating…' : 'Create'}
        </button>
      </form>

      <div className="card">
        {loading ? (
          <p className="empty">Loading…</p>
        ) : watchlists.length === 0 ? (
          <p className="empty">No watchlists yet. Create one above.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Tokens</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {watchlists.map((wl) => (
                <tr key={wl.id}>
                  <td>
                    <Link to={`/watchlists/${wl.id}`}>{wl.name}</Link>
                  </td>
                  <td>{wl.item_count}</td>
                  <td className="muted">
                    {new Date(wl.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="row">
                      <button
                        className="btn btn-sm"
                        onClick={() => handleRename(wl)}
                      >
                        Rename
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(wl)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

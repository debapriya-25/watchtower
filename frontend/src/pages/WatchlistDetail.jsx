import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { TokensAPI, WatchlistsAPI } from '../api/endpoints'
import { useToast } from '../context/ToastContext'

export default function WatchlistDetail() {
  const { id } = useParams()
  const toast = useToast()

  const [watchlist, setWatchlist] = useState(null)
  const [catalogue, setCatalogue] = useState([])
  const [prices, setPrices] = useState({}) // token_id -> { price, cached } | { error }
  const [loading, setLoading] = useState(true)
  const [selectedToken, setSelectedToken] = useState('')
  const [adding, setAdding] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [wl, cat] = await Promise.all([
        WatchlistsAPI.get(id),
        TokensAPI.list(1, 100),
      ])
      setWatchlist(wl)
      setCatalogue(cat.items)
      loadPrices(wl.items)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadPrices(items) {
    const entries = await Promise.all(
      items.map(async (item) => {
        try {
          const p = await TokensAPI.price(item.token_id)
          return [item.token_id, { price: p.price, cached: p.cached }]
        } catch {
          return [item.token_id, { error: true }]
        }
      }),
    )
    setPrices(Object.fromEntries(entries))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function handleAdd(e) {
    e.preventDefault()
    if (!selectedToken) return
    setAdding(true)
    try {
      await WatchlistsAPI.addToken(id, selectedToken)
      toast.success('Token added')
      setSelectedToken('')
      load()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setAdding(false)
    }
  }

  async function handleRemove(item) {
    try {
      await WatchlistsAPI.removeToken(id, item.token_id)
      toast.success(`${item.token.symbol} removed`)
      load()
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <p className="empty">Loading…</p>
  if (!watchlist) return <p className="empty">Watchlist not found.</p>

  const ownedIds = new Set(watchlist.items.map((i) => i.token_id))
  const available = catalogue.filter((t) => !ownedIds.has(t.id))

  return (
    <>
      <div className="page-header">
        <h1>{watchlist.name}</h1>
        <Link to="/dashboard" className="btn btn-sm">
          ← Back
        </Link>
      </div>

      <form className="card inline-form" onSubmit={handleAdd}>
        <label>
          Add token
          <select
            value={selectedToken}
            onChange={(e) => setSelectedToken(e.target.value)}
          >
            <option value="">Select a token…</option>
            {available.map((t) => (
              <option key={t.id} value={t.id}>
                {t.symbol} — {t.name}
              </option>
            ))}
          </select>
        </label>
        <button className="btn btn-primary" type="submit" disabled={adding}>
          {adding ? 'Adding…' : 'Add'}
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => loadPrices(watchlist.items)}
        >
          Refresh prices
        </button>
      </form>

      <div className="card">
        {watchlist.items.length === 0 ? (
          <p className="empty">No tokens yet. Add one above.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Name</th>
                <th>Price (USD)</th>
                <th>Source</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {watchlist.items.map((item) => {
                const p = prices[item.token_id]
                return (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.token.symbol}</strong>
                    </td>
                    <td>{item.token.name}</td>
                    <td>
                      {!p ? (
                        <span className="muted">…</span>
                      ) : p.error ? (
                        <span className="muted">—</span>
                      ) : (
                        `$${p.price.toLocaleString()}`
                      )}
                    </td>
                    <td>
                      {p && !p.error && (
                        <span
                          className={`badge ${p.cached ? 'badge-cached' : 'badge-live'}`}
                        >
                          {p.cached ? 'cached' : 'live'}
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleRemove(item)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

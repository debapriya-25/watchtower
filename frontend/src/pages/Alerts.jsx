import { useEffect, useState } from 'react'
import { AlertsAPI, TokensAPI } from '../api/endpoints'
import { useToast } from '../context/ToastContext'

export default function Alerts() {
  const toast = useToast()
  const [alerts, setAlerts] = useState([])
  const [catalogue, setCatalogue] = useState([])
  const [loading, setLoading] = useState(true)

  const [tokenId, setTokenId] = useState('')
  const [condition, setCondition] = useState('ABOVE')
  const [targetPrice, setTargetPrice] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [a, cat] = await Promise.all([
        AlertsAPI.list(),
        TokensAPI.list(1, 100),
      ])
      setAlerts(a.items)
      setCatalogue(cat.items)
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
    const price = Number(targetPrice)
    if (!tokenId || !(price > 0)) {
      toast.error('Pick a token and a target price greater than 0')
      return
    }
    setCreating(true)
    try {
      await AlertsAPI.create({
        token_id: tokenId,
        condition,
        target_price: price,
      })
      toast.success('Alert created')
      setTokenId('')
      setTargetPrice('')
      load()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function toggleActive(alert) {
    try {
      if (alert.is_active) {
        await AlertsAPI.deactivate(alert.id)
        toast.success('Alert deactivated')
      } else {
        await AlertsAPI.activate(alert.id)
        toast.success('Alert reactivated')
      }
      load()
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDelete(alert) {
    if (!window.confirm('Delete this alert?')) return
    try {
      await AlertsAPI.remove(alert.id)
      toast.success('Alert deleted')
      load()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Price Alerts</h1>
      </div>

      <form className="card inline-form" onSubmit={handleCreate}>
        <label>
          Token
          <select value={tokenId} onChange={(e) => setTokenId(e.target.value)}>
            <option value="">Select a token…</option>
            {catalogue.map((t) => (
              <option key={t.id} value={t.id}>
                {t.symbol} — {t.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Condition
          <select
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
          >
            <option value="ABOVE">Above</option>
            <option value="BELOW">Below</option>
          </select>
        </label>
        <label>
          Target price (USD)
          <input
            type="number"
            min="0"
            step="any"
            value={targetPrice}
            onChange={(e) => setTargetPrice(e.target.value)}
            placeholder="e.g. 75000"
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={creating}>
          {creating ? 'Creating…' : 'Create alert'}
        </button>
      </form>

      <div className="card">
        {loading ? (
          <p className="empty">Loading…</p>
        ) : alerts.length === 0 ? (
          <p className="empty">No alerts yet. Create one above.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Token</th>
                <th>Condition</th>
                <th>Target (USD)</th>
                <th>Status</th>
                <th>Triggered</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <strong>{a.token.symbol}</strong>{' '}
                    <span className="muted">{a.token.name}</span>
                  </td>
                  <td>{a.condition === 'ABOVE' ? 'Above' : 'Below'}</td>
                  <td>${Number(a.target_price).toLocaleString()}</td>
                  <td>
                    <span className={`badge ${a.is_active ? 'badge-ok' : 'badge-off'}`}>
                      {a.is_active ? 'active' : 'inactive'}
                    </span>
                  </td>
                  <td className="muted">
                    {a.triggered_at
                      ? new Date(a.triggered_at).toLocaleString()
                      : '—'}
                  </td>
                  <td>
                    <div className="row">
                      <button
                        className="btn btn-sm"
                        onClick={() => toggleActive(a)}
                      >
                        {a.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(a)}
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

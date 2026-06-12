import { useEffect, useState } from 'react'
import { AdminAPI } from '../api/endpoints'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

export default function Admin() {
  const toast = useToast()
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const data = await AdminAPI.users(1, 50)
      setUsers(data.items)
      setTotal(data.pagination.total)
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

  async function toggleActive(u) {
    try {
      await AdminAPI.setActive(u.id, !u.is_active)
      toast.success(`${u.email} ${u.is_active ? 'deactivated' : 'activated'}`)
      load()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Admin — Users</h1>
        <span className="muted">{total} total</span>
      </div>

      <div className="card">
        {loading ? (
          <p className="empty">Loading…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>
                    <span
                      className={`badge ${u.role === 'admin' ? 'badge-admin' : 'badge-off'}`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'badge-ok' : 'badge-off'}`}>
                      {u.is_active ? 'active' : 'inactive'}
                    </span>
                  </td>
                  <td className="muted">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <button
                      className="btn btn-sm"
                      disabled={u.id === me?.id}
                      title={u.id === me?.id ? 'You cannot change your own status' : ''}
                      onClick={() => toggleActive(u)}
                    >
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
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

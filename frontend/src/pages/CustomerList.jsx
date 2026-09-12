import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';

export default function CustomerList() {
  const authFetch = useAuthFetch();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteError, setDeleteError] = useState({});

  const loadCustomers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/customers/`);
      if (response.ok) {
        const data = await response.json();
        setCustomers(Array.isArray(data) ? data : data.results ?? []);
      } else if (response.status !== 401) {
        setError(`Server returned ${response.status}`);
      }
    } catch (err) {
      setError('Network error: could not reach the server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, []);

  const handleDelete = async (id) => {
    setDeletingId(id);
    setDeleteError((prev) => ({ ...prev, [id]: null }));

    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/customers/${id}/`, {
        method: 'DELETE',
      });

      if (response.status === 204) {
        setConfirmingId(null);
        await loadCustomers();
        return;
      }

      if (response.status === 409) {
        const data = await response.json();
        setDeleteError((prev) => ({ ...prev, [id]: data.detail }));
      } else if (response.status !== 401) {
        setDeleteError((prev) => ({ ...prev, [id]: `Server returned ${response.status}` }));
      }
    } catch (err) {
      setDeleteError((prev) => ({ ...prev, [id]: 'Network error: could not reach the server' }));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      <h1>Customers</h1>
      <Link to="/customers/new">New Customer</Link>
      {loading && <p>Loading...</p>}
      {error && <p>{error}</p>}
      <ul>
        {customers.map((c) => (
          <li key={c.id}>
            {c.name}{' '}
            <Link to={`/customers/${c.id}/edit`}>Edit</Link>{' '}
            {confirmingId === c.id ? (
              <>
                <span>Delete this customer?</span>{' '}
                <button
                  onClick={() => handleDelete(c.id)}
                  disabled={deletingId === c.id}
                >
                  {deletingId === c.id ? 'Deleting...' : 'Yes, delete'}
                </button>{' '}
                <button onClick={() => setConfirmingId(null)} disabled={deletingId === c.id}>
                  Cancel
                </button>
                {deleteError[c.id] && <p>{deleteError[c.id]}</p>}
              </>
            ) : (
              <button onClick={() => setConfirmingId(c.id)}>Delete</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

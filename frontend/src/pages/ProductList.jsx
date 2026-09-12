import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';

export default function ProductList() {
  const authFetch = useAuthFetch();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteError, setDeleteError] = useState({});

  const loadProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/products/`);
      if (response.ok) {
        const data = await response.json();
        setProducts(Array.isArray(data) ? data : data.results ?? []);
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
    loadProducts();
  }, []);

  const handleDelete = async (id) => {
    setDeletingId(id);
    setDeleteError((prev) => ({ ...prev, [id]: null }));

    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/products/${id}/`, {
        method: 'DELETE',
      });

      if (response.status === 204) {
        setConfirmingId(null);
        await loadProducts();
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
      <h1>Products</h1>
      <Link to="/products/new">New Product</Link>
      {loading && <p>Loading...</p>}
      {error && <p>{error}</p>}
      <ul>
        {products.map((p) => (
          <li key={p.id}>
            {p.name} - {p.unit_price} ({p.default_tax_rate}% GST, HSN/SAC: {p.hsn_sac_code}){' '}
            <Link to={`/products/${p.id}/edit`}>Edit</Link>{' '}
            {confirmingId === p.id ? (
              <>
                <span>Delete this product?</span>{' '}
                <button onClick={() => handleDelete(p.id)} disabled={deletingId === p.id}>
                  {deletingId === p.id ? 'Deleting...' : 'Yes, delete'}
                </button>{' '}
                <button onClick={() => setConfirmingId(null)} disabled={deletingId === p.id}>
                  Cancel
                </button>
                {deleteError[p.id] && <p>{deleteError[p.id]}</p>}
              </>
            ) : (
              <button onClick={() => setConfirmingId(p.id)}>Delete</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

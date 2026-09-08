import { useEffect, useState } from 'react';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';

export default function CustomerList() {
  const authFetch = useAuthFetch();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  return (
    <div>
      <h1>Customers</h1>
      {loading && <p>Loading...</p>}
      {error && <p>{error}</p>}
      <ul>
        {customers.map((c) => (
          <li key={c.id}>{c.name}</li>
        ))}
      </ul>

    </div>
  );
}

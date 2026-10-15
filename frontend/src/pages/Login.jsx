import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (response.status === 401) {
        setError('Incorrect username or password.');
        setPassword('');
        setSubmitting(false);
        return;
      }

      if (!response.ok) {
        setError('Something went wrong on the server. Try again in a moment.');
        setSubmitting(false);
        return;
      }

      const data = await response.json();
      login(data.access, { username });

      const redirectTo = location.state?.from?.pathname ?? '/invoices';
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError('Could not reach the server. Check your connection and try again.');
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <aside className="login-brand">
        <h1>Billing &amp; Invoice Generator</h1>
        <p className="login-tag">GST-aware invoicing with a payment ledger and aging analysis</p>
        <ul>
          <li>Tax and totals calculated on the server, line by line</li>
          <li>Sequential invoice numbers, safe under concurrent requests</li>
          <li>Append-only payment ledger with overpayment protection</li>
          <li>Aging report grouped by days overdue</li>
        </ul>
      </aside>
      <main className="login-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h2>Sign in</h2>
          <p className="login-sub">Use your administrator account.</p>
          <div className="login-field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="login-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-button" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </main>
    </div>
  );
}

import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function LoginStub() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleFakeLogin = () => {
    login('fake-token-for-testing', { username: 'testuser' });
    const destination = location.state?.from?.pathname || '/dashboard';
    navigate(destination, { replace: true });
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Login (stub)</h1>
      <p>Redirected from: {location.state?.from?.pathname || 'nowhere (direct visit)'}</p>
      <button onClick={handleFakeLogin}>Fake Login</button>
    </div>
  );
}

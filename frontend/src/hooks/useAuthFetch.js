import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { markRedirecting, isAlreadyRedirecting } from '../utils/authRedirectGuard';

export function useAuthFetch() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const authFetch = async (url, options = {}) => {
    const headers = new Headers(options.headers);

    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    if (options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401 && !isAlreadyRedirecting()) {
      markRedirecting();
      logout();
      navigate('/login', { state: { from: location, sessionExpired: true } });
    }

    return response;
  };

  return authFetch;
}

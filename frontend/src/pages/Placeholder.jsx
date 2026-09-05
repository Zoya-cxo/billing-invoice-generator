import { useLocation } from 'react-router-dom';

export function Placeholder({ label }) {
  const location = useLocation();
  return (
    <div style={{ padding: '2rem' }}>
      <h1>{label}</h1>
      <p>Path: {location.pathname}</p>
    </div>
  );
}

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/invoices', label: 'Invoices' },
  { to: '/invoices/new', label: 'New invoice' },
  { to: '/aging', label: 'Aging Report' },
  { to: '/customers', label: 'Customers' },
  { to: '/products', label: 'Products' },
];

export default function AppLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isLinkActive = (to, matched) =>
    to === '/invoices' ? matched && pathname !== '/invoices/new' : matched;

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Main">
        <span className="app-nav__brand">Billing &amp; Invoice Generator</span>
        {NAV_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isLinkActive(to, isActive)
                ? 'app-nav__link app-nav__link--active'
                : 'app-nav__link'
            }
          >
            {label}
          </NavLink>
        ))}
        <span className="app-nav__spacer" />
        <button type="button" className="app-nav__logout" onClick={handleLogout}>
          Log out
        </button>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

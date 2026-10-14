import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { fetchAllPages } from '../utils/pagination';
import { formatMoney } from '../utils/money';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'sent', label: 'Sent' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'paid', label: 'Paid' },
  { value: 'cancelled', label: 'Cancelled' },
];

const COLUMN_COUNT = 7;

export default function InvoiceList() {
  const authFetch = useAuthFetch();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    let cancelled = false;

    const loadInvoices = async () => {
      try {
        const data = await fetchAllPages(authFetch, '/api/v1/invoices/');
        if (!cancelled) {
          setInvoices(data);
        }
      } catch (err) {
        if (cancelled || err.status === 401) return;
        if (err.status) {
          setError(`Server returned ${err.status}`);
        } else if (err.truncated) {
          setError('Too many invoices to load into the list.');
        } else {
          setError('Network error: could not reach the server');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadInvoices();

    return () => {
      cancelled = true;
    };
  }, []);

  const visible =
    filter === 'all' ? invoices : invoices.filter((invoice) => invoice.status === filter);

  const emptyMessage = filter === 'all' ? 'No invoices yet.' : `No ${filter} invoices.`;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Invoices</h1>
        <div className="page-actions">
          <Link to="/invoices/new" className="btn btn--primary">
            New Invoice
          </Link>
        </div>
      </div>

      {loading && <p role="status">Loading invoices...</p>}
      {error && (
        <p role="alert" className="alert alert--error">
          {error}
        </p>
      )}

      {!loading && !error && (
        <div className="panel">
          <div className="filter-bar" role="group" aria-label="Filter by status">
            {FILTERS.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                className={
                  filter === value
                    ? 'filter-bar__btn filter-bar__btn--active'
                    : 'filter-bar__btn'
                }
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Invoice</th>
                  <th scope="col">Customer</th>
                  <th scope="col">Issued</th>
                  <th scope="col">Due</th>
                  <th scope="col" className="table__num">Total</th>
                  <th scope="col" className="table__num">Outstanding</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr>
                    <td colSpan={COLUMN_COUNT} className="table__empty">
                      {emptyMessage}
                    </td>
                  </tr>
                ) : (
                  visible.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>
                        <Link to={`/invoices/${invoice.id}`} className="table__link">
                          {invoice.invoice_number}
                        </Link>
                      </td>
                      <td>
                        <span className="truncate" title={invoice.customer_name}>
                          {invoice.customer_name}
                        </span>
                      </td>
                      <td>{invoice.issue_date}</td>
                      <td>{invoice.due_date}</td>
                      <td className="table__num">
                        <span className="money">{formatMoney(invoice.total)}</span>
                      </td>
                      <td className="table__num">
                        <span className="money">{formatMoney(invoice.outstanding)}</span>
                      </td>
                      <td>
                        <span className={`status status--${invoice.status}`}>
                          {invoice.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

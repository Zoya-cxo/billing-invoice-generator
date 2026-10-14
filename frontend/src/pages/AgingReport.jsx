import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';
import { formatMoney, toPaise, fromPaise } from '../utils/money';

const BUCKETS = [
  ['not_due', 'Not due'],
  ['days_0_30', '1-30 days overdue'],
  ['days_31_60', '31-60 days overdue'],
  ['days_61_90', '61-90 days overdue'],
  ['days_90_plus', '90+ days overdue'],
];

const sum = (rows) => fromPaise(rows.reduce((t, r) => t + toPaise(r.outstanding), 0n));

export default function AgingReport() {
  const authFetch = useAuthFetch();
  const fetchRef = useRef(authFetch);
  useEffect(() => {
    fetchRef.current = authFetch;
  });
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchRef.current(`${API_BASE_URL}/api/v1/invoices/aging/`);
        if (cancelled || res.status === 401) return;
        if (!res.ok) return setError(`Could not load the report (error ${res.status}).`);
        const body = await res.json();
        if (!cancelled) setData(body);
      } catch {
        if (!cancelled) setError('Could not reach the server.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <p className="alert alert--error" role="alert">{error}</p>;
  if (!data) return <p>Loading…</p>;

  const all = BUCKETS.flatMap(([k]) => data[k] || []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Aging Report</h1>
      </div>
      <p>Total outstanding: <span className="money">{formatMoney(sum(all))}</span> across {all.length} invoice{all.length === 1 ? '' : 's'}</p>

      {BUCKETS.map(([key, title]) => {
        const rows = data[key] || [];
        return (
          <section className="panel bucket" key={key}>
            <h2 className="panel__title bucket__title">{title}</h2>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Invoice</th>
                    <th scope="col">Customer</th>
                    <th scope="col">Due date</th>
                    <th scope="col" className="table__num">Total</th>
                    <th scope="col" className="table__num">Outstanding</th>
                    <th scope="col" className="table__num">Days overdue</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr><td colSpan={6} className="table__empty">No invoices in this bucket.</td></tr>
                  ) : rows.map((r) => (
                    <tr key={r.id}>
                      <td><Link className="table__link" to={`/invoices/${r.id}`}>{r.invoice_number}</Link></td>
                      <td><span className="truncate" title={r.customer}>{r.customer}</span></td>
                      <td>{r.due_date}</td>
                      <td className="table__num"><span className="money">{formatMoney(r.total)}</span></td>
                      <td className="table__num"><span className="money">{formatMoney(r.outstanding)}</span></td>
                      <td className="table__num">{r.days_overdue}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="bucket__subtotal">Subtotal: <span className="money">{formatMoney(sum(rows))}</span></p>
          </section>
        );
      })}
    </div>
  );
}

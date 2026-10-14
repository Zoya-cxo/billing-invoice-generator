import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';
import { formatMoney } from '../utils/money';
import PaymentForm from '../components/PaymentForm';

const ZERO = '0.00';
const METHOD_LABELS = { cash: 'Cash', upi: 'UPI', bank_transfer: 'Bank transfer', cheque: 'Cheque' };

// Contract: "Button rules for the invoice detail page".
const ACTIONS = [
  { label: 'Mark as sent', target: 'sent', variant: 'primary', show: (i) => i.status === 'draft' },
  { label: 'Mark as overdue', target: 'overdue', variant: 'secondary', show: (i) => i.status === 'sent' },
  {
    label: 'Mark as paid', target: 'paid', variant: 'primary',
    show: (i) => (i.status === 'sent' || i.status === 'overdue') && i.outstanding === ZERO,
  },
  {
    label: 'Cancel', target: 'cancelled', variant: 'danger',
    confirm: 'Cancel this invoice? This cannot be undone.',
    show: (i) => ['draft', 'sent', 'overdue'].includes(i.status),
  },
];

function toMessages(value) {
  if (value == null) return [];
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(toMessages);
  if (typeof value === 'object') {
    return Object.entries(value).flatMap(([k, v]) => {
      const msgs = toMessages(v);
      return k === 'non_field_errors' || k === 'detail' ? msgs : msgs.map((m) => `${k}: ${m}`);
    });
  }
  return [String(value)];
}

const Money = ({ v }) => <span className="money">{formatMoney(v)}</span>;

function Party({ title, name, gstin, state, address }) {
  return (
    <div className="panel party">
      <h3 className="panel__title">{title}</h3>
      <p><strong>{name}</strong></p>
      <p className="party__address">{address}</p>
      <p>GSTIN: {gstin || 'Unregistered'}</p>
      <p>State code: {state}</p>
    </div>
  );
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const authFetch = useAuthFetch();
  const fetchRef = useRef(authFetch);
  useEffect(() => {
    fetchRef.current = authFetch;
  });

  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const inFlight = useRef(false);
  const loadSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    try {
      const res = await fetchRef.current(`${API_BASE_URL}/api/v1/invoices/${id}/`);
      if (seq !== loadSeq.current || res.status === 401) return;
      if (!res.ok) {
        setLoadError(res.status === 404 ? 'Invoice not found.' : `Could not load the invoice (error ${res.status}).`);
        setLoading(false);
        return;
      }
      const data = await res.json();
      if (seq !== loadSeq.current) return;
      setInvoice(data);
      setLoadError('');
      setLoading(false);
    } catch {
      if (seq !== loadSeq.current) return;
      setLoadError('Could not reach the server. Check your connection and try again.');
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function changeStatus(action) {
    if (inFlight.current) return;
    if (action.confirm && !window.confirm(action.confirm)) return;
    inFlight.current = true;
    setBusy(true);
    setActionError('');
    try {
      const res = await fetchRef.current(`${API_BASE_URL}/api/v1/invoices/${id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ status: action.target }),
      });
      if (res.status === 401) return;
      if (!res.ok) {
        let text = '';
        if (res.status < 500) {
          try {
            text = toMessages(await res.json()).join(' ');
          } catch {
            text = '';
          }
        }
        setActionError(text || `The server could not change the status (error ${res.status}).`);
        return;
      }
      await load();
    } catch {
      setActionError('Could not reach the server. The status was not changed.');
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  if (loading) return <p>Loading invoice…</p>;
  if (!invoice) {
    return (
      <div>
        <p className="alert alert--error" role="alert">{loadError}</p>
        <Link to="/invoices">Back to invoices</Link>
      </div>
    );
  }

  const actions = ACTIONS.filter((a) => a.show(invoice));
  const canPay = (invoice.status === 'sent' || invoice.status === 'overdue') && invoice.outstanding !== ZERO;
  const items = invoice.items || [];
  const payments = invoice.payments || [];

  return (
    <div>
      <p><Link to="/invoices">← Back to invoices</Link></p>

      <div className="page-header">
        <h1 className="page-title">{invoice.invoice_number}</h1>
        <span className={'status status--' + invoice.status}>{invoice.status}</span>
      </div>
      <p>Issue date: {invoice.issue_date} · Due date: {invoice.due_date}</p>

      {loadError && <p className="alert alert--error" role="alert">{loadError}</p>}

      {actions.length > 0 && (
        <div className="page-actions">
          {actions.map((a) => (
            <button key={a.target} type="button" className={'btn btn--' + a.variant}
              disabled={busy} onClick={() => changeStatus(a)}>
              {a.label}
            </button>
          ))}
        </div>
      )}
      {actionError && <p className="alert alert--error" role="alert">{actionError}</p>}

      <div className="parties">
        <Party title="Seller" name={invoice.seller_name} gstin={invoice.seller_gstin}
          state={invoice.seller_state} address={invoice.seller_address} />
        <Party title="Bill to" name={invoice.customer_name} gstin={invoice.customer_gstin}
          state={invoice.customer_state} address={invoice.customer_billing_address} />
      </div>

      <section className="panel">
        <h2 className="panel__title">Items</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Product</th>
                <th scope="col">HSN/SAC</th>
                <th scope="col" className="table__num">Qty</th>
                <th scope="col" className="table__num">Unit price</th>
                <th scope="col" className="table__num">Discount</th>
                <th scope="col" className="table__num">Tax rate</th>
                <th scope="col" className="table__num">Line total</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id}>
                  <td>{it.product_name}</td>
                  <td>{it.hsn_sac_code}</td>
                  <td className="table__num">{it.quantity}</td>
                  <td className="table__num"><Money v={it.unit_price} /></td>
                  <td className="table__num"><Money v={it.discount} /></td>
                  <td className="table__num">{it.tax_rate}%</td>
                  <td className="table__num"><Money v={it.line_total} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2 className="panel__title">Totals</h2>
        <dl className="summary">
          <div className="summary__row"><dt>Subtotal</dt><dd><Money v={invoice.subtotal} /></dd></div>
          <div className="summary__row"><dt>Tax</dt><dd><Money v={invoice.tax_total} /></dd></div>
          <div className="summary__row summary__row--total"><dt>Total</dt><dd><Money v={invoice.total} /></dd></div>
          <div className="summary__row"><dt>Paid</dt><dd><Money v={invoice.paid} /></dd></div>
          <div className="summary__row summary__row--total"><dt>Outstanding</dt><dd><Money v={invoice.outstanding} /></dd></div>
        </dl>
      </section>

      <section className="panel">
        <h2 className="panel__title">Payments</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Method</th>
                <th scope="col" className="table__num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {payments.length === 0 ? (
                <tr><td colSpan={3} className="table__empty">No payments recorded.</td></tr>
              ) : payments.map((p) => (
                <tr key={p.id}>
                  <td>{p.payment_date}</td>
                  <td>{METHOD_LABELS[p.method] || p.method}</td>
                  <td className="table__num"><Money v={p.amount} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {canPay && <PaymentForm invoice={invoice} onRecorded={load} />}
    </div>
  );
}

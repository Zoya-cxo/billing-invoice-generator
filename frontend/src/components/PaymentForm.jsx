import { useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from '../config';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { formatMoney, toPaise } from '../utils/money';

const METHODS = [
  ['cash', 'Cash'],
  ['upi', 'UPI'],
  ['bank_transfer', 'Bank transfer'],
  ['cheque', 'Cheque'],
];

function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

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

export default function PaymentForm({ invoice, onRecorded }) {
  const authFetch = useAuthFetch();
  const fetchRef = useRef(authFetch);
  useEffect(() => {
    fetchRef.current = authFetch;
  });

  const [amount, setAmount] = useState(invoice.outstanding);
  const [date, setDate] = useState(today());
  const [method, setMethod] = useState('cash');
  // One key per form; reused on retry so a repeated submit cannot double-pay.
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const inFlight = useRef(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (inFlight.current) return;
    setError('');
    setSuccess('');

    const paise = toPaise(amount);
    if (paise <= 0n) return setError('Amount must be greater than zero.');
    if (paise > toPaise(invoice.outstanding)) {
      return setError(`Amount cannot exceed the outstanding ${formatMoney(invoice.outstanding)}.`);
    }

    inFlight.current = true;
    setBusy(true);
    try {
      const res = await fetchRef.current(`${API_BASE_URL}/api/v1/payments/`, {
        method: 'POST',
        body: JSON.stringify({
          invoice: invoice.id,
          amount,
          payment_date: date,
          method,
          idempotency_key: key,
        }),
      });
      if (res.status === 401) return;
      if (res.ok) {
        setSuccess(`Payment of ${formatMoney(amount)} recorded.`);
        setKey(crypto.randomUUID());
        setAmount('');
        await onRecorded();
        return;
      }
      let text = '';
      if (res.status < 500) {
        try {
          text = toMessages(await res.json()).join(' ');
        } catch {
          text = '';
        }
      }
      setError(text || `The server could not record the payment (error ${res.status}). Check the invoice before retrying.`);
    } catch {
      setError('Could not reach the server. The payment may not have been saved; check the invoice before retrying.');
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={handleSubmit}>
      <h3 className="panel__title">Record payment</h3>
      <p>Outstanding: <span className="money">{formatMoney(invoice.outstanding)}</span></p>

      <div className="field">
        <label className="field__label" htmlFor="pay-amount">Amount</label>
        <input id="pay-amount" className="input" type="number" step="0.01" min="0.01"
          value={amount} onChange={(e) => setAmount(e.target.value)} required />
      </div>
      <div className="field">
        <label className="field__label" htmlFor="pay-date">Payment date</label>
        <input id="pay-date" className="input" type="date"
          value={date} onChange={(e) => setDate(e.target.value)} required />
      </div>
      <div className="field">
        <label className="field__label" htmlFor="pay-method">Method</label>
        <select id="pay-method" className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
          {METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {error && <p className="alert alert--error" role="alert">{error}</p>}
      {success && <p className="alert alert--success">{success}</p>}

      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Recording…' : 'Record payment'}
        </button>
      </div>
    </form>
  );
}

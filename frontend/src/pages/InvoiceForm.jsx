import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';

const MAX_PAGES = 50;

let rowKeyCounter = 0;

const makeRow = () => {
  rowKeyCounter += 1;
  return { key: rowKeyCounter, product: '', quantity: '1', discount: '0' };
};

const INITIAL_ROW = { key: 0, product: '', quantity: '1', discount: '0' };

const todayLocal = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const messagesOf = (value) => {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.filter((v) => typeof v === 'string').join(' ');
  return '';
};

const isPlainObject = (entry) =>
  Boolean(entry) && typeof entry === 'object' && !Array.isArray(entry);

const splitItemErrors = (value) => {
  if (Array.isArray(value)) {
    const rows = value.map((entry) => (isPlainObject(entry) ? entry : {}));
    return { general: messagesOf(value), rows };
  }
  if (isPlainObject(value)) {
    const byIndex = {};
    let general = '';
    let highest = -1;
    Object.entries(value).forEach(([key, entry]) => {
      const index = Number(key);
      if (Number.isInteger(index) && index >= 0 && isPlainObject(entry)) {
        byIndex[index] = entry;
        highest = Math.max(highest, index);
      } else {
        general = `${general} ${messagesOf(entry) || 'The server rejected the line items.'}`.trim();
      }
    });
    const rows = Array.from({ length: highest + 1 }, (_, i) => byIndex[i] || {});
    return { general, rows };
  }
  return { general: messagesOf(value), rows: [] };
};

const dedupeById = (list) => [...new Map(list.map((item) => [item.id, item])).values()];

const fetchAllPages = async (authFetch, path) => {
  const collected = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const response = await authFetch(`${API_BASE_URL}${path}?page=${page}`);
    if (!response.ok) {
      throw Object.assign(new Error('Request failed'), { status: response.status });
    }
    const data = await response.json();
    if (Array.isArray(data)) {
      return data;
    }
    collected.push(...data.results);
    if (!data.next) {
      return dedupeById(collected);
    }
  }
  throw Object.assign(new Error('Too many pages'), { truncated: true });
};

const EMPTY_HEADER = { customer: '', issue_date: '', due_date: '' };

export default function InvoiceForm() {
  const authFetch = useAuthFetch();
  const submittingRef = useRef(false);

  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [refLoading, setRefLoading] = useState(true);
  const [refError, setRefError] = useState(null);

  const [form, setForm] = useState({ ...EMPTY_HEADER, issue_date: todayLocal() });
  const [rows, setRows] = useState([INITIAL_ROW]);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [itemsError, setItemsError] = useState('');
  const [rowErrors, setRowErrors] = useState([]);
  const [topError, setTopError] = useState('');
  const [created, setCreated] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const loadReferenceData = async () => {
      try {
        const [customerList, productList] = await Promise.all([
          fetchAllPages(authFetch, '/api/v1/customers/'),
          fetchAllPages(authFetch, '/api/v1/products/'),
        ]);
        if (!cancelled) {
          setCustomers(customerList);
          setProducts(productList);
          setRefLoading(false);
        }
      } catch (err) {
        if (cancelled || err.status === 401) return;
        if (err.status) {
          setRefError(`Could not load customers and products (status ${err.status})`);
        } else if (err.truncated) {
          setRefError('Too many customers or products to load into a dropdown.');
        } else {
          setRefError('Network error: could not reach the server');
        }
        setRefLoading(false);
      }
    };

    loadReferenceData();

    return () => {
      cancelled = true;
    };
  }, []);

  const productMap = new Map(products.map((p) => [String(p.id), p]));

  const handleHeaderChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const updateRow = (key, field) => (e) => {
    const { value } = e.target;
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, [field]: value } : row)));
  };

  const addRow = () => {
    setRows((prev) => [...prev, makeRow()]);
  };

  const removeRow = (key) => {
    setRows((prev) => (prev.length === 1 ? prev : prev.filter((row) => row.key !== key)));
  };

  const validate = () => {
    const errs = {};
    if (!form.customer) errs.customer = 'Select a customer.';
    if (!form.issue_date) errs.issue_date = 'Issue date is required.';
    if (!form.due_date) {
      errs.due_date = 'Due date is required.';
    } else if (form.issue_date && form.due_date < form.issue_date) {
      errs.due_date = 'Due date cannot be before the issue date.';
    }

    const rowErrs = rows.map((row) => {
      const e = {};
      const product = productMap.get(row.product);
      if (!row.product) e.product = 'Select a product.';
      if (!(Number(row.quantity) > 0)) e.quantity = 'Quantity must be greater than 0.';
      if (row.discount !== '' && Number(row.discount) < 0) e.discount = 'Discount cannot be negative.';
      if (product && !e.quantity && !e.discount) {
        const lineCents = Math.round(Number(row.quantity) * Number(product.unit_price) * 100);
        const discountCents = Math.round(Number(row.discount || 0) * 100);
        if (discountCents > lineCents) e.discount = 'Discount cannot exceed the line amount.';
      }
      return e;
    });

    const ok = Object.keys(errs).length === 0 && rowErrs.every((e) => Object.keys(e).length === 0);
    return { errs, rowErrs, ok };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submittingRef.current) return;

    setTopError('');
    setFieldErrors({});
    setItemsError('');
    setRowErrors([]);

    const { errs, rowErrs, ok } = validate();
    if (!ok) {
      setFieldErrors(errs);
      setRowErrors(rowErrs);
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload = {
      customer: form.customer,
      issue_date: form.issue_date,
      due_date: form.due_date,
      items: rows.map((row) => ({
        product: row.product,
        quantity: row.quantity,
        discount: row.discount === '' ? '0' : row.discount,
      })),
    };

    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/invoices/`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (response.status === 401) return;

      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }

      if (response.ok) {
        if (data) {
          setCreated(data);
        } else {
          setTopError('The invoice was created but the response could not be read. Verify in the invoice list before retrying.');
        }
        return;
      }

      if (response.status === 400 && data && typeof data === 'object') {
        const { items, ...rest } = data;
        const itemSplit = splitItemErrors(items);
        setFieldErrors(rest);
        setItemsError(itemSplit.general);
        setRowErrors(itemSplit.rows);
        const anyMessage =
          Object.values(rest).some((v) => messagesOf(v)) ||
          itemSplit.general ||
          itemSplit.rows.some((r) => Object.keys(r).length > 0);
        if (!anyMessage) setTopError('The server rejected the request.');
        return;
      }

      setTopError(messagesOf(data?.detail) || `Server returned ${response.status}`);
    } catch {
      setTopError('Network error: could not confirm whether the invoice was saved. Verify in the invoice list before retrying.');
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const handleCreateAnother = () => {
    setCreated(null);
    setForm({ ...EMPTY_HEADER, issue_date: todayLocal() });
    setRows([makeRow()]);
    setFieldErrors({});
    setItemsError('');
    setRowErrors([]);
    setTopError('');
  };

  if (refLoading) {
    return <p>Loading...</p>;
  }

  if (refError) {
    return <p>{refError}</p>;
  }

  if (created) {
    return (
      <div>
        <h1>Invoice Created</h1>
        <p>Invoice number: {created.invoice_number}</p>
        <p>Status: {created.status}</p>
        <p>Subtotal: {created.subtotal}</p>
        <p>Tax total: {created.tax_total}</p>
        <p>Total: {created.total}</p>
        <Link to={`/invoices/${created.id}`}>View invoice</Link>{' '}
        <button onClick={handleCreateAnother}>Create another</button>
      </div>
    );
  }

  if (customers.length === 0 || products.length === 0) {
    return (
      <div>
        <h1>New Invoice</h1>
        <p>
          An invoice needs at least one customer and one product.{' '}
          {customers.length === 0 && <Link to="/customers/new">Add a customer</Link>}{' '}
          {products.length === 0 && <Link to="/products/new">Add a product</Link>}
        </p>
      </div>
    );
  }

  const knownFields = ['customer', 'issue_date', 'due_date'];
  const extraErrors = Object.entries(fieldErrors).filter(([key]) => !knownFields.includes(key));

  return (
    <div>
      <h1>New Invoice</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="customer">Customer</label>
          <select id="customer" value={form.customer} onChange={handleHeaderChange('customer')} required>
            <option value="">Select a customer</option>
            {customers.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name}
              </option>
            ))}
          </select>
          {fieldErrors.customer && <p>{messagesOf(fieldErrors.customer)}</p>}
        </div>

        <div>
          <label htmlFor="issue_date">Issue Date</label>
          <input
            id="issue_date"
            type="date"
            value={form.issue_date}
            onChange={handleHeaderChange('issue_date')}
            required
          />
          {fieldErrors.issue_date && <p>{messagesOf(fieldErrors.issue_date)}</p>}
        </div>

        <div>
          <label htmlFor="due_date">Due Date</label>
          <input
            id="due_date"
            type="date"
            value={form.due_date}
            onChange={handleHeaderChange('due_date')}
            required
          />
          {fieldErrors.due_date && <p>{messagesOf(fieldErrors.due_date)}</p>}
        </div>

        <h2>Line Items</h2>
        {rows.map((row, index) => {
          const product = productMap.get(row.product);
          const errs = rowErrors[index] || {};
          return (
            <div key={row.key}>
              <div>
                <label htmlFor={`product-${row.key}`}>Product</label>
                <select
                  id={`product-${row.key}`}
                  value={row.product}
                  onChange={updateRow(row.key, 'product')}
                  required
                >
                  <option value="">Select a product</option>
                  {products.map((p) => (
                    <option key={p.id} value={String(p.id)}>
                      {p.name} ({p.unit_price})
                    </option>
                  ))}
                </select>
                {errs.product && <p>{messagesOf(errs.product)}</p>}
              </div>

              {product && (
                <p>
                  Unit price {product.unit_price}, GST {product.default_tax_rate}%, HSN/SAC{' '}
                  {product.hsn_sac_code}. The server captures these when the invoice is created.
                </p>
              )}

              <div>
                <label htmlFor={`quantity-${row.key}`}>Quantity</label>
                <input
                  id={`quantity-${row.key}`}
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={row.quantity}
                  onChange={updateRow(row.key, 'quantity')}
                  required
                />
                {errs.quantity && <p>{messagesOf(errs.quantity)}</p>}
              </div>

              <div>
                <label htmlFor={`discount-${row.key}`}>Discount (amount, not %)</label>
                <input
                  id={`discount-${row.key}`}
                  type="number"
                  step="0.01"
                  min="0"
                  value={row.discount}
                  onChange={updateRow(row.key, 'discount')}
                />
                {errs.discount && <p>{messagesOf(errs.discount)}</p>}
              </div>

              <button type="button" onClick={() => removeRow(row.key)} disabled={rows.length === 1}>
                Remove line
              </button>
            </div>
          );
        })}

        {itemsError && <p>{itemsError}</p>}

        <button type="button" onClick={addRow}>
          Add line
        </button>

        {extraErrors.map(([key, value]) => (
          <p key={key}>
            {key === 'non_field_errors' ? '' : `${key}: `}
            {messagesOf(value)}
          </p>
        ))}
        {topError && <p>{topError}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : 'Create Invoice'}
        </button>
      </form>
    </div>
  );
}
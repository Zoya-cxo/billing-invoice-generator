import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';
import { GST_STATE_CHOICES } from '../constants/gstStates';

const EMPTY_FORM = {
  name: '',
  email: '',
  phone: '',
  gstin: '',
  state: '',
  billing_address: '',
};

export default function CustomerForm() {
  const { id } = useParams();
  const isEditMode = Boolean(id);
  const authFetch = useAuthFetch();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(isEditMode);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    if (!isEditMode) return;

    let cancelled = false;

    const loadCustomer = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const response = await authFetch(`${API_BASE_URL}/api/v1/customers/${id}/`);
        if (!response.ok) {
          if (response.status !== 401) {
            setLoadError(`Could not load customer (status ${response.status})`);
          }
          return;
        }
        const data = await response.json();
        if (!cancelled) {
          setForm({
            name: data.name ?? '',
            email: data.email ?? '',
            phone: data.phone ?? '',
            gstin: data.gstin ?? '',
            state: data.state ?? '',
            billing_address: data.billing_address ?? '',
          });
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError('Network error: could not reach the server');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadCustomer();

    return () => {
      cancelled = true;
    };
  }, [id, isEditMode]);

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFieldErrors({});

    const url = isEditMode
      ? `${API_BASE_URL}/api/v1/customers/${id}/`
      : `${API_BASE_URL}/api/v1/customers/`;
    const method = isEditMode ? 'PATCH' : 'POST';

    try {
      const response = await authFetch(url, {
        method,
        body: JSON.stringify(form),
      });

      if (response.ok) {
        navigate('/customers');
        return;
      }

      if (response.status === 400) {
        const errors = await response.json();
        setFieldErrors(errors);
      } else if (response.status !== 401) {
        setFieldErrors({ non_field_errors: [`Server returned ${response.status}`] });
      }
    } catch (err) {
      setFieldErrors({ non_field_errors: ['Network error: could not reach the server'] });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <p>Loading...</p>;
  }

  if (loadError) {
    return <p>{loadError}</p>;
  }

  return (
    <div>
      <h1>{isEditMode ? 'Edit Customer' : 'New Customer'}</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name">Name</label>
          <input id="name" value={form.name} onChange={handleChange('name')} required />
          {fieldErrors.name && <p>{fieldErrors.name.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={form.email} onChange={handleChange('email')} required />
          {fieldErrors.email && <p>{fieldErrors.email.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="phone">Phone</label>
          <input id="phone" value={form.phone} onChange={handleChange('phone')} required />
          {fieldErrors.phone && <p>{fieldErrors.phone.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="gstin">GSTIN (optional)</label>
          <input id="gstin" value={form.gstin} onChange={handleChange('gstin')} />
          {fieldErrors.gstin && <p>{fieldErrors.gstin.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="state">State</label>
          <select id="state" value={form.state} onChange={handleChange('state')} required>
            <option value="">Select a state</option>
            {GST_STATE_CHOICES.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
          {fieldErrors.state && <p>{fieldErrors.state.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="billing_address">Billing Address</label>
          <textarea
            id="billing_address"
            value={form.billing_address}
            onChange={handleChange('billing_address')}
            required
          />
          {fieldErrors.billing_address && <p>{fieldErrors.billing_address.join(' ')}</p>}
        </div>

        {fieldErrors.non_field_errors && <p>{fieldErrors.non_field_errors.join(' ')}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : 'Save'}
        </button>
      </form>
    </div>
  );
}

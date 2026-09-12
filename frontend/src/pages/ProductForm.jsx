import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthFetch } from '../hooks/useAuthFetch';
import { API_BASE_URL } from '../config';

const EMPTY_FORM = {
  name: '',
  unit_price: '',
  default_tax_rate: '',
  hsn_sac_code: '',
};

export default function ProductForm() {
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

    const loadProduct = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const response = await authFetch(`${API_BASE_URL}/api/v1/products/${id}/`);
        if (!response.ok) {
          if (response.status !== 401) {
            setLoadError(`Could not load product (status ${response.status})`);
          }
          return;
        }
        const data = await response.json();
        if (!cancelled) {
          setForm({
            name: data.name ?? '',
            unit_price: data.unit_price ?? '',
            default_tax_rate: data.default_tax_rate ?? '',
            hsn_sac_code: data.hsn_sac_code ?? '',
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

    loadProduct();

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
      ? `${API_BASE_URL}/api/v1/products/${id}/`
      : `${API_BASE_URL}/api/v1/products/`;
    const method = isEditMode ? 'PATCH' : 'POST';

    try {
      const response = await authFetch(url, {
        method,
        body: JSON.stringify(form),
      });

      if (response.ok) {
        navigate('/products');
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
      <h1>{isEditMode ? 'Edit Product' : 'New Product'}</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name">Name</label>
          <input id="name" value={form.name} onChange={handleChange('name')} required />
          {fieldErrors.name && <p>{fieldErrors.name.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="unit_price">Unit Price</label>
          <input
            id="unit_price"
            type="number"
            step="0.01"
            value={form.unit_price}
            onChange={handleChange('unit_price')}
            required
          />
          {fieldErrors.unit_price && <p>{fieldErrors.unit_price.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="default_tax_rate">Default Tax Rate (%)</label>
          <input
            id="default_tax_rate"
            type="number"
            step="0.01"
            value={form.default_tax_rate}
            onChange={handleChange('default_tax_rate')}
            required
          />
          {fieldErrors.default_tax_rate && <p>{fieldErrors.default_tax_rate.join(' ')}</p>}
        </div>

        <div>
          <label htmlFor="hsn_sac_code">HSN/SAC Code</label>
          <input
            id="hsn_sac_code"
            value={form.hsn_sac_code}
            onChange={handleChange('hsn_sac_code')}
            required
          />
          {fieldErrors.hsn_sac_code && <p>{fieldErrors.hsn_sac_code.join(' ')}</p>}
        </div>

        {fieldErrors.non_field_errors && <p>{fieldErrors.non_field_errors.join(' ')}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : 'Save'}
        </button>
      </form>
    </div>
  );
}

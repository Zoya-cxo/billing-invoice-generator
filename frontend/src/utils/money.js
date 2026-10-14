// Money values are strings from the API. Never Number() them.
export function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '';
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value).trim());
  if (!m) return String(value);
  const [, sign, int, frac = ''] = m;
  const head = int.replace(/^0+(?=\d)/, '');
  const last3 = head.slice(-3);
  const rest = head.slice(0, -3);
  const grouped = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' : '';
  return `${sign}₹${grouped}${last3}.${(frac + '00').slice(0, 2)}`;
}

// Exact integer arithmetic on money strings (paise as BigInt).
export function toPaise(value) {
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value).trim());
  if (!m) return 0n;
  const v = BigInt(m[2]) * 100n + BigInt(((m[3] || '') + '00').slice(0, 2));
  return m[1] ? -v : v;
}

export function fromPaise(p) {
  const neg = p < 0n;
  const s = String(neg ? -p : p).padStart(3, '0');
  return `${neg ? '-' : ''}${s.slice(0, -2)}.${s.slice(-2)}`;
}

export default formatMoney;

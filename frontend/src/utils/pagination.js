import { API_BASE_URL } from '../config';

export const MAX_PAGES = 50;

export function dedupeById(list) {
  return [...new Map(list.map((item) => [item.id, item])).values()];
}

export async function fetchAllPages(authFetch, path) {
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
}

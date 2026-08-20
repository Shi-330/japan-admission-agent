const API = import.meta.env.VITE_API_URL || '';

/** Shared fetch wrapper: auth header, JSON serialize/deserialize, error parsing. */
export async function apiCall(path, token, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const err = new Error(detail.detail || `${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

/** Multipart upload wrapper (file + optional form fields), no JSON Content-Type. */
export async function apiUpload(path, token, file, extraFields = {}) {
  const formData = new FormData();
  formData.append('file', file);
  for (const [k, v] of Object.entries(extraFields)) {
    formData.append(k, v);
  }
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { method: 'POST', headers, body: formData });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const err = new Error(detail.detail || `${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

const api = axios.create({ baseURL: BASE_URL });

function getTokens() {
  try {
    return JSON.parse(localStorage.getItem('gullak_tokens') || 'null');
  } catch {
    return null;
  }
}

function setTokens(tokens) {
  if (tokens) localStorage.setItem('gullak_tokens', JSON.stringify(tokens));
  else localStorage.removeItem('gullak_tokens');
}

api.interceptors.request.use((config) => {
  const tokens = getTokens();
  if (tokens?.access) {
    config.headers.Authorization = `Bearer ${tokens.access}`;
  }
  return config;
});

let refreshPromise = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      const tokens = getTokens();
      if (!tokens?.refresh) {
        setTokens(null);
        window.dispatchEvent(new Event('gullak:logout'));
        return Promise.reject(error);
      }
      original._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${BASE_URL}/auth/login/refresh/`, { refresh: tokens.refresh })
            .finally(() => {
              refreshPromise = null;
            });
        }
        const { data } = await refreshPromise;
        setTokens({ ...tokens, access: data.access });
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (refreshErr) {
        setTokens(null);
        window.dispatchEvent(new Event('gullak:logout'));
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  }
);

export { getTokens, setTokens };
export default api;

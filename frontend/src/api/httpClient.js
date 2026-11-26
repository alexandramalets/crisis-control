import axios from 'axios';

const TOKEN_KEY = 'ca_access_token';

export const SESSION_ENDED_EVENT = 'ca:session-ended';

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
  withCredentials: true,
});

export function getAccessToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token) {
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

httpClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (config.headers && typeof config.headers.delete === 'function') {
      config.headers.delete('Content-Type');
    } else if (config.headers) {
      delete config.headers['Content-Type'];
      delete config.headers['content-type'];
    }
  }
  return config;
});

let refreshPromise = null;

httpClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {};
    const url = String(original.url || '');
    if (error.response?.status !== 401 || original._retry || url.includes('/auth/')) {
      return Promise.reject(error);
    }
    original._retry = true;
    try {
      if (!refreshPromise) {
        refreshPromise = httpClient.post('/auth/refresh').finally(() => {
          refreshPromise = null;
        });
      }
      const { data } = await refreshPromise;
      setAccessToken(data.access_token);
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${data.access_token}`;
      return httpClient(original);
    } catch {
      setAccessToken(null);
      window.dispatchEvent(new Event(SESSION_ENDED_EVENT));
      return Promise.reject(error);
    }
  },
);

export function errorMessage(error) {
  const payload = error?.response?.data?.error;
  if (payload?.message) {
    const details = payload.details;
    if (Array.isArray(details) && details.length) {
      const bits = details
        .map((item) => (typeof item === 'string' ? item : item?.message || item?.msg))
        .filter(Boolean);
      if (bits.length) {
        return `${payload.message}: ${bits.join('; ')}`;
      }
    }
    return payload.message;
  }
  if (Array.isArray(error?.response?.data?.detail)) {
    const bits = error.response.data.detail
      .map((item) => item?.msg || item?.message)
      .filter(Boolean);
    if (bits.length) {
      return bits.join('; ');
    }
  }
  if (!error?.response) {
    return 'Сервер недоступен. Проверьте соединение и повторите попытку.';
  }
  if (error.response.status === 413) {
    return 'Файл слишком большой. Допустим размер до 10 МБ.';
  }
  if (error.response.status >= 500) {
    return 'Не удалось выполнить операцию. Повторите попытку позже. Если ошибка сохраняется, обратитесь к администратору.';
  }
  return 'Не удалось выполнить запрос. Проверьте введённые данные и повторите попытку.';
}

export function errorDetails(error) {
  return error?.response?.data?.error?.details ?? null;
}

export default httpClient;

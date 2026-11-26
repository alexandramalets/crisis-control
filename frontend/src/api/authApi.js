import httpClient, { setAccessToken } from './httpClient.js';

export async function login(loginName, password) {
  const { data } = await httpClient.post('/auth/login', { login: loginName, password });
  setAccessToken(data.access_token);
  return data;
}

export async function logout() {
  try {
    await httpClient.post('/auth/logout');
  } finally {
    setAccessToken(null);
  }
}

export async function fetchMe() {
  const { data } = await httpClient.get('/auth/me');
  return data;
}

export async function changePassword(currentPassword, newPassword) {
  await httpClient.put('/auth/me/password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

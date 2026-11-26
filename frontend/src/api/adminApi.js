import httpClient from './httpClient.js';

export async function fetchAdminOverview() {
  const { data } = await httpClient.get('/admin/overview');
  return data;
}

export async function fetchAdminUsers({ q, limit = 50, offset = 0 } = {}) {
  const { data } = await httpClient.get('/admin/users', { params: { q, limit, offset } });
  return data;
}

export async function fetchAdminUser(userId) {
  const { data } = await httpClient.get(`/admin/users/${userId}`);
  return data;
}

export async function createAdminUser(payload) {
  const { data } = await httpClient.post('/admin/users', payload);
  return data;
}

export async function updateAdminUser(userId, payload) {
  const { data } = await httpClient.patch(`/admin/users/${userId}`, payload);
  return data;
}

export async function resetAdminUserPassword(userId, password) {
  await httpClient.post(`/admin/users/${userId}/password`, { password });
}

export async function unlockAdminUser(userId) {
  const { data } = await httpClient.post(`/admin/users/${userId}/unlock`);
  return data;
}

export async function fetchOrganizationMembers(organizationId) {
  const { data } = await httpClient.get(`/admin/organizations/${organizationId}/members`);
  return data;
}

export async function grantOrganizationAccess(organizationId, userId, accessLevel = 'view') {
  await httpClient.put(`/admin/organizations/${organizationId}/access/${userId}`, null, {
    params: { access_level: accessLevel },
  });
}

export async function revokeOrganizationAccess(organizationId, userId) {
  await httpClient.delete(`/admin/organizations/${organizationId}/access/${userId}`);
}

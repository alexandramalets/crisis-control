import httpClient from './httpClient.js';

export async function fetchOrganizations() {
  const { data } = await httpClient.get('/organizations', { params: { limit: 100 } });
  return data;
}

export async function fetchOrganization(organizationId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}`);
  return data;
}

export async function createOrganization(payload) {
  const { data } = await httpClient.post('/organizations', payload);
  return data;
}

export async function updateOrganization(organizationId, payload) {
  const { data } = await httpClient.patch(`/organizations/${organizationId}`, payload);
  return data;
}

export async function fetchOrganizationMembers(organizationId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/members`);
  return data;
}

export async function assignOrganizationMember(organizationId, userId, accessLevel, login) {
  const payload = {
    user_id: userId || undefined,
    login: login || undefined,
    access_level: accessLevel,
  };
  if (userId) {
    const { data } = await httpClient.put(`/organizations/${organizationId}/members/${userId}`, payload);
    return data;
  }
  const { data } = await httpClient.post(`/organizations/${organizationId}/members`, payload);
  return data;
}

export async function createOrganizationEmployee(organizationId, payload) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/employees`, payload);
  return data;
}

export async function revokeOrganizationMember(organizationId, userId) {
  await httpClient.delete(`/organizations/${organizationId}/members/${userId}`);
}

export async function clearOrganizationWorkspace(organizationId) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/workspace/clear`);
  return data;
}

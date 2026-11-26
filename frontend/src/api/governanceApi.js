import httpClient from './httpClient.js';

export async function fetchFindings(organizationId, runId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/findings`, {
    params: { run_id: runId },
  });
  return data;
}

export async function fetchAlerts(organizationId, runId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/alerts`, {
    params: { run_id: runId },
  });
  return data;
}

export async function fetchRecommendations(organizationId, runId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/recommendations`, {
    params: { run_id: runId },
  });
  return data;
}

export async function updateRecommendation(id, payload) {
  const { data } = await httpClient.patch(`/recommendations/${id}`, payload);
  return data;
}

export async function convertRecommendation(id, payload = {}) {
  const { data } = await httpClient.post(`/recommendations/${id}/convert`, payload);
  return data;
}

export async function fetchMeasures(organizationId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/measures`);
  return data;
}

export async function createMeasure(organizationId, payload) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/measures`, payload);
  return data;
}

export async function updateMeasure(id, payload) {
  const { data } = await httpClient.patch(`/measures/${id}`, payload);
  return data;
}

export async function deleteMeasure(id) {
  await httpClient.delete(`/measures/${id}`);
}

export async function fetchMeasureEvents(id) {
  const { data } = await httpClient.get(`/measures/${id}/events`);
  return data;
}

export async function fetchProfile(organizationId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/profile`);
  return data;
}

export async function upsertTarget(organizationId, payload) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/targets`, payload);
  return data;
}

export async function upsertThreshold(organizationId, payload) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/thresholds`, payload);
  return data;
}

export async function importProfileFile(organizationId, file) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await httpClient.post(`/organizations/${organizationId}/profile/import`, form, { timeout: 30000 });
  return data;
}

export async function fetchScenarios(organizationId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/scenarios`);
  return data;
}

export async function createScenario(organizationId, payload) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/scenarios`, payload, { timeout: 120000 });
  return data;
}

export async function compareRuns(runId, otherId) {
  const { data } = await httpClient.get(`/analyses/${runId}/compare`, { params: { other_id: otherId } });
  return data;
}

export async function fetchOrgAudit(organizationId) {
  const { data } = await httpClient.get(`/organizations/${organizationId}/audit`);
  return data;
}

import httpClient from './httpClient.js';

export async function fetchDatasets({ organizationId, limit = 50 } = {}) {
  const { data } = await httpClient.get('/datasets', {
    params: { organization_id: organizationId, limit },
  });
  return data;
}

export async function fetchDataset(datasetId) {
  const { data } = await httpClient.get(`/datasets/${datasetId}`);
  return data;
}

export async function fetchDatasetSchema(datasetId) {
  const { data } = await httpClient.get(`/datasets/${datasetId}/schema`);
  return data;
}

export async function fetchDatasetQuality(datasetId) {
  const { data } = await httpClient.get(`/datasets/${datasetId}/quality`);
  return data;
}

export async function fetchDatasetValues(datasetId, params = {}) {
  const { data } = await httpClient.get(`/datasets/${datasetId}/values`, {
    params: { limit: 10000, ...params },
  });
  return data;
}

export async function previewDataset(file) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await httpClient.post('/datasets/preview', form, { timeout: 30000 });
  return data;
}

export async function validatePreview(payload) {
  const { data } = await httpClient.post('/datasets/preview/validate', payload);
  return data;
}

export async function importDataset(organizationId, payload) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/datasets/import`, payload);
  return data;
}

export async function fetchDemoInfo() {
  const { data } = await httpClient.get('/datasets/demo');
  return data;
}

export async function importDemoDataset(organizationId) {
  const { data } = await httpClient.post(`/organizations/${organizationId}/datasets/demo`, null, { timeout: 60000 });
  return data;
}

export async function deleteDataset(datasetId) {
  await httpClient.delete(`/datasets/${datasetId}`);
}

export async function downloadTemplate(format = 'csv') {
  const response = await httpClient.get('/datasets/template', {
    params: { format },
    responseType: 'blob',
  });
  return response;
}

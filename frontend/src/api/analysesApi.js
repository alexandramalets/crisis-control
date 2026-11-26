import httpClient from './httpClient.js';

export async function fetchAnalyses({ datasetId, organizationId, status, limit = 50 } = {}) {
  const { data } = await httpClient.get('/analyses', {
    params: { dataset_id: datasetId, organization_id: organizationId, status, limit },
  });
  return data;
}

export async function fetchAnalysis(runId) {
  const { data } = await httpClient.get(`/analyses/${runId}`);
  return data;
}

export async function fetchAnalysisResults(runId) {
  const { data } = await httpClient.get(`/analyses/${runId}/results`, { timeout: 60000 });
  return data;
}

export async function startAnalysis(payload) {
  const { data } = await httpClient.post('/analyses', payload, { timeout: 120000 });
  return data;
}

export async function deleteAnalysis(runId) {
  await httpClient.delete(`/analyses/${runId}`);
}

export async function createAnalysisPdf(runId) {
  const { data } = await httpClient.post(`/analyses/${runId}/report`, null, { timeout: 60000 });
  return data;
}

export async function downloadReportContent(reportId) {
  const response = await httpClient.get(`/reports/${reportId}/content`, { responseType: 'blob', timeout: 60000 });
  return response;
}

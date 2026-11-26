import httpClient from './httpClient.js';

export async function fetchDashboard({ months, organizationId, datasetId, signal } = {}) {
  const { data } = await httpClient.get('/dashboard', {
    signal,
    params: {
      months,
      organization_id: organizationId,
      dataset_id: datasetId,
    },
  });
  return data;
}

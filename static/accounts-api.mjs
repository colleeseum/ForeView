async function jsonResponse(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

export async function loadAssetData() {
  const [accountData, holdingData, realEstateData] = await Promise.all([
    fetch('/api/model/accounts').then(jsonResponse),
    fetch('/api/model/holdings').then(jsonResponse),
    fetch('/api/model/real-estate').then(jsonResponse),
  ]);
  return {
    accounts: accountData.accounts,
    categoryTotals: accountData.category_totals,
    holdings: holdingData.holdings,
    realEstateAssets: realEstateData.assets,
  };
}

export async function loadPeople() {
  return (await fetch('/api/model/people').then(jsonResponse)).people;
}

export function saveJson(url, method, payload) {
  return fetch(url, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  }).then(jsonResponse);
}

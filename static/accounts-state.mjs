export const assetGroups = [
  ['non_registered', 'Non-registered'],
  ['tfsa', 'TFSA'],
  ['rrsp', 'RRSP'],
  ['resp', 'RESP'],
];

const requestedView = new URLSearchParams(window.location.search).get('tab');
const validViews = new Set([...assetGroups.map(([type]) => type), 'real_estate']);

export const assetState = {
  accounts: [],
  categoryTotals: [],
  holdings: [],
  people: [],
  realEstateAssets: [],
  view: validViews.has(requestedView) ? requestedView : 'non_registered',
};

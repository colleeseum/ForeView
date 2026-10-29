// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from '../shared/html.mjs';
import {t, locale} from '../shared/i18n.mjs';
import {createDialog} from '../shared/dialog.mjs';

let catalogPromise;
function loadCatalog() {
  if (catalogPromise) return catalogPromise;
  catalogPromise = fetch('/api/help').then(async (response) => {
    const catalog = await response.json();
    if (!response.ok) {
      const error = new Error(catalog?.error || t('help.load_error'));
      error.language = catalog?.error ? 'en-CA' : locale;
      throw error;
    }
    if (!catalog || !Array.isArray(catalog.articles) || !Array.isArray(catalog.tooltips)
        || (catalog.categories !== undefined && !Array.isArray(catalog.categories))) {
      const error = new Error(t('help.load_error'));
      error.language = locale;
      throw error;
    }
    return catalog;
  }).catch(error => {
    catalogPromise = null;
    throw error;
  });
  return catalogPromise;
}
// Help is fetched eagerly, but failures are presented when the user opens it.
loadCatalog().catch(() => {});

const tooltip = document.createElement('section');
tooltip.className = 'help-tooltip fv-ui';
tooltip.id = 'help-quick-reference';
tooltip.hidden = true;
tooltip.setAttribute('role', 'tooltip');
tooltip.innerHTML = '<strong></strong><p></p>';
document.body.append(tooltip);

const backdrop = document.createElement('dialog');
backdrop.className = 'help-drawer-backdrop fv-ui';
backdrop.setAttribute('aria-labelledby', 'full-help-title');
backdrop.hidden = true;
backdrop.innerHTML = `<section class="help-drawer">
  <div class="help-controls">
  <button class="help-drawer-close fv-button" type="button" aria-label="${t('help.close')}">×</button>
  <p class="eyebrow">${t('help.reference')}</p>
  <h1 id="full-help-title">${t('help.title')}</h1>
  <label class="help-search-label" for="help-search">${t('help.search')}</label>
  <input id="help-search" class="help-search fv-input" type="search" placeholder="${t('help.search_placeholder')}" autocomplete="off" autofocus aria-controls="help-results">
  <p class="help-status fv-help" role="status" aria-live="polite"></p>
  </div>
  <div class="help-layout">
    <nav id="help-results" class="help-results" aria-label="${t('help.topics')}"></nav>
    <article class="help-article" tabindex="0" aria-labelledby="help-article-title"><h2 id="help-article-title"></h2><p class="help-article-summary"></p><div class="help-article-body"></div></article>
  </div>
</section>`;
document.body.append(backdrop);

const search = backdrop.querySelector('#help-search');
const status = backdrop.querySelector('.help-status');
const results = backdrop.querySelector('.help-results');
const articleTitle = backdrop.querySelector('.help-article h2');
const articleSummary = backdrop.querySelector('.help-article-summary');
const articleBody = backdrop.querySelector('.help-article-body');
let selectedArticleKey = null;
let renderVersion = 0;
let tooltipVersion = 0;
let tooltipAnchor = null;
let controller;

function pageArticleKey() {
  const declaredKey = document.querySelector('main > header')?.dataset.helpArticle;
  if (declaredKey) return declaredKey;
  const mapping = {
    '/': 'summary',
    '/expenses': 'expenses',
    '/connections': 'connections',
    '/accounts': 'assets',
    '/income': 'income',
    '/transactions': 'transactions',
    '/settings': 'public-rule-approval',
  };
  return mapping[window.location.pathname] || null;
}

function closeTooltip() {
  tooltipVersion += 1;
  tooltip.hidden = true;
  if (tooltipAnchor) {
    const descriptions = (tooltipAnchor.getAttribute('aria-describedby') || '').split(/\s+/)
      .filter(id => id && id !== tooltip.id);
    if (descriptions.length) tooltipAnchor.setAttribute('aria-describedby', descriptions.join(' '));
    else tooltipAnchor.removeAttribute('aria-describedby');
  }
  tooltipAnchor = null;
}

function positionTooltip() {
  if (tooltip.hidden || !tooltipAnchor) return;
  const box = tooltipAnchor.getBoundingClientRect();
  if (box.bottom < 0 || box.top > window.innerHeight) {closeTooltip(); return;}
  const size = tooltip.getBoundingClientRect();
  const top = box.bottom + size.height + 16 <= window.innerHeight
    ? box.bottom + 8 : box.top - size.height - 8;
  tooltip.style.top = `${Math.max(8, Math.min(top, window.innerHeight - size.height - 8))}px`;
  tooltip.style.left = `${Math.max(8, Math.min(box.left, window.innerWidth - size.width - 8))}px`;
}

function closeFullHelp() {
  if (backdrop.hidden) return;
  renderVersion += 1;
  closeTooltip();
  backdrop.hidden = true;
  controller.close();
}

function showArticle(article, language = 'en-CA') {
  if (!article) {
    articleTitle.textContent = t('help.no_match');
    articleTitle.lang = locale;
    articleSummary.textContent = '';
    articleSummary.lang = locale;
    articleBody.textContent = t('help.try_keyword');
    articleBody.lang = locale;
    selectedArticleKey = null;
    return;
  }
  selectedArticleKey = article.key;
  articleTitle.textContent = article.title;
  articleTitle.lang = article.field_languages?.title || article.language || language;
  articleSummary.textContent = article.summary;
  articleSummary.lang = article.field_languages?.summary || article.language || language;
  articleBody.textContent = article.body;
  articleBody.lang = article.field_languages?.body || article.language || language;
  results.querySelectorAll('[data-help-result]').forEach((button) => {
    button.classList.toggle('active', button.dataset.helpResult === article.key);
    if (button.dataset.helpResult === article.key) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  });
}

function matchingArticles(articles, query, categories) {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return articles;
  return articles.filter((article) => [
    article.title, article.summary, article.body, ...(article.keywords || []),
    ...categoryPath(article.category, categories).map((category) => category.title),
  ].join(' ').toLocaleLowerCase().includes(normalized));
}

function categoryPath(categoryKey, categories) {
  const byKey = new Map(categories.map((category) => [category.key, category]));
  const path = [];
  const visited = new Set();
  let current = byKey.get(categoryKey);
  while (current && !visited.has(current.key)) {
    visited.add(current.key);
    path.unshift(current);
    current = byKey.get(current.parent);
  }
  return path;
}

function renderResults(articles, preferredKey = null, language = 'en-CA', categories = [], searching = false) {
  articles = [...articles].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  results.lang = language;
  const articleButton = (article, path = '') =>
    `<button class="fv-button" type="button" data-help-result="${escapeHtml(article.key)}">${path}<strong lang="${escapeHtml(article.field_languages?.title || article.language || language)}">${escapeHtml(article.title)}</strong><span lang="${escapeHtml(article.field_languages?.summary || article.language || language)}">${escapeHtml(article.summary)}</span></button>`;
  if (searching) {
    results.innerHTML = articles.map((article) => {
      const path = categoryPath(article.category, categories).map((part) =>
        `<span lang="${escapeHtml(part.language || language)}">${escapeHtml(part.title)}</span>`).join(' › ');
      return articleButton(article, `<small lang="${escapeHtml(language)}">${path}</small>`);
    }).join('');
  } else {
    const renderBranch = (parent = null) => categories.filter((category) => category.parent === parent)
      .sort((a, b) => a.order - b.order).map((category) => {
        const direct = articles.filter((article) => article.category === category.key);
        const children = renderBranch(category.key);
        if (!direct.length && !children) return '';
        const buttons = direct.map((article) => articleButton(article)).join('');
        return `<details class="help-category"><summary lang="${escapeHtml(category.language || language)}">${escapeHtml(category.title)}</summary><div class="help-category-children">${buttons}${children}</div></details>`;
      }).join('');
    results.innerHTML = renderBranch();
  }
  // The fallback must follow visible category traversal, not global article order.
  const buttons = [...results.querySelectorAll('[data-help-result]')];
  const selectedButton = buttons.find((button) => button.dataset.helpResult === preferredKey) || buttons[0];
  let branch = selectedButton?.closest('.help-category');
  while (branch) {
    branch.open = true;
    branch = branch.parentElement.closest('.help-category');
  }
  showArticle(articles.find((article) => article.key === selectedButton?.dataset.helpResult), language);
  status.textContent = articles.length ? t('help.results_count', {count: articles.length}) : t('help.no_match');
}

function showCatalogFailure(error) {
  status.textContent = t('help.unavailable');
  articleTitle.textContent = t('help.unavailable');
  articleTitle.lang = locale;
  articleBody.textContent = error.message;
  articleBody.lang = error.language || 'en-CA';
}

async function openFullHelp(key = null) {
  const invoker = document.activeElement;
  const version = ++renderVersion;
  closeTooltip();
  backdrop.hidden = false;
  controller.open(invoker);
  results.textContent = '';
  search.value = '';
  articleTitle.textContent = t('help.loading');
  articleTitle.lang = locale;
  articleSummary.textContent = '';
  articleSummary.lang = locale;
  articleBody.textContent = '';
  articleBody.lang = locale;
  status.textContent = t('help.loading');
  search.focus();
  try {
    const catalog = await loadCatalog();
    if (version !== renderVersion || backdrop.hidden) return;
    renderResults(catalog.articles, key || pageArticleKey(), catalog.language || 'en-CA', catalog.categories || []);
  } catch (error) {
    if (version !== renderVersion || backdrop.hidden) return;
    showCatalogFailure(error);
  }
}

async function openTooltip(key, anchor) {
  closeTooltip();
  const version = tooltipVersion;
  try {
    const catalog = await loadCatalog();
    if (version !== tooltipVersion || !anchor.isConnected) return;
    const content = catalog.tooltips.find((item) => item.key === key);
    if (!content) return;
    tooltip.querySelector('strong').textContent = content.title;
    tooltip.querySelector('p').textContent = content.body;
    tooltip.querySelector('strong').lang = content.field_languages?.title || content.language || catalog.language || 'en-CA';
    tooltip.querySelector('p').lang = content.field_languages?.body || content.language || catalog.language || 'en-CA';
    tooltip.lang = content.language || catalog.language || 'en-CA';
    tooltipAnchor = anchor;
    anchor.setAttribute('aria-describedby', [anchor.getAttribute('aria-describedby'), tooltip.id].filter(Boolean).join(' '));
    (anchor.closest('dialog[open]') || document.body).append(tooltip);
    tooltip.hidden = false;
    positionTooltip();
  } catch (_error) {
    closeTooltip();
  }
}

const pageHeader = document.querySelector('main > header');
if (pageHeader) {
  const fullHelpButton = document.createElement('button');
  fullHelpButton.className = 'full-help-button fv-ui';
  fullHelpButton.type = 'button';
  fullHelpButton.setAttribute('aria-label', t('help.open'));
  fullHelpButton.title = t('help.full_help');
  fullHelpButton.textContent = '?';
  pageHeader.append(fullHelpButton);
  fullHelpButton.addEventListener('click', () => openFullHelp());
}
controller = createDialog(backdrop, {fallbackFocus: document.querySelector('.full-help-button')});

window.openContextHelp = (key) => openFullHelp(key);

// Existing in-modal income/expense help remains owned by its feature controller.
document.addEventListener('focusin', event => {
  const button = event.target.closest('[data-help-tooltip]');
  if (button && !button.closest('dialog')) openTooltip(button.dataset.helpTooltip, button);
  else if (!tooltip.contains(event.target)) closeTooltip();
});
window.addEventListener('resize', closeTooltip);
document.addEventListener('scroll', positionTooltip, true);

document.addEventListener('click', (event) => {
  const tooltipButton = event.target.closest('[data-help-tooltip]');
  if (tooltipButton) {
    event.stopPropagation();
    openTooltip(tooltipButton.dataset.helpTooltip, tooltipButton);
    return;
  }
  const contextButton = event.target.closest('[data-help-article]');
  if (contextButton) {
    event.stopPropagation();
    openFullHelp(contextButton.dataset.helpArticle);
    return;
  }
  if (!tooltip.hidden && !tooltip.contains(event.target)) closeTooltip();
});

results.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-help-result]');
  if (!button) return;
  const version = renderVersion;
  const catalog = await loadCatalog();
  if (version !== renderVersion || backdrop.hidden) return;
  showArticle(
    catalog.articles.find((article) => article.key === button.dataset.helpResult),
    catalog.language || 'en-CA',
  );
  // Keep the selected reading surface in the dialog controller's Tab order.
  backdrop.querySelector('.help-article').focus();
});

search.addEventListener('input', async () => {
  const version = ++renderVersion;
  try {
    const catalog = await loadCatalog();
    if (version !== renderVersion || backdrop.hidden) return;
    const matches = matchingArticles(catalog.articles, search.value, catalog.categories || []);
    renderResults(matches, selectedArticleKey, catalog.language || 'en-CA', catalog.categories || [], Boolean(search.value.trim()));
  } catch (error) {
    if (version === renderVersion && !backdrop.hidden) showCatalogFailure(error);
  }
});

backdrop.querySelector('.help-drawer-close').addEventListener('click', closeFullHelp);
backdrop.addEventListener('cancel', event => {event.preventDefault(); closeFullHelp();});
backdrop.addEventListener('click', (event) => {
  if (event.target === backdrop) closeFullHelp();
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (!backdrop.hidden) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
  closeTooltip();
  closeFullHelp();
}, true);

// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from './html.mjs';
import {t, locale} from './i18n.mjs';

const catalogPromise = fetch('/api/help').then(async (response) => {
  const catalog = await response.json();
  if (!response.ok) {
    const error = new Error(catalog.error || t('help.load_error'));
    error.language = catalog.error ? 'en-CA' : locale;
    throw error;
  }
  return catalog;
});

const tooltip = document.createElement('section');
tooltip.className = 'help-tooltip';
tooltip.hidden = true;
tooltip.setAttribute('role', 'tooltip');
tooltip.innerHTML = '<strong></strong><p></p>';
document.body.append(tooltip);

const backdrop = document.createElement('div');
backdrop.className = 'help-drawer-backdrop';
backdrop.hidden = true;
backdrop.innerHTML = `<aside class="help-drawer" role="dialog" aria-modal="true" aria-labelledby="full-help-title">
  <button class="help-drawer-close" type="button" aria-label="${t('help.close')}">×</button>
  <p class="eyebrow">${t('help.reference')}</p>
  <h1 id="full-help-title">${t('help.title')}</h1>
  <label class="help-search-label" for="help-search">${t('help.search')}</label>
  <input id="help-search" class="help-search" type="search" placeholder="${t('help.search_placeholder')}" autocomplete="off">
  <div class="help-layout">
    <nav class="help-results" aria-label="${t('help.topics')}"></nav>
    <article class="help-article"><h2></h2><p class="help-article-summary"></p><div class="help-article-body"></div></article>
  </div>
</aside>`;
document.body.append(backdrop);

const drawer = backdrop.querySelector('.help-drawer');
const search = backdrop.querySelector('#help-search');
const results = backdrop.querySelector('.help-results');
const articleTitle = backdrop.querySelector('.help-article h2');
const articleSummary = backdrop.querySelector('.help-article-summary');
const articleBody = backdrop.querySelector('.help-article-body');
let selectedArticleKey = null;

function pageArticleKey() {
  const declaredKey = document.querySelector('main > header')?.dataset.helpArticle;
  if (declaredKey) return declaredKey;
  const mapping = {
    '/accounts': 'assets',
    '/income': 'income',
    '/transactions': 'transactions',
    '/settings': 'public-rule-approval',
  };
  return mapping[window.location.pathname] || null;
}

function closeTooltip() {
  tooltip.hidden = true;
}

function closeFullHelp() {
  backdrop.hidden = true;
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
  articleTitle.lang = language;
  articleSummary.textContent = article.summary;
  articleSummary.lang = language;
  articleBody.textContent = article.body;
  articleBody.lang = language;
  results.querySelectorAll('[data-help-result]').forEach((button) => {
    button.classList.toggle('active', button.dataset.helpResult === article.key);
  });
}

function matchingArticles(articles, query) {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return articles;
  return articles.filter((article) => [
    article.title, article.summary, article.body, ...(article.keywords || []),
  ].join(' ').toLocaleLowerCase().includes(normalized));
}

function renderResults(articles, preferredKey = null, language = 'en-CA') {
  results.lang = language;
  results.innerHTML = articles.map((article) =>
    `<button type="button" data-help-result="${escapeHtml(article.key)}"><strong>${escapeHtml(article.title)}</strong><span>${escapeHtml(article.summary)}</span></button>`
  ).join('');
  const selected = articles.find((article) => article.key === preferredKey) || articles[0];
  showArticle(selected, language);
}

async function openFullHelp(key = null) {
  backdrop.hidden = false;
  search.value = '';
  articleTitle.textContent = t('help.loading');
  articleTitle.lang = locale;
  articleSummary.textContent = '';
  articleSummary.lang = locale;
  articleBody.textContent = '';
  articleBody.lang = locale;
  try {
    const catalog = await catalogPromise;
    renderResults(catalog.articles, key || pageArticleKey(), catalog.language || 'en-CA');
    search.focus();
  } catch (error) {
    articleTitle.textContent = t('help.unavailable');
    articleBody.textContent = error.message;
    articleBody.lang = error.language || 'en-CA';
  }
}

async function openTooltip(key, anchor) {
  try {
    const catalog = await catalogPromise;
    const content = catalog.tooltips.find((item) => item.key === key);
    if (!content) return;
    tooltip.querySelector('strong').textContent = content.title;
    tooltip.querySelector('p').textContent = content.body;
    tooltip.lang = catalog.language || 'en-CA';
    tooltip.hidden = false;
    const box = anchor.getBoundingClientRect();
    tooltip.style.top = `${Math.min(box.bottom + 8, window.innerHeight - 160)}px`;
    tooltip.style.left = `${Math.min(Math.max(16, box.left), window.innerWidth - 340)}px`;
  } catch (_error) {
    closeTooltip();
  }
}

const pageHeader = document.querySelector('main > header');
if (pageHeader) {
  const fullHelpButton = document.createElement('button');
  fullHelpButton.className = 'full-help-button';
  fullHelpButton.type = 'button';
  fullHelpButton.setAttribute('aria-label', t('help.open'));
  fullHelpButton.title = t('help.full_help');
  fullHelpButton.textContent = '?';
  pageHeader.append(fullHelpButton);
  fullHelpButton.addEventListener('click', () => openFullHelp());
}

window.openContextHelp = (key) => openFullHelp(key);

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
  const catalog = await catalogPromise;
  showArticle(
    catalog.articles.find((article) => article.key === button.dataset.helpResult),
    catalog.language || 'en-CA',
  );
});

search.addEventListener('input', async () => {
  const catalog = await catalogPromise;
  const matches = matchingArticles(catalog.articles, search.value);
  renderResults(matches, selectedArticleKey, catalog.language || 'en-CA');
});

backdrop.querySelector('.help-drawer-close').addEventListener('click', closeFullHelp);
backdrop.addEventListener('click', (event) => {
  if (event.target === backdrop) closeFullHelp();
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  closeTooltip();
  closeFullHelp();
});

'use strict';
// Translate authored interface copy only. Project content never passes through here.
window.AgoraI18n = (() => {
  const dictionaries = {en: {}, fr: {}}, originals = new WeakMap();
  let language = 'en';
  try { if (localStorage.getItem('agora-language') === 'fr') language = 'fr'; } catch (_) { /* Storage may be disabled. */ }
  function t(key, params = {}) {
    const text = dictionaries[language][key] ?? dictionaries.en[key] ?? key;
    return text.replace(/\{(\w+)\}/g, (match, name) => String(params[name] ?? match));
  }
  function apply(root = document) {
    for (const node of root.querySelectorAll('[data-fr], [data-fr-placeholder], [data-fr-aria-label]')) {
      if (!originals.has(node)) originals.set(node, {text: node.textContent, placeholder: node.getAttribute('placeholder'), aria: node.getAttribute('aria-label')});
      const original = originals.get(node);
      if (node.hasAttribute('data-fr')) node.textContent = language === 'fr' ? node.dataset.fr : original.text;
      for (const [attr, field] of [['placeholder', 'placeholder'], ['aria-label', 'aria']]) {
        if (node.hasAttribute('data-fr-' + attr)) node.setAttribute(attr, language === 'fr' ? node.getAttribute('data-fr-' + attr) : original[field]);
      }
    }
    for (const node of root.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
    document.documentElement.lang = language;
    document.title = language === 'fr' ? 'Agora · Faites dialoguer vos agents' : 'Agora · Put your agents in conversation';
    const selector = document.getElementById('language');
    if (selector) selector.value = language;
    for (const link of document.querySelectorAll('.install-guide')) link.href = 'https://github.com/Jeffchoux/agora/blob/main/docs/INSTALL' + (language === 'en' ? '.en' : '') + '.md';
  }
  function setLanguage(value) {
    language = value === 'fr' ? 'fr' : 'en';
    try { localStorage.setItem('agora-language', language); } catch (_) { /* Preference remains valid for this page. */ }
    apply();
    document.dispatchEvent(new CustomEvent('agora:language', {detail: {language}}));
  }
  return {t, apply, setLanguage, get language() { return language; }, register(messages) { for (const lang of ['en', 'fr']) Object.assign(dictionaries[lang], messages[lang] || {}); }};
})();

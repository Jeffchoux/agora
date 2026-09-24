'use strict';
// Public directory and a local-only configuration builder. No credentials or model calls.
(() => {
  const byId = id => document.getElementById(id);
  const dialog = byId('model-catalog'), list = byId('catalog-list');
  let catalog = null, loading = false;
  const selections = new Map();
  const copy = (en, fr) => AgoraI18n.language === 'fr' ? fr : en;
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
  const mode = value => ({api:copy('API · account pricing and quotas','API · tarifs et quotas du compte'),subscription:copy('Subscription / CLI · eligibility and quotas apply','Abonnement / CLI · éligibilité et quotas'),local:copy('Local · your hardware, no paid API','Local · votre matériel, sans API payante'),pending:copy('Adapter needed · not selectable','Adaptateur à développer · non sélectionnable')})[value];
  function selectedCount() {
    byId('catalog-selected').textContent = copy(`${selections.size} access routes selected. One profile per model; up to 32 profiles per installation.`,`${selections.size} accès sélectionnés. Un profil par modèle ; 32 profils au maximum par installation.`);
    byId('catalog-download').disabled = !selections.size;
    byId('catalog-review').disabled = !selections.size;
    byId('catalog-review').textContent = copy(`Review my selection (${selections.size})`,`Voir ma sélection (${selections.size})`);
  }
  function render() {
    if (!catalog) return;
    const search = byId('catalog-search').value.trim().toLowerCase(), filter = byId('catalog-filter').value;
    const entries = catalog.entries.filter(p => (!search || `${p.name} ${p.families}`.toLowerCase().includes(search)) && (filter === 'all' || p.mode === filter || (filter === 'selected' && selections.has(p.id))));
    const selectedOption = byId('catalog-filter').querySelector('[value=selected]');
    selectedOption.textContent = copy('My selection','Ma sélection');
    list.replaceChildren();
    byId('catalog-status').textContent = copy(`${entries.length} routes · directory reviewed ${catalog.reviewed}. No live availability check.`,`${entries.length} accès · annuaire revu le ${catalog.reviewed}. Disponibilité non testée en direct.`);
    if (!entries.length) list.append(node('p',copy('No match. Try a model family or use the custom API route.','Aucun résultat. Essayez une famille de modèles ou l’accès API personnalisé.'),'empty'));
    for (const p of entries) {
      const row = node('div',null,'catalog-row'), check = node('input'), content = node('div');
      check.type = 'checkbox'; check.id = 'provider-' + p.id; check.checked = selections.has(p.id); check.disabled = p.mode === 'pending';
      const name = node('label',p.name); name.htmlFor = check.id;
      const badge = node('span',mode(p.mode),'catalog-badge');
      content.append(badge,name,node('p',p.families,'hint'));
      const requirements = node('details');
      requirements.append(node('summary',copy('Connection requirements & models','Connexion et modèles disponibles')));
      requirements.append(node('p',p.note[AgoraI18n.language] || p.note.en,'hint'));
      const link = node('a',copy('Official documentation / models ↗','Documentation officielle / modèles ↗')); link.href = p.docs; link.target = '_blank'; link.rel = 'noopener noreferrer'; requirements.append(link); content.append(requirements);
      const setup = node('div',null,'catalog-models'); setup.hidden = !check.checked;
      const label = node('label',copy('Model IDs (one per line, from your provider’s catalogue)','Identifiants des modèles (un par ligne, depuis le catalogue du fournisseur)')); label.htmlFor = 'models-' + p.id;
      const input = node('textarea'); input.id = label.htmlFor; input.rows = 2; input.maxLength = 3900; input.value = selections.get(p.id)?.models || ''; input.disabled = !check.checked; input.required = check.checked;
      input.addEventListener('input',() => { selections.get(p.id).models = input.value; byId('catalog-error').textContent = ''; });
      setup.append(label,input);
      if (p.mode === 'subscription') setup.append(node('p',copy('Sign in on the runner using the official CLI. No API key. Only models accepted by that CLI and your account.','Connectez le CLI officiel sur le runner. Sans clé API. Uniquement les modèles acceptés par ce CLI et votre compte.'),'hint'));
      if (p.key_env) setup.append(node('p',copy(`Private credential name: ${p.key_env}. Never paste the key here.`,`Nom de la clé dans le fichier privé : ${p.key_env}. Ne collez jamais la clé ici.`),'hint'));
      if (p.custom_endpoint) {
        const label = node('label',copy('Your HTTPS Chat Completions base URL','Votre URL HTTPS de base Chat Completions')); label.htmlFor = 'endpoint-' + p.id;
        const endpoint = node('input'); endpoint.id = label.htmlFor; endpoint.type = 'url'; endpoint.value = selections.get(p.id)?.endpoint || ''; endpoint.maxLength = 500; endpoint.disabled = !check.checked; endpoint.required = check.checked;
        endpoint.oninput = () => { selections.get(p.id).endpoint = endpoint.value; };
        setup.append(label,endpoint);
      }
      check.onchange = () => {
        if (check.checked) selections.set(p.id,{models:input.value,endpoint:setup.querySelector('input')?.value || ''}); else selections.delete(p.id);
        setup.hidden = !check.checked;
        requirements.open = check.checked;
        for (const field of setup.querySelectorAll('input,textarea')) { field.disabled = !check.checked; field.required = check.checked; }
        selectedCount(); byId('catalog-error').textContent = '';
        if (check.checked) input.focus();
      };
      content.append(setup); row.append(check,content); list.append(row);
    }
    selectedCount();
  }
  async function load() {
    if (loading) return;
    loading = true; byId('catalog-retry').hidden = true; byId('catalog-status').textContent = copy('Loading directory…','Chargement de l’annuaire…');
    try {
      const response = await fetch('providers.json', {credentials:'omit'});
      if (!response.ok) throw Error('catalog');
      catalog = await response.json(); render();
    } catch (_) { byId('catalog-status').textContent = copy('Directory unavailable. Your current agents are unchanged.','Annuaire indisponible. Vos agents actuels sont inchangés.'); byId('catalog-retry').hidden = false; }
    finally { loading = false; }
  }
  for (const button of document.querySelectorAll('[data-open-catalog]')) button.onclick = () => { dialog.showModal(); if (!catalog) load(); else render(); };
  byId('catalog-close').onclick = () => dialog.close();
  const selectedOption = node('option',copy('My selection','Ma sélection')); selectedOption.value = 'selected'; byId('catalog-filter').append(selectedOption);
  byId('catalog-review').onclick = () => { byId('catalog-search').value = ''; byId('catalog-filter').value = 'selected'; render(); byId('catalog-filter').focus(); };
  byId('catalog-retry').onclick = load;
  byId('catalog-search').oninput = render; byId('catalog-filter').onchange = render;
  document.addEventListener('agora:language', render);
  byId('catalog-form').onsubmit = event => {
    event.preventDefault(); byId('catalog-error').textContent = '';
    try {
      const profiles = {};
      for (const [id, value] of selections) {
        const p = catalog.entries.find(p => p.id === id);
        const models = [...new Set(value.models.split('\n').map(s => s.trim()).filter(Boolean))];
        if (!models.length || models.some(m => m.length > 120 || /[\x00-\x1f]/.test(m))) throw Error(copy(`Enter valid model IDs for ${p.name}.`, `Indiquez des modèles valides pour ${p.name}.`));
        if (p.provider === 'openrouter-free' && models.some(m => !m.endsWith(':free'))) throw Error(copy('OpenRouter free routes require model IDs ending in :free.','Les modèles OpenRouter gratuits doivent se terminer par :free.'));
        let endpoint = p.endpoint;
        if (p.custom_endpoint) {
          const url = new URL(value.endpoint);
          if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw Error(copy('Use an HTTPS base URL without credentials, query or fragment.','Utilisez une URL HTTPS de base sans identifiants, paramètres ni fragment.'));
          endpoint = value.endpoint.replace(/\/$/,'');
        }
        for (const [index, model] of models.entries()) {
          const profile = {label:`${p.name} · ${model}`.slice(0,120),provider:p.provider,model};
          if (endpoint) profile.endpoint = endpoint;
          if (p.mode !== 'local') profile.operator_authorized = false;
          if (p.key_env) { profile.key_env = p.key_env; profile.credential_file = '~/.config/agora/credentials.json'; }
          profiles[`${id}-${index+1}`] = profile;
        }
      }
      if (!Object.keys(profiles).length || Object.keys(profiles).length > 32) throw Error(copy('Select 1–32 model profiles.','Choisissez de 1 à 32 profils de modèles.'));
      const url = URL.createObjectURL(new Blob([JSON.stringify(profiles,null,2)+'\n'],{type:'application/json'}));
      const a = node('a'); a.href = url; a.download = 'agora-agents.json'; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
      byId('catalog-selected').textContent = copy('Configuration downloaded — not connected yet. Follow the three steps below.','Configuration téléchargée — pas encore connectée. Suivez les trois étapes ci-dessous.');
    } catch (error) { byId('catalog-error').textContent = error.message; }
  };
})();

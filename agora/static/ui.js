'use strict';
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('agora-operator') || '', selected = null, busy = false;
let listSnapshot = '', detailSnapshot = '', firstLoad = true, formSeeded = false;
const labels = {draft:'Prête à lancer', queued:'En attente', running:'En cours', finished:'Échanges terminés', stopped:'Arrêtée', failed:'Échec', done:'Contribution reçue'};
function el(tag, value, cls) { const n = document.createElement(tag); if (value !== undefined) n.textContent = value; if (cls) n.className = cls; return n; }
function notice(value, error = false) { $('notice').textContent = value; $('notice').className = error ? 'error' : ''; }
async function api(path = '', body) {
  const r = await fetch('v1/console' + path, {method:body ? 'POST' : 'GET', headers:{Authorization:'Bearer ' + token, ...(body ? {'Content-Type':'application/json'} : {})}, body:body ? JSON.stringify(body) : undefined});
  const d = await r.json();
  if (!r.ok) { if (r.status === 401) logout(); throw Error(d.error || 'Connexion indisponible'); }
  return d;
}
function logout() { token = ''; sessionStorage.removeItem('agora-operator'); $('workspace').hidden = true; $('login').hidden = false; $('logout').hidden = true; selected = null; listSnapshot = detailSnapshot = ''; firstLoad = true; }
async function refresh(force = false) {
  const data = await api();
  $('login').hidden = true; $('workspace').hidden = false; $('logout').hidden = false;
  if (!$('agents').children.length) for (const a of data.agents) {
    const l = el('label', undefined, 'agent'), c = el('input'), t = el('span', a.label);
    c.type = 'checkbox'; c.value = a.id; c.name = 'agent'; c.checked = ['codex','qwen-coder'].includes(a.id);
    t.append(el('small', a.type)); l.append(c,t); $('agents').append(l);
  }
  if (!$('target').children.length) for (const t of data.targets) {
    const o = el('option', t.label + ' · ' + t.repository); o.value = t.id; $('target').append(o);
  }
  if (!formSeeded && $('target').selectedOptions.length) {
    $('title').value = 'Revue de ' + $('target').selectedOptions[0].textContent.split(' · ')[0];
    $('brief').value = 'Vérifiez le code du dépôt, les tests disponibles, le site public et son UX/UI sur mobile et ordinateur. Posez-vous des questions, répondez-vous avec des preuves précises, puis indiquez les problèmes prioritaires et ce qui reste à vérifier. Ne modifiez rien.';
    formSeeded = true;
  }
  if (firstLoad) { $('compose').open = !data.missions.length; firstLoad = false; }
  if (!selected || !data.missions.some(m => m.id === selected)) selected = data.missions[0]?.id || null;
  const snapshot = JSON.stringify([data.missions, selected]);
  if (force || snapshot !== listSnapshot) {
    listSnapshot = snapshot; $('mission-list').replaceChildren();
    if (!data.missions.length) $('mission-list').append(el('p','Aucune mission encore. Lancez une première vérification.','empty'));
    for (const m of data.missions) {
      const b = el('button', undefined, 'mission-card' + (m.id === selected ? ' selected' : ''));
      b.type = 'button'; b.setAttribute('aria-current', m.id === selected ? 'true' : 'false');
      b.append(el('span', labels[m.status] || m.status, 'status'), el('strong', m.title), el('small', m.calls + ' / ' + m.max_calls + ' appels'));
      b.onclick = () => show(m.id, true); $('mission-list').append(b);
    }
  }
  if (selected) await show(selected, false, force);
  else { $('detail').hidden = true; detailSnapshot = ''; }
}
async function show(id, focus = false, force = false) {
  selected = id;
  const m = await api('/' + encodeURIComponent(id)), snapshot = JSON.stringify(m), box = $('detail');
  if (!force && snapshot === detailSnapshot) { if (focus) focusDetail(); return; }
  detailSnapshot = snapshot; box.hidden = false; box.replaceChildren();
  const heading = el('div', undefined, 'detail-head'), title = el('div');
  title.append(el('p', labels[m.status] || m.status, 'eyebrow'), el('h2', m.title));
  const actions = el('div', undefined, 'actions');
  for (const [action, label] of [['start','Lancer cette mission'],['stop','Arrêter les prochains appels']]) {
    if ((action === 'start' && m.status !== 'draft') || (action === 'stop' && !['queued','running'].includes(m.status))) continue;
    const b = el('button', label, action === 'start' ? 'primary' : 'quiet');
    b.onclick = async () => { b.disabled = true; try { await api('/' + id + '/' + action, {}); detailSnapshot = ''; await refresh(true); notice(action === 'start' ? 'Mission en file : les preuves seront relevées avant les échanges.' : 'Arrêt enregistré. L’appel déjà engagé peut terminer.'); } catch (e) { notice(e.message,true); b.disabled = false; } };
    actions.append(b);
  }
  const download = el('button','Exporter le rapport JSON','quiet');
  download.onclick = () => { const blob = new Blob([JSON.stringify(m,null,2)], {type:'application/json'}), url = URL.createObjectURL(blob), a = el('a'); a.href = url; a.download = 'agora-' + m.id + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
  actions.append(download); heading.append(title,actions); box.append(heading);
  const target = m.evidence?.repository || m.target || 'Projet non connecté';
  box.append(el('p', target + ' · ' + m.calls + ' / ' + m.max_calls + ' appels · ' + (m.seconds / 60) + ' min maximum', 'mission-meta'));
  const answer = [...m.turns].reverse().find(t => t.status === 'done' && ['answer','review','artifact'].includes(t.kind));
  const latest = answer || [...m.turns].reverse().find(t => t.status === 'done');
  const result = el('section', undefined, 'result');
  result.append(el('p', answer ? 'DERNIÈRE RÉPONSE' : latest ? 'DERNIÈRE CONTRIBUTION' : 'ÉTAT DE LA MISSION', 'eyebrow'));
  if (latest) {
    result.append(el('h3', (answer ? 'Réponse' : latest.kind === 'question' ? 'Question posée' : 'Contribution') + ' de ' + latest.agent));
    result.append(el('p', latest.body || 'Contribution vide.', 'result-body'));
  } else {
    const state = m.status === 'draft' ? 'Prête à lancer. Les preuves seront relevées au démarrage.' : m.status === 'queued' ? 'En attente de l’inspection et des échanges.' : m.status === 'running' ? 'Les agents examinent les preuves et se répondent.' : 'Aucune réponse reçue.';
    result.append(el('h3', state));
  }
  if (m.error) result.append(el('p', 'Erreur : ' + m.error, 'error'));
  box.append(result);
  box.append(el('p', 'Une réponse d’agent n’est pas une validation du livrable. Agora ne lance pas les tests du dépôt et ne modifie pas son code.', 'caveat'));
  const brief = el('details', undefined, 'section-details'); brief.append(el('summary','Question initiale'),el('p',m.brief,'prewrap')); box.append(brief);
  if (m.evidence) { const evidence = el('details', undefined, 'section-details'); evidence.append(el('summary','Preuves et limites de la vérification'), evidenceView(m)); box.append(evidence); }
  else box.append(el('p', m.target ? 'Preuves du dépôt et du site en attente.' : 'Ancienne mission sans projet connecté : seul le brief était disponible.', 'hint'));
  if (m.turns.length) {
    const conversation = el('details', undefined, 'section-details');
    conversation.append(el('summary','Tous les échanges (' + m.turns.length + ')'));
    for (const t of m.turns) {
      const card = el('article',undefined,'turn'), h = el('div',undefined,'turn-heading');
      const kind = {question:'Question',answer:'Réponse',review:'Revue',artifact:'Livrable'}[t.kind] || 'Contribution';
      h.append(el('strong', String(t.ordinal).padStart(2,'0') + ' · ' + kind + ' · ' + t.agent), el('span',labels[t.status] || t.status,'status'));
      card.append(h,el('p',t.body || 'L’agent prépare sa contribution…','prewrap')); conversation.append(card);
    }
    box.append(conversation);
  }
  if (focus) { listSnapshot = ''; focusDetail(); refresh().catch(e => notice(e.message,true)); }
}
function focusDetail() { const box = $('detail'); box.scrollIntoView({block:'start'}); box.tabIndex = -1; box.focus({preventScroll:true}); }
function evidenceView(m) {
  const e = m.evidence, section = el('div',undefined,'evidence');
  section.append(el('p',e.repository + ' · commit ' + e.github_sha.slice(0,12) + ' · ' + e.file_count + ' fichiers répertoriés'));
  const links = el('p',undefined,'evidence-links');
  for (const [label,url] of [['Voir le commit','https://github.com/' + e.repository + '/commit/' + e.github_sha],['Ouvrir le site',e.website]]) {
    const a = el('a',label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; links.append(a);
  }
  section.append(links);
  section.append(el('p',e.production_matches_github === true ? 'Production et GitHub : même commit.' : e.production_matches_github === false ? 'Attention : la production diffère de GitHub.' : 'Commit de production non vérifié.','hint'));
  section.append(el('p',e.checks.length ? 'CI : ' + e.checks.map(x => x.name + ' ' + (x.conclusion || x.status)).join(' · ') : 'CI : aucun check rapporté pour ce commit.','hint'));
  section.append(el('p','Extraits lus : ' + (e.files.map(x => x.path).join(', ') || 'aucun') + '. Ce n’est pas une revue exhaustive du dépôt.','hint'));
  const views = el('div',undefined,'evidence-views');
  for (const view of e.browser) {
    const card = el('div',undefined,'evidence-view'); card.append(el('strong',view.viewport + ' px · ' + (view.http_status || view.error || 'sans réponse')));
    if (view.error) card.append(el('span','Capture indisponible'));
    else {
      card.append(el('span','Titre : ' + (view.title || 'absent') + ' · h1 : ' + ((view.h1 || []).join(' / ') || 'absent')));
      card.append(el('span','Débordement : ' + (view.overflow ? 'oui' : 'non') + ' · images cassées : ' + view.brokenImages + ' · erreurs JS : ' + view.page_errors.length));
      if (view.public_link_probe) { const p = view.public_link_probe; card.append(el('span',p.destination_allowed ? 'Lien « ' + p.label + ' » : Tab ' + (p.tab_reachable ? 'oui' : 'non') + ', Entrée ' + (p.enter_opened_expected ? 'oui' : 'non vérifiée') + ', destination HTTP ' + (p.destination_status || 'non vérifiée') + '.' : 'Lien « ' + p.label + ' » absent ou destination non autorisée.')); }
      if (view.screenshot) { const b = el('button','Voir la capture','quiet'); b.onclick = () => showCapture(m.id,view.viewport); card.append(b); }
    }
    views.append(card);
  }
  section.append(views,el('p','Codex reçoit les captures visuelles ; les autres agents lisent les mesures et extraits. Aucun test unitaire du dépôt n’est exécuté par Agora.','hint'));
  return section;
}
async function showCapture(id,width) {
  try {
    const response = await fetch('v1/console/' + encodeURIComponent(id) + '/evidence/' + width,{headers:{Authorization:'Bearer ' + token}});
    if (!response.ok) throw Error('Capture indisponible');
    const url = URL.createObjectURL(await response.blob()), dialog = el('dialog',undefined,'capture-dialog'), close = el('button','Fermer la capture','quiet'), img = el('img');
    img.src = url; img.alt = 'Capture du site à ' + width + ' pixels'; close.onclick = () => dialog.close(); dialog.append(close,img);
    dialog.addEventListener('close',() => { URL.revokeObjectURL(url); dialog.remove(); }); document.body.append(dialog); dialog.showModal();
  } catch (error) { notice(error.message,true); }
}
$('logout').onclick = logout;
$('target').onchange = () => { if ($('title').value.startsWith('Revue de ')) $('title').value = 'Revue de ' + $('target').selectedOptions[0].textContent.split(' · ')[0]; };
$('new-mission').onclick = () => { $('compose').open = true; $('compose').scrollIntoView({block:'start'}); $('target').focus({preventScroll:true}); };
$('keyfile').onchange = async e => { const f = e.target.files[0]; if (!f) return; if (f.size > 1024) { notice('Fichier de clé invalide.',true); return; } token = (await f.text()).trim(); try { await refresh(); sessionStorage.setItem('agora-operator',token); notice('Atelier ouvert.'); } catch (err) { notice(err.message,true); } e.target.value = ''; };
$('login-form').onsubmit = async e => { e.preventDefault(); token = $('token').value.trim(); try { await refresh(); sessionStorage.setItem('agora-operator',token); $('token').value = ''; notice('Atelier ouvert.'); } catch (err) { notice(err.message,true); } };
$('mission-form').onsubmit = async e => {
  e.preventDefault(); if (busy) return;
  const agents = Array.from(document.querySelectorAll('[name=agent]:checked')).map(x => x.value);
  if (!agents.length || agents.length > 4 || Number($('calls').value) < agents.length) { $('compose').open = true; document.querySelector('.advanced').open = true; notice('Choisissez 1 à 4 agents et au moins un appel par agent.',true); return; }
  busy = true; $('create').disabled = true;
  try {
    const d = await api('',{title:$('title').value,target:$('target').value,brief:$('brief').value,agents,max_calls:Number($('calls').value),seconds:Number($('duration').value),request_key:crypto.randomUUID()});
    selected = d.id; detailSnapshot = ''; await refresh(true); $('compose').open = false;
    try { await api('/' + encodeURIComponent(d.id) + '/start',{}); detailSnapshot = ''; await refresh(true); notice('Mission lancée. Les preuves sont relevées avant les échanges.'); }
    catch (startError) { notice('Mission préparée mais non lancée : ' + startError.message + '. Utilisez « Lancer cette mission » pour réessayer.',true); }
    focusDetail();
  } catch (err) { notice(err.message,true); }
  finally { busy = false; $('create').disabled = false; }
};
if (token) refresh().catch(e => notice(e.message,true));
setInterval(() => { if (token && !document.hidden && !busy) refresh().catch(e => notice(e.message,true)); },10000);

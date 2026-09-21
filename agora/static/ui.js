'use strict';
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('agora-operator') || '', selected = null, busy = false;
let listSnapshot = '', detailSnapshot = '', firstLoad = true, formSeeded = false, targetsSnapshot = '';
let projectFilter = sessionStorage.getItem('agora-project') || 'all', targets = [], agentLabels = {};
let chatSnapshot = '';
let motionPaused = sessionStorage.getItem('agora-motion-paused') === 'true';
const tr = (key, params) => AgoraI18n.t('console.' + key, params);
const serverErrorKeys = Object.freeze({
  "Nom de projet requis, 80 caractères maximum": "errors.projectName",
  "Détails du projet : 2 000 caractères maximum": "errors.projectNotes",
  "Ce dépôt et ce site sont déjà enregistrés avec d’autres détails": "errors.projectDuplicate",
  "Limite de 100 projets atteinte": "errors.projectLimit",
  "Projet introuvable": "errors.projectMissing",
  "Message requis, 4 000 caractères maximum": "errors.messageBody",
  "Identifiant de message requis": "errors.messageId",
  "Conflit de message": "errors.messageConflict",
  "Limite de 50 messages atteinte pour ce projet": "errors.messageLimit",
  "Titre requis, 100 caractères maximum": "errors.missionTitle",
  "Le brief doit contenir 10 à 8 000 caractères": "errors.missionBrief",
  "Choisir 1 à 4 agents disponibles": "errors.agents",
  "Prévoir au moins un appel par agent, au plus 12 appels": "errors.calls",
  "Durée entre 3 et 30 minutes": "errors.duration",
  "Identifiant de création requis": "errors.creationId",
  "Projet non connecté": "errors.projectDisconnected",
  "Conflit de création": "errors.creationConflict",
  "Mission introuvable": "errors.missionMissing",
  "Trois missions sont déjà en attente ou en cours": "errors.missionLimit",
  "Action inconnue": "errors.actionUnknown",
  "Réservation inexistante": "errors.reservationMissing",
  "Inspection impossible ; aucun agent appelé.": "errors.inspectionFailed",
  "Plafond atteint : aucun nouvel appel.": "errors.limitReached",
  "Appel échoué ; pas de nouvelle tentative automatique.": "errors.callFailed",
  "Exécution interrompue. Appels réservés conservés ; aucun redémarrage automatique.": "errors.executionInterrupted",
  "Dépôt GitHub invalide": "errors.repositoryInvalid",
  "Indiquez un dépôt GitHub sous la forme owner/repo ou son URL": "errors.repositoryFormat",
  "URL publique HTTPS invalide": "errors.websiteInvalid",
  "Indiquez une URL publique HTTPS sans identifiant, paramètre ni port spécial": "errors.websiteFormat",
  "Les adresses IP directes ne sont pas acceptées": "errors.directIp",
  "Adresse publique introuvable": "errors.addressMissing",
  "Adresse publique requise": "errors.publicAddress",
  "Lecture GitHub indisponible": "errors.githubUnavailable",
  "Branche GitHub par défaut introuvable": "errors.defaultBranch",
  "SHA GitHub invalide": "errors.githubSha",
  "Arbre GitHub tronqué": "errors.githubTree",
  "Objet requis": "errors.objectRequired",
  "Capture introuvable": "errors.screenshotMissing",
  "credential required": "errors.credentialRequired",
  "invalid operator credential": "errors.credentialInvalid",
  "invalid credential": "errors.credentialInvalid",
  "GitHub response too large": "errors.githubTooLarge"
});
function translateServerError(message) {
  return Object.hasOwn(serverErrorKeys, message) ? tr(serverErrorKeys[message]) : message;
}
const labels = {};
function updateLabels() {
  for (const status of ['draft','queued','running','finished','stopped','failed','done']) labels[status] = tr('status.' + status);
}
updateLabels();
let seededTitle = '', seededBrief = '', authenticated = false;
let detailMissionId = null;
let sessionGeneration = 0;
function guardSession(generation) {
  if (generation !== sessionGeneration) throw new DOMException('Obsolete session', 'AbortError');
}
function reportError(error) { if (error.name !== 'AbortError') notice(error.message,true); }
function seedTitle() { return tr('reviewTitle', {project:$('target').selectedOptions[0]?.textContent.split(' · ')[0] || ''}); }
function providerType(type) {
  const key = {Local:'local', local:'local', Abonnement:'subscription', abonnement:'subscription', 'Votre abonnement':'subscription', subscription:'subscription', 'API personnelle':'api', 'Votre API · tarif du fournisseur':'api', api:'api'}[type];
  return key ? tr('type.' + key) : type;
}
function viewState(root) {
  const focus = document.activeElement;
  const path = [];
  if (root.contains(focus)) {
    for (let item = focus; item && item !== root; item = item.parentElement) path.unshift(Array.from(item.parentElement.children).indexOf(item));
  }
  return {open:Array.from(root.querySelectorAll('details[open]')).map(item => item.id).filter(Boolean), path:root.contains(focus) ? path : null};
}
function restoreView(root, state) {
  for (const id of state.open) { const item = $(id); if (item && root.contains(item)) item.open = true; }
  if (state.path) {
    let item = root;
    for (const index of state.path) item = item?.children[index];
    if (item?.focus) item.focus({preventScroll:true});
  }
}
function el(tag, value, cls) { const n = document.createElement(tag); if (value !== undefined) n.textContent = value; if (cls) n.className = cls; return n; }
function notice(value, error = false) { $('notice').textContent = value; $('notice').className = error ? 'error' : ''; }
async function api(path = '', body) {
  const generation = sessionGeneration;
  const r = await fetch('v1/console' + path, {method:body ? 'POST' : 'GET', headers:{Authorization:'Bearer ' + token, 'Accept-Language':AgoraI18n.language, ...(body ? {'Content-Type':'application/json'} : {})}, body:body ? JSON.stringify(body) : undefined}).catch(error => { guardSession(generation); throw error; });
  guardSession(generation);
  const d = await r.json().catch(error => { guardSession(generation); throw error; });
  guardSession(generation);
  if (!r.ok) {
    const message = d.error ? translateServerError(d.error) : tr('connectionUnavailable');
    if (r.status === 401) {
      logout(true);
      $('login').hidden = false;
      const error = el('p',message,'error'); error.id = 'login-error'; error.setAttribute('role','alert');
      if (Object.hasOwn(serverErrorKeys, d.error)) error.dataset.i18n = 'console.' + serverErrorKeys[d.error];
      $('login-form').prepend(error);
      $('login').scrollIntoView({block:'start'});
      $('token').focus({preventScroll:true});
    }
    throw Error(message);
  }
  return d;
}
function logout(preserveLogin = false) {
  sessionGeneration++; token = ''; authenticated = false; busy = false;
  sessionStorage.removeItem('agora-operator'); sessionStorage.removeItem('agora-project');
  notice(''); $('keyfile').value = '';
  $('login-error')?.remove();
  $('workspace').hidden = true; $('welcome').hidden = false; $('login').hidden = true;
  $('back-workspace').hidden = true; $('logout').hidden = true;
  for (const id of ['detail','mission-list','agents','chat-messages','target','project-filter']) $(id).replaceChildren();
  for (const id of ['project-summary','connections-status']) $(id).textContent = '';
  for (const id of ['mission-form','project-form','chat-form']) $(id).reset();
  if (!preserveLogin) $('login-form').reset();
  for (const id of ['create','save-message','save-project']) $(id).disabled = false;
  for (const dialog of document.querySelectorAll('.capture-dialog')) dialog.close();
  selected = detailMissionId = null; projectFilter = 'all'; targets = []; agentLabels = {};
  listSnapshot = detailSnapshot = targetsSnapshot = chatSnapshot = seededTitle = seededBrief = '';
  firstLoad = true; formSeeded = false;
}
async function refresh(force = false) {
  const generation = sessionGeneration;
  const scope = projectFilter;
  const data = await api(scope === 'all' ? '' : '?target=' + encodeURIComponent(scope));
  guardSession(generation);
  if (scope !== projectFilter) return;
  if (!authenticated) { $('login-error')?.remove(); $('welcome').hidden = true; $('login').hidden = true; $('workspace').hidden = false; authenticated = true; }
  $('logout').hidden = false; $('back-workspace').hidden = false;
  agentLabels = Object.fromEntries(data.agents.map(a => [a.id,a.label]));
  $('connections-status').textContent = data.agents.length ? tr('agentsConfigured', {count:data.agents.length}) : tr('agentsNotConfigured');
  if (!$('agents').children.length) for (const a of data.agents) {
    const l = el('label', undefined, 'agent'), c = el('input'), t = el('span', a.label);
    c.type = 'checkbox'; c.value = a.id; c.name = 'agent'; c.checked = ['codex','qwen-coder'].includes(a.id);
    const type = el('small', providerType(a.type)); type.dataset.providerType = a.type;
    t.append(type); l.append(c,t); $('agents').append(l);
  }
  const nextTargets = JSON.stringify(data.targets);
  if (nextTargets !== targetsSnapshot) {
    const previousTarget = $('target').value;
    targetsSnapshot = nextTargets; targets = data.targets;
    $('target').replaceChildren(); $('project-filter').replaceChildren();
    const all = el('option',tr('allProjects')); all.value = 'all'; $('project-filter').append(all);
    for (const t of targets) {
      const option = el('option',t.label + (t.repository ? ' · ' + t.repository : '')); option.value = t.id; $('target').append(option);
      const filter = el('option',t.label); filter.value = t.id; $('project-filter').append(filter);
    }
    if (!targets.some(t => t.id === projectFilter)) projectFilter = 'all';
    $('project-filter').value = projectFilter;
    $('target').value = targets.some(t => t.id === previousTarget) ? previousTarget : projectFilter !== 'all' ? projectFilter : targets[0]?.id || '';
  }
  if (!formSeeded && $('target').selectedOptions.length) {
    seededTitle = seedTitle(); seededBrief = tr('seedBrief');
    if (!$('title').value) $('title').value = seededTitle;
    if (!$('brief').value) $('brief').value = seededBrief;
    formSeeded = true;
  }
  if (firstLoad) { $('compose').open = !data.missions.length; firstLoad = false; }
  const chosen = targets.find(t => t.id === projectFilter);
  $('project-summary').textContent = chosen ? [chosen.repository, chosen.website, chosen.notes].filter(Boolean).join(' · ') || tr('projectContext') : tr('chooseProject');
  $('project-chat').hidden = !chosen;
  if (chosen) {
    const messages = await api('/projects/' + encodeURIComponent(chosen.id) + '/chat');
    guardSession(generation);
    if (scope !== projectFilter) return;
    const nextChat = JSON.stringify([chosen.id,messages]);
    if (chatSnapshot !== nextChat) {
      chatSnapshot = nextChat; $('chat-messages').replaceChildren();
      for (const message of messages) { const entry = el('article',undefined,'turn'); entry.append(el('strong',tr('you')),el('p',message.body,'prewrap')); $('chat-messages').append(entry); }
      if (!messages.length) $('chat-messages').append(el('p',tr('chatEmpty'),'hint'));
    }
  }
  const visible = data.missions.filter(m => projectFilter === 'all' || m.target === projectFilter);
  if (!selected || !visible.some(m => m.id === selected)) { selected = visible[0]?.id || null; detailSnapshot = ''; }
  const snapshot = JSON.stringify([visible, selected, projectFilter]);
  if (force || snapshot !== listSnapshot) {
    const previousListView = viewState($('mission-list'));
    listSnapshot = snapshot; $('mission-list').replaceChildren();
    if (!visible.length) $('mission-list').append(el('p',tr('missionsEmpty'),'empty'));
    for (const m of visible) {
      const b = el('button', undefined, 'mission-card' + (m.id === selected ? ' selected' : ''));
      b.type = 'button'; b.setAttribute('aria-current', m.id === selected ? 'true' : 'false');
      b.append(el('span', labels[m.status] || m.status, 'status'), el('strong', m.title), el('small', tr('calls', {count:m.calls, limit:m.max_calls})));
      b.onclick = () => show(m.id, true); $('mission-list').append(b);
    }
    restoreView($('mission-list'), previousListView);
  }
  if (selected) await show(selected, false, force);
  else {
    const box = $('detail'); box.hidden = false; detailSnapshot = '';
    box.replaceChildren(el('h2',chosen ? chosen.label : tr('noMission')), el('p',tr('projectReady'),'hint'));
  }
}
async function show(id, focus = false, force = false) {
  const generation = sessionGeneration;
  selected = id;
  const m = await api('/' + encodeURIComponent(id)), snapshot = JSON.stringify(m), box = $('detail');
  guardSession(generation);
  if (selected !== id) return;
  if (!force && snapshot === detailSnapshot) { if (focus) focusDetail(); return; }
  const previousView = detailMissionId === id ? viewState(box) : null;
  detailMissionId = id; detailSnapshot = snapshot; box.hidden = false; box.replaceChildren();
  const heading = el('div', undefined, 'detail-head'), title = el('div');
  title.append(el('p', labels[m.status] || m.status, 'eyebrow'), el('h2', m.title));
  const actions = el('div', undefined, 'actions');
  for (const [action, label] of [['start',tr('start')],['stop',tr('stop')]]) {
    if ((action === 'start' && m.status !== 'draft') || (action === 'stop' && !['queued','running'].includes(m.status))) continue;
    const b = el('button', label, action === 'start' ? 'primary' : 'quiet');
    b.onclick = async () => { const generation = sessionGeneration; b.disabled = true; try { await api('/' + id + '/' + action, {}); guardSession(generation); detailSnapshot = ''; await refresh(true); guardSession(generation); notice(action === 'start' ? tr('queuedNotice') : tr('stoppedNotice')); } catch (e) { reportError(e); b.disabled = false; } };
    actions.append(b);
  }
  const download = el('button',tr('export'),'quiet');
  download.onclick = () => { const blob = new Blob([JSON.stringify(m,null,2)], {type:'application/json'}), url = URL.createObjectURL(blob), a = el('a'); a.href = url; a.download = 'agora-' + m.id + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
  actions.append(download); heading.append(title,actions); box.append(heading);
  const target = m.evidence?.repository || targets.find(t => t.id === m.target)?.label || (m.target ? tr('projectUnavailable') : tr('projectNotConnected'));
  box.append(el('p', tr('missionMeta', {project:target, agents:m.agents.map(id => agentLabels[id] || id).join(', '), count:m.calls, limit:m.max_calls, minutes:m.seconds / 60}), 'mission-meta'));
  if (m.decision) box.append(AgoraDecisions.render(m, {agentLabels, onOpenTurn:openTurn}));
  box.append(conversationView(m));
  const answer = [...m.turns].reverse().find(t => t.status === 'done' && ['answer','review','artifact'].includes(t.kind));
  const latest = answer || [...m.turns].reverse().find(t => t.status === 'done');
  const result = el('section', undefined, 'result');
  result.append(el('p', answer ? tr('latestAnswer') : latest ? tr('latestContribution') : tr('missionState'), 'eyebrow'));
  if (latest) {
    result.append(el('h3', tr('contributionBy', {kind:answer ? tr('answer') : latest.kind === 'question' ? tr('questionAsked') : tr('contribution'), agent:agentLabels[latest.agent] || latest.agent})));
    result.append(el('p', latest.body || tr('emptyContribution'), 'result-body'));
  } else {
    const state = m.status === 'draft' ? tr('stateDraft') : m.status === 'queued' ? tr('stateQueued') : m.status === 'running' ? tr('stateRunning') : tr('noAnswer');
    result.append(el('h3', state));
  }
  if (m.error) result.append(el('p', tr('error', {message:translateServerError(m.error)}), 'error'));
  box.append(result);
  box.append(el('p', tr('caveat'), 'caveat'));
  const brief = el('details', undefined, 'section-details'); brief.id = 'mission-brief'; brief.append(el('summary',tr('initialQuestion')),el('p',m.brief,'prewrap')); box.append(brief);
  if (m.evidence) { const evidence = el('details', undefined, 'section-details'); evidence.id = 'mission-evidence'; evidence.append(el('summary',tr('evidence')), evidenceView(m)); box.append(evidence); }
  else box.append(el('p', m.target ? tr('evidencePending') : tr('legacyMission'), 'hint'));
  if (m.turns.length) {
    const conversation = el('details', undefined, 'section-details');
    conversation.id = 'conversation-transcript';
    conversation.append(el('summary',tr('allExchanges', {count:m.turns.length})));
    for (const t of m.turns) {
      const card = el('article',undefined,'turn'), h = el('div',undefined,'turn-heading');
      card.id = 'turn-' + t.id; card.tabIndex = -1;
      const kind = {question:tr('question'),answer:tr('answer'),review:tr('review'),artifact:tr('artifact')}[t.kind] || tr('contribution');
      h.append(el('strong', String(t.ordinal).padStart(2,'0') + ' · ' + kind + ' · ' + t.agent), el('span',labels[t.status] || t.status,'status'));
      card.append(h,el('p',t.body || tr('preparingContribution'),'prewrap')); conversation.append(card);
    }
    box.append(conversation);
  }
  if (previousView) restoreView(box, previousView);
  if (focus) { listSnapshot = ''; focusDetail(); refresh().catch(e => reportError(e)); }
}
function openTurn(turnId) {
  const transcript = $('conversation-transcript'), turn = $('turn-' + turnId);
  if (!transcript || !turn) return;
  transcript.open = true; turn.scrollIntoView({block:'center'}); turn.focus({preventScroll:true});
}
function conversationView(m) {
  const section = el('section',undefined,'conversation-map' + (motionPaused ? ' motion-paused' : ''));
  section.setAttribute('aria-label',tr('whoTalks'));
  const name = id => agentLabels[id] || id;
  const active = m.turns.find(t => t.status === 'running');
  const last = [...m.turns].reverse().find(t => t.status === 'done');
  const failed = [...m.turns].reverse().find(t => t.status === 'failed');
  const current = active || (m.status === 'failed' ? failed : null) || last;
  const moving = Boolean(active && m.status === 'running');
  const heading = el('div',undefined,'conversation-heading');
  heading.append(el('h3',tr('aroundTable')),el('span',moving ? tr('exchangeRunning') : labels[m.status] || m.status,'status'));
  section.append(heading);
  if (moving) {
    const toggle = el('button',motionPaused ? tr('enableMotion') : tr('pauseMotion'),'motion-toggle');
    toggle.type = 'button'; toggle.setAttribute('aria-pressed',String(motionPaused));
    toggle.onclick = () => { motionPaused = !motionPaused; sessionStorage.setItem('agora-motion-paused',String(motionPaused)); section.classList.toggle('motion-paused',motionPaused); toggle.textContent = motionPaused ? tr('enableMotion') : tr('pauseMotion'); toggle.setAttribute('aria-pressed',String(motionPaused)); };
    section.append(toggle);
  }
  let headline, detail;
  if (current) {
    const kind = current.kind || current.expected_kind;
    const recipient = current.recipient;
    const self = recipient === current.agent;
    if (current.status === 'failed') headline = tr('agentFailed', {agent:name(current.agent)});
    else if (active && m.status === 'stopped') headline = tr('agentStopping', {agent:name(active.agent)});
    else if (kind === 'answer') headline = tr(active ? 'answerPreparing' : 'answerReceived', {agent:name(current.agent), recipient:recipient && !self ? name(recipient) : tr('projectRecipient')});
    else if (kind === 'question') headline = tr(active ? 'questionPreparing' : 'questionReceived', {agent:name(current.agent), recipient:recipient && !self ? name(recipient) : tr('nextRoundRecipient')});
    else headline = tr(active ? 'summaryPreparing' : 'contributionReceived', {agent:name(current.agent)});
    detail = active ? tr('responsePending') : current.body;
    const pair = el('div',undefined,'exchange-pair' + (moving ? ' is-live' : ''));
    const participant = (id, label) => {
      const person = el('div',undefined,'exchange-person');
      const avatar = el('span',name(id).slice(0,2).toUpperCase(),'agent-avatar'); avatar.setAttribute('aria-hidden','true');
      person.append(avatar,el('strong',name(id)),el('small',label)); return person;
    };
    pair.append(participant(current.agent,active ? tr('speaking') : current.status === 'failed' ? tr('interrupted') : tr('received')));
    const link = el('div',undefined,'exchange-link'); link.setAttribute('aria-hidden','true'); link.append(el('span',undefined,'exchange-dot'),el('span','→','exchange-arrow')); pair.append(link);
    if (recipient && !self) pair.append(participant(recipient,kind === 'answer' ? tr('questionAuthor') : tr('nextParticipant')));
    else { const project = el('div',undefined,'exchange-person'); project.append(el('span','a','agent-avatar project-avatar'),el('strong',self ? tr('nextTurn') : tr('theProject')),el('small',self ? tr('sameAgent') : tr('sharedSummary'))); pair.append(project); }
    section.append(pair);
  } else {
    headline = m.status === 'queued' ? tr('agentsWaiting') : m.status === 'failed' ? tr('preparationFailed') : m.status === 'stopped' ? tr('stoppedBeforeDiscussion') : tr('teamReady');
    detail = m.status === 'queued' ? tr('runnerPreparing') : tr('discussionPending');
  }
  const summary = el('p',headline,'exchange-headline'); summary.setAttribute('role','status'); section.append(summary);
  section.append(el('p',detail ? detail.slice(0,240) + (detail.length > 240 ? '…' : '') : tr('callNoAnswer'),'exchange-excerpt'));
  const roster = el('div',undefined,'agent-roster');
  for (const id of m.agents) {
    const turns = m.turns.filter(t => t.agent === id), latest = [...turns].reverse().find(t => t.status === 'done');
    const isActive = active?.agent === id && m.status === 'running';
    const button = el('button',undefined,'roster-agent' + (isActive ? ' is-speaking' : ''));
    button.type = 'button'; button.append(el('span',name(id)),el('small',isActive ? tr('speakingNow') : m.next_agent === id ? tr('nextContribution') : turns.some(t => t.status === 'failed') ? tr('callFailed') : latest ? tr('contributions', {count:turns.filter(t => t.status === 'done').length}) : tr('noContribution')));
    if (latest) { button.setAttribute('aria-label',tr('readContribution', {agent:name(id)})); button.onclick = () => openTurn(latest.id); }
    else { button.disabled = true; }
    roster.append(button);
  }
  section.append(roster);
  const exchanges = m.turns.filter(t => t.status === 'done').slice(-3);
  if (exchanges.length) {
    const list = el('ol',undefined,'exchange-history'); list.setAttribute('aria-label',tr('recentExchanges'));
    for (const t of exchanges) {
      const row = el('li'), button = el('button',undefined,'exchange-history-link'); button.type = 'button';
      const kind = {question:tr('question'),answer:tr('answer'),review:tr('summary'),artifact:tr('artifact')}[t.kind] || tr('contribution');
      button.append(el('span',String(t.ordinal).padStart(2,'0'),'exchange-number'),el('span',name(t.agent) + (t.recipient && t.recipient !== t.agent ? ' → ' + name(t.recipient) : tr('projectArrow'))),el('small',kind));
      button.onclick = () => openTurn(t.id); row.append(button); list.append(row);
    }
    section.append(list);
  }
  section.append(el('p',tr('arrowsHint'),'hint'));
  return section;
}
function focusDetail() { const box = $('detail'); box.scrollIntoView({block:'start'}); box.tabIndex = -1; box.focus({preventScroll:true}); }
function evidenceView(m) {
  const e = m.evidence, section = el('div',undefined,'evidence');
  section.append(el('p',e.repository ? tr('repositoryFiles', {repository:e.repository, sha:e.github_sha?.slice(0,12) || tr('notVerified'), count:e.file_count}) : tr('noRepository')));
  const links = el('p',undefined,'evidence-links');
  for (const [label,url] of [[tr('viewCommit'),'https://github.com/' + e.repository + '/commit/' + e.github_sha],[tr('openSite'),e.website]]) {
    if (!url || (label === tr('viewCommit') && !e.github_sha)) continue;
    const a = el('a',label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; links.append(a);
  }
  section.append(links);
  section.append(el('p',e.production_matches_github === true ? tr('productionMatch') : e.production_matches_github === false ? tr('productionMismatch') : tr('productionUnknown'),'hint'));
  section.append(el('p',e.checks.length ? 'CI : ' + e.checks.map(x => x.name + ' ' + (x.conclusion || x.status)).join(' · ') : tr('noChecks'),'hint'));
  section.append(el('p',tr('filesRead', {files:e.files.map(x => x.path).join(', ') || tr('none')}),'hint'));
  const views = el('div',undefined,'evidence-views');
  for (const view of e.browser) {
    const card = el('div',undefined,'evidence-view'); card.append(el('strong',view.viewport + ' px · ' + (view.http_status || view.error || tr('noResponse'))));
    if (view.error) card.append(el('span',tr('captureUnavailable')));
    else {
      card.append(el('span',tr('pageHeadings', {title:view.title || tr('missing'), headings:(view.h1 || []).join(' / ') || tr('missing')})));
      card.append(el('span',tr('pageMetrics', {overflow:view.overflow ? tr('yes') : tr('no'), images:view.brokenImages, errors:view.page_errors.length})));
      if (view.public_link_probe) { const p = view.public_link_probe; card.append(el('span',p.destination_allowed ? tr('linkProbe', {label:p.label, tab:p.tab_reachable ? tr('yes') : tr('no'), enter:p.enter_opened_expected ? tr('yes') : tr('notVerified'), status:p.destination_status || tr('notVerified')}) : tr('linkBlocked', {label:p.label}))); }
      if (view.screenshot) { const b = el('button',tr('viewCapture'),'quiet'); b.onclick = () => showCapture(m.id,view.viewport); card.append(b); }
    }
    views.append(card);
  }
  section.append(views);
  if (e.limitations?.length) {
    const limits = el('ul',undefined,'evidence-limitations');
    for (const line of e.limitations) limits.append(el('li',line));
    section.append(limits);
  }
  section.append(el('p',tr('visualEvidenceHint'),'hint'));
  return section;
}
async function showCapture(id,width) {
  const generation = sessionGeneration;
  try {
    const response = await fetch('v1/console/' + encodeURIComponent(id) + '/evidence/' + width,{headers:{Authorization:'Bearer ' + token}});
    guardSession(generation);
    if (!response.ok) throw Error(tr('captureUnavailable'));
    const blob = await response.blob(); guardSession(generation);
    const url = URL.createObjectURL(blob), dialog = el('dialog',undefined,'capture-dialog'), close = el('button',tr('closeCapture'),'quiet'), img = el('img');
    img.src = url; img.alt = tr('captureAlt', {width}); close.onclick = () => dialog.close(); dialog.append(close,img);
    dialog.addEventListener('close',() => { URL.revokeObjectURL(url); dialog.remove(); }); document.body.append(dialog); dialog.showModal();
  } catch (error) { if (generation === sessionGeneration) reportError(error); }
}
$('logout').onclick = () => logout();
$('chat-form').onsubmit = async e => {
  e.preventDefault(); if (busy || projectFilter === 'all') return;
  const generation = sessionGeneration;
  busy = true; $('save-message').disabled = true;
  try { await api('/projects/' + encodeURIComponent(projectFilter) + '/chat',{body:$('chat-body').value,request_key:crypto.randomUUID()}); guardSession(generation); $('chat-body').value = ''; await refresh(); guardSession(generation); notice(tr('messageSaved')); }
  catch (error) { reportError(error); }
  finally { if (generation === sessionGeneration) { busy = false; $('save-message').disabled = false; } }
};
$('ask-agents').onclick = () => {
  if (!prepareMission()) return;
  $('brief').value = $('chat-body').value.trim() || tr('chatBrief'); $('brief').focus();
};
$('target').onchange = () => { if (!$('title').value || $('title').value === seededTitle) { seededTitle = seedTitle(); $('title').value = seededTitle; } };
$('project-filter').onchange = () => {
  projectFilter = $('project-filter').value; sessionStorage.setItem('agora-project',projectFilter);
  if (projectFilter !== 'all') { $('target').value = projectFilter; $('target').onchange(); }
  selected = null; detailSnapshot = ''; refresh(true).catch(e => reportError(e));
};
$('new-project').onclick = () => { $('project-setup').open = true; $('project-setup').scrollIntoView({block:'start'}); $('project-label').focus({preventScroll:true}); };
function prepareMission() {
  if (!targets.length) {
    $('new-project').click(); notice(tr('firstProject')); return false;
  }
  if (!Object.keys(agentLabels).length) {
    const connections = $('connections') || $('connections-status').closest('details');
    connections.open = true; connections.scrollIntoView({block:'start'});
    connections.querySelector('summary').focus({preventScroll:true});
    notice(tr('connectAgents')); return false;
  }
  if (projectFilter !== 'all') { $('target').value = projectFilter; $('target').onchange(); }
  $('compose').open = true; $('compose').scrollIntoView({block:'start'}); $('target').focus({preventScroll:true});
  return true;
}
$('new-mission').onclick = prepareMission;
$('keyfile').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  if (f.size > 1024) { notice(tr('invalidKeyFile'),true); return; }
  const generation = ++sessionGeneration; authenticated = false;
  try {
    const value = await f.text(); guardSession(generation); token = value.trim();
    await refresh(); guardSession(generation);
    sessionStorage.setItem('agora-operator',token); notice(tr('workspaceOpen'));
  } catch (err) { reportError(err); }
  finally { if (generation === sessionGeneration) e.target.value = ''; }
};
$('login-form').onsubmit = async e => {
  e.preventDefault(); const generation = ++sessionGeneration; authenticated = false; token = $('token').value.trim();
  try {
    await refresh(); guardSession(generation);
    sessionStorage.setItem('agora-operator',token); $('token').value = ''; notice(tr('workspaceOpen'));
  } catch (err) { reportError(err); }
};
$('project-form').onsubmit = async e => {
  e.preventDefault(); if (busy) return; const generation = sessionGeneration; busy = true; $('save-project').disabled = true;
  try {
    const project = await api('/projects',{label:$('project-label').value,repository:$('project-repository').value,website:$('project-website').value,notes:$('project-notes').value});
    guardSession(generation);
    projectFilter = project.id; sessionStorage.setItem('agora-project',project.id);
    targetsSnapshot = ''; selected = null; await refresh(true); guardSession(generation);
    $('target').value = project.id; $('target').onchange();
    $('project-setup').open = false; $('compose').open = true;
    $('compose').scrollIntoView({block:'start'}); $('title').focus({preventScroll:true});
    notice(tr('projectSaved'));
  } catch (err) { reportError(err); }
  finally { if (generation === sessionGeneration) { busy = false; $('save-project').disabled = false; } }
};
$('mission-form').onsubmit = async e => {
  e.preventDefault(); if (busy) return;
  const generation = sessionGeneration;
  const agents = Array.from(document.querySelectorAll('[name=agent]:checked')).map(x => x.value);
  if (!agents.length || agents.length > 4 || Number($('calls').value) < agents.length) { $('compose').open = true; document.querySelector('.advanced').open = true; notice(tr('agentSelectionError'),true); return; }
  busy = true; $('create').disabled = true;
  try {
    const d = await api('',{title:$('title').value,target:$('target').value,brief:$('brief').value,decision_question:$('decision-question').value,agents,max_calls:Number($('calls').value),seconds:Number($('duration').value),request_key:crypto.randomUUID()});
    guardSession(generation);
    projectFilter = $('target').value; sessionStorage.setItem('agora-project',projectFilter);
    selected = d.id; detailSnapshot = ''; await refresh(true); guardSession(generation); $('compose').open = false;
    try { await api('/' + encodeURIComponent(d.id) + '/start',{}); guardSession(generation); detailSnapshot = ''; await refresh(true); guardSession(generation); notice(tr('missionStarted')); }
    catch (startError) { if (startError.name === 'AbortError') throw startError; notice(tr('startFailed', {message:startError.message}),true); }
    guardSession(generation); focusDetail();
  } catch (err) { reportError(err); }
  finally { if (generation === sessionGeneration) { busy = false; $('create').disabled = false; } }
};
document.addEventListener('agora:language', () => {
  updateLabels();
  if (formSeeded) {
    if ($('title').value === seededTitle) { seededTitle = seedTitle(); $('title').value = seededTitle; }
    if ($('brief').value === seededBrief) { seededBrief = tr('seedBrief'); $('brief').value = seededBrief; }
  }
  for (const node of document.querySelectorAll('[data-provider-type]')) node.textContent = providerType(node.dataset.providerType);
  listSnapshot = detailSnapshot = chatSnapshot = targetsSnapshot = '';
  if (token) refresh(true).catch(e => reportError(e));
});
if (token) refresh().catch(e => reportError(e));
setInterval(() => { if (token && !document.hidden && !busy) refresh().catch(e => reportError(e)); },10000);

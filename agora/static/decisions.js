'use strict';

// Authored labels only. Agent assessments and project questions remain unchanged.
AgoraI18n.register({
  en: {
    'decision.heading': 'Decision brief',
    'decision.question': 'The decision to resolve',
    'decision.example': 'Fictional example · no model calls',
    'decision.missionId': 'Mission ID',
    'decision.missionTitle': 'Mission title',
    'decision.missionStatus': 'Mission status',
    'decision.snapshotAt': 'Snapshot generated at (UTC)',
    'decision.status.draft': 'Ready to start',
    'decision.status.queued': 'Queued',
    'decision.status.running': 'Running',
    'decision.status.finished': 'Discussion complete',
    'decision.status.stopped': 'Stopped',
    'decision.status.failed': 'Failed',
    'decision.provisional': 'Provisional · {received} of {total} selected agents have a position',
    'decision.complete': 'Complete · all {total} selected agents have a position',
    'decision.aligned': 'Available positions align',
    'decision.mixed': 'Positions differ',
    'decision.none': 'No comparison yet',
    'decision.latest': 'Latest turn from every selected agent. A missing position is not approval. Positions may change while the mission is running.',
    'decision.proceed': 'Proceed',
    'decision.revise': 'Revise first',
    'decision.insufficient_evidence': 'Insufficient evidence',
    'decision.pending': 'No contribution yet',
    'decision.running': 'Contribution in progress',
    'decision.failed': 'Latest call failed',
    'decision.unstructured': 'No structured position in the latest contribution',
    'decision.noPosition': 'No position available. Do not infer approval from silence or a failed call.',
    'decision.rationale': 'Why this position',
    'decision.nextCheck': 'What could change this / next check',
    'decision.notProvided': 'Not provided',
    'decision.sources': 'Linked source IDs',
    'decision.noSources': 'No linked source IDs. This position is not independent verification.',
    'decision.readTurn': 'Read {agent}’s contribution',
    'decision.disclaimer': 'These are agent assessments, not a vote, a probability or an automatic go/no-go decision. Agreement does not establish truth. Source IDs confirm that a source exists, not that it supports the claim. You decide what to do next.',
    'decision.sharing': 'Contains project content. Review before sharing. Download stays local; nothing is published.',
    'decision.preview': 'Preview the decision brief before downloading',
    'decision.download': 'Download decision brief (.txt)',
    'decision.reportPreview': 'Decision brief plain-text preview'
  },
  fr: {
    'decision.heading': 'Note de décision',
    'decision.question': 'La décision à résoudre',
    'decision.example': 'Exemple fictif · aucun appel de modèle',
    'decision.missionId': 'Identifiant de mission',
    'decision.missionTitle': 'Titre de la mission',
    'decision.missionStatus': 'Statut de la mission',
    'decision.snapshotAt': 'Instantané généré le (UTC)',
    'decision.status.draft': 'Prête à lancer',
    'decision.status.queued': 'En attente',
    'decision.status.running': 'En cours',
    'decision.status.finished': 'Échanges terminés',
    'decision.status.stopped': 'Arrêtée',
    'decision.status.failed': 'Échec',
    'decision.provisional': 'Provisoire · {received} agents choisis sur {total} ont une position',
    'decision.complete': 'Complète · les {total} agents choisis ont une position',
    'decision.aligned': 'Les positions disponibles convergent',
    'decision.mixed': 'Les positions divergent',
    'decision.none': 'Pas encore de comparaison',
    'decision.latest': 'Dernier tour de chaque agent choisi. Une position absente ne vaut pas approbation. Les positions peuvent changer pendant la mission.',
    'decision.proceed': 'Poursuivre',
    'decision.revise': 'Réviser d’abord',
    'decision.insufficient_evidence': 'Preuves insuffisantes',
    'decision.pending': 'Aucune contribution pour le moment',
    'decision.running': 'Contribution en cours',
    'decision.failed': 'Dernier appel échoué',
    'decision.unstructured': 'Aucune position structurée dans la dernière contribution',
    'decision.noPosition': 'Aucune position disponible. Ne déduisez pas une approbation d’un silence ou d’un appel échoué.',
    'decision.rationale': 'Pourquoi cette position',
    'decision.nextCheck': 'Ce qui pourrait changer cette position / prochaine vérification',
    'decision.notProvided': 'Non renseigné',
    'decision.sources': 'Identifiants des sources liées',
    'decision.noSources': 'Aucun identifiant de source lié. Cette position ne constitue pas une vérification indépendante.',
    'decision.readTurn': 'Lire la contribution de {agent}',
    'decision.disclaimer': 'Ces évaluations d’agents ne sont ni un vote, ni une probabilité, ni une décision automatique de lancement. Un accord ne prouve pas la justesse. Les identifiants confirment l’existence d’une source, pas qu’elle étaye l’affirmation. Vous décidez de la suite.',
    'decision.sharing': 'Contient du contenu du projet. Relisez avant de partager. Le téléchargement reste local ; rien n’est publié.',
    'decision.preview': 'Prévisualiser la note de décision avant de la télécharger',
    'decision.download': 'Télécharger la note de décision (.txt)',
    'decision.reportPreview': 'Aperçu de la note de décision en texte brut'
  }
});

window.AgoraDecisions = (() => {
  const verdicts = ['proceed', 'revise', 'insufficient_evidence'];
  const t = (key, params) => AgoraI18n.t('decision.' + key, params);
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function positions(mission) {
    return mission.agents.map(agent => {
      const position = mission.decision.positions.find(item => item.agent === agent);
      if (!position) return {agent, status: 'pending', assessment: null};
      const assessment = position.status === 'done' && verdicts.includes(position.assessment?.verdict) ? position.assessment : null;
      return {...position, assessment};
    });
  }
  function status(position) {
    if (position.assessment) return t(position.assessment.verdict);
    if (position.status === 'done') return t('unstructured');
    return t(['running', 'failed'].includes(position.status) ? position.status : 'pending');
  }
  function summary(mission, items) {
    const received = items.filter(item => item.assessment).length;
    const complete = mission.decision.complete && items.length > 0 && received === items.length;
    return t(complete ? 'complete' : 'provisional', {received, total: items.length});
  }
  function alignment(mission) {
    return t(['aligned', 'mixed'].includes(mission.decision.agreement) ? mission.decision.agreement : 'none');
  }
  function sources(mission, position) {
    const catalogue = new Map(mission.decision.references.map(source => [source.id, source.label]));
    return (position.assessment?.references || []).filter(id => catalogue.has(id)).map(id => '[' + id + '] ' + catalogue.get(id));
  }
  function missionStatus(mission) {
    if (typeof mission.status !== 'string' || !mission.status) return '';
    const translated = ['draft', 'queued', 'running', 'finished', 'stopped', 'failed'].includes(mission.status) ? t('status.' + mission.status) : mission.status;
    return t('missionStatus') + ': ' + translated;
  }
  function buildReport(mission, agentLabels = {}, {isExample = false} = {}) {
    if (!mission.decision) return '';
    const items = positions(mission);
    const lines = [t('heading')];
    if (isExample) lines.push(t('example'));
    if (typeof mission.id === 'string' && mission.id) lines.push(t('missionId') + ': ' + mission.id);
    if (typeof mission.title === 'string' && mission.title) lines.push(t('missionTitle') + ': ' + mission.title);
    if (missionStatus(mission)) lines.push(missionStatus(mission));
    lines.push(t('snapshotAt') + ': ' + new Date().toISOString());
    lines.push('', t('question') + ':', mission.decision.question, '', summary(mission, items), alignment(mission), t('latest'));
    for (const position of items) {
      lines.push('', agentLabels[position.agent] || position.agent, status(position));
      if (position.assessment) {
        lines.push(t('rationale') + ': ' + (position.assessment.rationale || t('notProvided')));
        lines.push(t('nextCheck') + ': ' + (position.assessment.next_check || t('notProvided')));
        const linked = sources(mission, position);
        lines.push(linked.length ? t('sources') + ':\n' + linked.join('\n') : t('noSources'));
      } else lines.push(t('noPosition'));
    }
    lines.push('', t('disclaimer'), '', t('sharing'));
    return lines.join('\n') + '\n';
  }
  function render(mission, {agentLabels = {}, onOpenTurn, isExample = false} = {}) {
    if (!mission.decision) return null;
    const items = positions(mission), section = element('section', undefined, 'decision-room');
    section.setAttribute('aria-label', t('heading'));
    if (isExample) section.append(element('p', t('example'), 'decision-example'));
    section.append(element('p', t('heading'), 'eyebrow'), element('h3', mission.decision.question, 'decision-question'));
    if (missionStatus(mission)) section.append(element('p', missionStatus(mission), 'hint'));
    const state = element('p', summary(mission, items), 'decision-completion');
    state.setAttribute('role', 'status');
    section.append(state, element('p', alignment(mission), 'decision-agreement'), element('p', t('latest'), 'hint'));
    const list = element('ol', undefined, 'decision-positions');
    for (const position of items) {
      const row = element('li'), heading = element('div', undefined, 'decision-position-heading');
      const name = agentLabels[position.agent] || position.agent;
      heading.append(element('h4', name), element('span', status(position), 'decision-verdict'));
      row.append(heading);
      if (position.assessment) {
        const reasons = element('dl', undefined, 'decision-reasons');
        reasons.append(element('dt', t('rationale')), element('dd', position.assessment.rationale || t('notProvided')),
          element('dt', t('nextCheck')), element('dd', position.assessment.next_check || t('notProvided')));
        row.append(reasons);
        const linked = sources(mission, position);
        if (linked.length) {
          row.append(element('p', t('sources'), 'decision-sources-label'));
          const references = element('ul', undefined, 'decision-sources');
          for (const reference of linked) references.append(element('li', reference));
          row.append(references);
        } else row.append(element('p', t('noSources'), 'hint'));
      } else row.append(element('p', t('noPosition'), 'hint'));
      if (position.turn_id && typeof onOpenTurn === 'function') {
        const open = element('button', t('readTurn', {agent: name}), 'quiet decision-read');
        open.type = 'button'; open.onclick = () => onOpenTurn(position.turn_id); row.append(open);
      }
      list.append(row);
    }
    section.append(list, element('p', t('disclaimer'), 'decision-disclaimer'));
    const preview = element('details', undefined, 'decision-export');
    // A stable ID lets the console preserve the disclosure across polling/language changes.
    preview.id = isExample ? 'example-decision-export' : 'mission-decision-export';
    preview.append(element('summary', t('preview')), element('p', t('sharing'), 'hint'));
    const report = buildReport(mission, agentLabels, {isExample});
    const text = element('pre', report, 'decision-report');
    text.tabIndex = 0; text.setAttribute('aria-label', t('reportPreview'));
    const download = element('button', t('download'), 'quiet'); download.type = 'button';
    download.onclick = () => {
      const url = URL.createObjectURL(new Blob([report], {type: 'text/plain;charset=utf-8'}));
      const safeId = typeof mission.id === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(mission.id) ? mission.id : null;
      const link = element('a'); link.href = url; link.download = isExample ? 'agora-example-decision.txt' : safeId ? 'agora-decision-' + safeId + '.txt' : 'agora-decision.txt';
      document.body.append(link);
      try { link.click(); } finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    };
    preview.append(text, download); section.append(preview);
    return section;
  }
  return {render, buildReport};
})();

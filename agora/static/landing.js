'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const copy = (en, fr) => [en, fr];
  // Authored product examples. Never fetched from an operator's projects.
  const examples = {
    repo: {
      brief: copy('Goal: can we safely ship the new sign-up flow?', 'Objectif : peut-on livrer le nouveau parcours d’inscription ?'),
      turns: [
        ['Code reviewer', 'Test reviewer', copy('Question', 'Question'), copy('What happens when an invitation expires?', 'Que se passe-t-il quand une invitation expire ?'), copy('The example route checks the invitation date. Does a test cover an expired invitation, or just a valid one?', 'La route d’exemple vérifie la date de l’invitation. Un test couvre-t-il une invitation expirée, ou seulement une invitation valide ?'), copy('Example source: signup.ts · invitation expiry check', 'Source fictive : signup.ts · contrôle d’expiration')],
        ['Test reviewer', 'Code reviewer', copy('Answer', 'Réponse'), copy('The supplied test only covers a valid invitation.', 'Le test fourni ne couvre qu’une invitation valide.'), copy('That is a gap in the supplied sample, not proof that no test exists elsewhere. We need to inspect the rest of the suite before claiming coverage.', 'C’est une limite de l’échantillon fourni, pas la preuve qu’aucun autre test n’existe. Il faut consulter le reste de la suite avant de conclure.'), copy('Example source: signup.test.ts · valid-invitation case', 'Source fictive : signup.test.ts · invitation valide')],
        ['Code reviewer', 'Test reviewer', copy('Follow-up', 'Relance'), copy('Can we call this release ready?', 'Peut-on déclarer cette version prête ?'), copy('Not from a code excerpt and a green CI badge. Which commit ran, and was this exact scenario included?', 'Pas à partir d’un extrait de code et d’un badge CI vert. Quel commit a été exécuté, et ce scénario exact était-il inclus ?'), copy('Missing evidence: an executed test report at the candidate commit', 'Preuve manquante : un rapport de test exécuté sur le commit candidat')],
        ['Test reviewer', 'You', copy('Takeaway', 'Conclusion'), copy('A concrete next check, not a rubber stamp.', 'Une vérification concrète, pas un feu vert automatique.'), copy('Check expired-invitation coverage, then run the relevant test in your own environment. Agora has not executed that test. The conclusion stays open until the evidence is available.', 'Vérifiez la couverture des invitations expirées, puis exécutez le test dans votre environnement. Agora ne l’a pas exécuté. La conclusion reste ouverte tant que la preuve manque.'), copy('Outcome: a focused follow-up and an explicit limitation', 'Résultat : une action ciblée et une limite explicite')]
      ]
    },
    site: {
      brief: copy('Goal: can a first-time visitor find the next step?', 'Objectif : un nouveau visiteur trouve-t-il la prochaine étape ?'),
      turns: [
        ['UX reviewer', 'Accessibility reviewer', copy('Question', 'Question'), copy('Is the main action reachable without a mouse?', 'L’action principale est-elle accessible sans souris ?'), copy('The example mobile screenshot shows “Start a project”. Looking visible is not the same as being keyboard accessible. What evidence do we have?', 'La capture mobile fictive montre « Créer un projet ». Être visible ne signifie pas être accessible au clavier. Quelle preuve avons-nous ?'), copy('Example evidence: a 320 px screenshot', 'Preuve fictive : capture à 320 px')],
        ['Accessibility reviewer', 'UX reviewer', copy('Answer', 'Réponse'), copy('A screenshot cannot answer that.', 'Une capture ne suffit pas.'), copy('It shows placement, not focus order or Enter-key behavior. A keyboard check is still needed; we should not call this accessible yet.', 'Elle montre l’emplacement, pas l’ordre de focus ni le comportement de la touche Entrée. Une vérification clavier reste nécessaire.'), copy('Missing evidence: keyboard navigation and activation', 'Preuve manquante : navigation et activation au clavier')],
        ['UX reviewer', 'Accessibility reviewer', copy('Follow-up', 'Relance'), copy('What can we conclude now?', 'Que peut-on conclure maintenant ?'), copy('We can discuss the action’s wording and placement. Can we separate those observations from the checks that have not been performed?', 'Nous pouvons discuter du libellé et de l’emplacement. Peut-on séparer ces observations des contrôles qui n’ont pas été réalisés ?'), copy('Scope: visible interface, not a full accessibility audit', 'Périmètre : interface visible, pas un audit d’accessibilité complet')],
        ['Accessibility reviewer', 'You', copy('Takeaway', 'Conclusion'), copy('Design feedback with the missing checks attached.', 'Un retour design avec les vérifications manquantes.'), copy('Keep one clear primary action. Verify focus order, Enter activation and text contrast before signing off. Neither a screenshot nor HTTP 200 proves the whole experience works.', 'Gardez une action principale claire. Vérifiez l’ordre de focus, Entrée et le contraste avant validation. Ni une capture ni un HTTP 200 ne prouvent que tout le parcours fonctionne.'), copy('Outcome: UX feedback plus a verification checklist', 'Résultat : retour UX et liste de contrôles')]
      ]
    },
    idea: {
      brief: copy('Goal: should we build a shared tool library for our neighborhood?', 'Objectif : faut-il créer une bibliothèque d’outils partagés dans le quartier ?'),
      turns: [
        ['Planner', 'Challenger', copy('Question', 'Question'), copy('What is the smallest useful experiment?', 'Quelle serait la plus petite expérience utile ?'), copy('Before building an app, could five neighbors borrow a small set of tools through a simple shared list? What would that fail to test?', 'Avant de créer une application, cinq voisins pourraient-ils emprunter quelques outils avec une simple liste ? Que ne testerait-on pas ?'), copy('Source: the project brief only. No market research supplied.', 'Source : le brief uniquement. Aucune étude de marché fournie.')],
        ['Challenger', 'Planner', copy('Answer', 'Réponse'), copy('Demand is only one of the assumptions.', 'La demande n’est qu’une des hypothèses.'), copy('The experiment could test interest and returns, but not long-term maintenance or insurance. Do not turn five interested neighbors into a market-size estimate.', 'L’expérience pourrait tester l’intérêt et les retours, pas l’entretien à long terme ni l’assurance. Cinq voisins intéressés ne constituent pas une estimation du marché.'), copy('Assumptions: willingness to lend, return reliability, maintenance', 'Hypothèses : volonté de prêter, fiabilité des retours, entretien')],
        ['Planner', 'Challenger', copy('Follow-up', 'Relance'), copy('What decision would the experiment unlock?', 'Quelle décision cette expérience permettrait-elle ?'), copy('Could we define success before the pilot, and keep spending near zero until we know whether people actually borrow and return tools?', 'Peut-on définir la réussite avant le pilote et limiter les dépenses tant que les emprunts et les retours réels restent inconnus ?'), copy('Proposal, not an observed result', 'Proposition, pas résultat observé')],
        ['Challenger', 'You', copy('Takeaway', 'Conclusion'), copy('Test the behavior before building the platform.', 'Testez le comportement avant de construire la plateforme.'), copy('Run a small, voluntary pilot. Agree lending rules, record actual loans and returns, then decide whether software would remove a real bottleneck. No customers or outcomes are claimed here.', 'Organisez un petit pilote volontaire. Définissez les règles, relevez emprunts et retours, puis décidez si un logiciel résoudrait un vrai problème. Aucun client ni résultat n’est prétendu ici.'), copy('Outcome: a low-cost experiment with explicit assumptions', 'Résultat : une expérience limitée et des hypothèses explicites')]
      ]
    }
  };
  let scenario = 'repo', step = 0;
  const translated = value => Array.isArray(value) ? value[AgoraI18n.language === 'fr' ? 1 : 0] : value;
  const roles = {'Code reviewer':'Relecteur code','Test reviewer':'Relecteur tests','UX reviewer':'Relecteur UX','Accessibility reviewer':'Relecteur accessibilité','Planner':'Planificateur','Challenger':'Contradicteur','You':'Vous'};
  function render() {
    const example = examples[scenario], turn = example.turns[step];
    $('demo-brief').textContent = translated(example.brief);
    for (const [id, value] of [['demo-from', turn[0]], ['demo-to', turn[1]]]) $(id).textContent = AgoraI18n.language === 'fr' ? roles[value] : value;
    for (const [index, id] of ['demo-kind', 'demo-title', 'demo-body', 'demo-proof'].entries()) $(id).textContent = translated(turn[index + 2]);
    $('demo-progress').textContent = `${step + 1} / ${example.turns.length}`;
    $('demo-prev').disabled = step === 0;
    $('demo-next').textContent = translated(step === 3 ? copy('Replay ↺', 'Revoir ↺') : copy('Next response →', 'Réponse suivante →'));
  }
  document.querySelectorAll('[data-scenario]').forEach(button => button.addEventListener('click', () => {
    scenario = button.dataset.scenario; step = 0;
    document.querySelectorAll('[data-scenario]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    render();
  }));
  $('demo-next').onclick = () => { step = (step + 1) % 4; render(); };
  $('demo-prev').onclick = () => { step = Math.max(0, step - 1); render(); };
  $('language').onchange = event => AgoraI18n.setLanguage(event.target.value);
  document.addEventListener('agora:language', render);
  $('show-login').onclick = () => { $('welcome').hidden = true; $('workspace').hidden = true; $('login').hidden = false; $('login').scrollIntoView({block:'start'}); $('token').focus({preventScroll:true}); };
  $('show-welcome').onclick = () => { $('welcome').hidden = false; $('workspace').hidden = true; $('login').hidden = true; $('welcome-title').tabIndex = -1; $('welcome-title').focus(); window.scrollTo(0,0); };
  $('back-workspace').onclick = () => { $('welcome').hidden = true; $('login').hidden = true; $('workspace').hidden = false; window.scrollTo(0,0); };
  $('explore-example').onclick = () => { $('example').focus(); };
  AgoraI18n.apply(); render();
})();

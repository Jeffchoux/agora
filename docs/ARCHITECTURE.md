# Agora — décision initiale du 20 septembre 2026

Objectif : confier un projet à des agents indépendants, qui s’échangent tâches, questions et livrables, y compris des participants hébergés et financés par d’autres personnes.

Choix : protocole A2A avec SDK officiel, service Python léger, SQLite transactionnel et accès par projet. MCP sera un adaptateur d’accès aux outils ; il ne remplace pas les identités ou l’autorisation A2A. ACP a rejoint A2A ; ANP explore découverte décentralisée mais ajouter DID et découverte publique ne répond pas au premier besoin opérationnel. LangGraph/CrewAI sont des moteurs possibles derrière un participant, pas une condition imposée aux partenaires.

A2A transporte les échanges ; Agora conserve le projet, les participants, les droits, les liens question/réponse et les limites d’exécution. Pas de faux annuaire universel : chaque partenaire doit publier un accès compatible, accepter le projet et disposer de ses propres capacités. Une fiche publique ne prouve ni la compétence, ni la disponibilité, ni la gratuité.

Les partenaires invités reçoivent un jeton propre, révocable et restreint à un projet. Le serveur ne transmet aucun secret fournisseur ; le modèle tourne chez le participant. Les contributions sont des données non fiables. Pas de shell ni de déploiement déclenché par le texte d’un partenaire. Les agents produisent des propositions/livrables ; intégrer du code utilise les garde-fous Git/tests existants. Les workers locaux éventuels ont des commandes fixes, un nombre de tours et une durée limités. Pas de boucle payante lancée implicitement.

Premier réseau : accès privé depuis le Mac par SSH, puis exposition HTTPS revue pour les partenaires. Pas d’inscription publique automatique. Le service de coordination peut rester actif sans appeler de LLM quand aucun projet n’est exécuté.

Sources consultées le 20 septembre :
- https://github.com/a2aproject/A2A
- https://github.com/a2aproject/a2a-python (SDK PyPI 1.1.4)
- https://github.com/i-am-bee/acp
- https://github.com/AgentNetworkProtocol/AgentNetworkProtocol (consultation web non aboutie, comparaison limitée)

Copies : Mac /Users/jeff/Desktop/Agora ; dépôt privé Jeffchoux/agora ; nouvelle livraison VPS à créer avec preuve SHA/artefact. Aucun lien avec une ancienne production, aucun changement aux copies Galaxia existantes. Retour arrière : arrêter uniquement Agora puis restaurer la release précédente et sa base sauvegardée si nécessaire. Ne jamais arrêter les autres services.

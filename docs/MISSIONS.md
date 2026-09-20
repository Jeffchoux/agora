# Atelier Agora — missions explicites

Console : /agora/ sur le domaine Galaxia. Accès privé par clé opérateur, conservée
uniquement dans sessionStorage jusqu'à déconnexion/fermeture de l'onglet. Aucun
contenu de projet public, aucun jeton de participant ne donne accès à la console.
Clé serveur : fichier600 /home/galaxia/.local/share/agora/operator.key.

La console permet de préparer un brief, sélectionner1à4 agents, fixer1à12 appels
(au moins un par agent), choisir une durée3à30minutes, lancer, arrêter et exporter.
Les agents travaillent successivement, avec les trois dernières contributions.
Les livrables sont du texte ; aucun code proposé n'est exécuté ni déployé.

Un service distinct, agora-runner.service, attend les missions explicitement lancées.
Attente déterministe sans appel LLM ; une seule génération à la fois sur ce serveur.
Les réservations SQLite atomiques comptent les tentatives AVANT l'appel. Aucune
remise à zéro ni reprise implicite après échec/redémarrage. Une mission arrêtée
peut recevoir la réponse de l'appel déjà engagé ; aucun suivant n'est lancé.
Un appel de CLI est tué après120secondes ; le runner exige125secondes restantes
avant d'en démarrer un. Les appels Ollama ont un délai réseau120secondes, qui
n'est pas une garantie de temps CPU du serveur Ollama après déconnexion.

Budget API payante de la console : strictement0USD, obtenu par une liste fermée
Codex ChatGPT, Grok OAuth et modèles Ollama. Impossible de soumettre un endpoint,
une commande, un modèle arbitraire ou une API payante depuis le formulaire.
Ce n'est PAS un plafond de tokens de l'abonnement global, ni de consommation des
applications externes. Les autres profils API manuels restent distincts. Claude
Mac et les APIs déjà raccordées ne sont pas lancés par ce dispatcher VPS.

Le statut « Cycle terminé » signifie plafond atteint, pas qualité validée ni
projet construit automatiquement. Un échec arrête la mission et conserve les
contributions précédentes. Trois missions actives/attente au maximum.

Retour arrière : arrêter agora-runner, revenir à la release précédente avec les
contrôles de provenance. Les tables missions/mission_turns sont additives ; aucune
modification destructive de la base des échanges A2A. Sauvegarder SQLite avant
publication et conserver les profils et la clé opérateur hors Git.

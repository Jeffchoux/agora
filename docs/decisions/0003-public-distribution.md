# 0003 — Distribution publique et accès propres à chaque installation

Décision du 21 septembre 2026 : publier AGORA sous licence MIT, sans identifiants,
sessions, bases privées ou crédit fournisseur. Chaque utilisateur installe sa
propre instance. Une instance neuve démarre sans agent autorisé ni projet privé.
Le mode historique est explicite et réservé à la continuité du serveur existant.

`AGORA_AGENTS_FILE` sélectionne les profils privés, chargés au démarrage de la
console et du runner. Les métadonnées publiques se limitent à l’identifiant,
au libellé et au type d’accès. Les clés restent dans l’environnement ou un
fichier privé. Les API sont permises seulement dans les profils explicitement
autorisés par leur opérateur ; Agora n’applique pas de plafond monétaire.

Les sources d’un projet deviennent facultatives : description seule, dépôt,
site ou combinaison. Les anciens enregistrements sont conservés lors de la
migration SQLite. Chaque discussion accepte 50 messages de 4 000 caractères,
avec clé d’idempotence ; les huit derniers messages alimentent les tours,
avec au plus 1 500 caractères par message transmis.

API ajoutée : GET/POST `/v1/console/projects/{id}/chat`. POST accepte `body` et
`request_key`, retourne `saved: true`. Les routes exigent la clé d’opérateur.
Les erreurs gardent le format `{error: string}`. L’enregistrement d’un message
ne lance aucun modèle. Les réponses d’agents restent regroupées par mission.

Limite assumée : pas de comptes publics ni de séparation entre plusieurs
utilisateurs d’une même console. La publication du code ne rend pas l’instance
privée accessible à tous. Les tokens A2A restent limités au projet invité.

Retour arrière : arrêter le runner, revenir à la release précédente et restaurer
la sauvegarde SQLite préalable si nécessaire. Conserver séparément les nouvelles
données avant restauration. Aucun secret ne dépend du checkout Git.

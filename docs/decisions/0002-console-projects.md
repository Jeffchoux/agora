# 0002 — Projets enregistrés dans la console

Décision du 21 septembre 2026. Agora n’est pas un auditeur BoostMyBiz : ce
projet était seulement la première cible vérifiable. La console enregistre
désormais des projets durables et sélectionne les missions par projet.

## Contrat

- `GET /v1/console` conserve sa réponse existante et ajoute les projets
  enregistrés dans `targets`. `?target=ID` filtre les 100 missions récentes
  du projet, sans retirer les missions historiques sans cible.
- `GET /v1/console/projects` liste les projets.
- `POST /v1/console/projects` accepte `label` (1–80 caractères),
  `repository` (GitHub `owner/repo` ou URL), `website` (URL HTTPS publique
  sans identifiant, paramètre ni port spécial) et `notes` (0–2 000 caractères).
  Il renvoie le projet, ou le projet existant si les mêmes données sont
  soumises. Une paire dépôt/site déjà enregistrée avec d’autres détails est
  refusée. L’accès exige la clé d’opérateur existante.
- `POST /v1/console` conserve son contrat et accepte l’identifiant d’un
  projet enregistré comme `target`. Les missions et preuves anciennes
  restent inchangées.

Les projets enregistrés sont immuables dans cette version ; il n’y a ni édition
ni suppression susceptible de modifier silencieusement une mission en attente.
La table SQLite `console_projects` est additive. Une sauvegarde de la base
active précède son déploiement.

## Contrôles et limites

Le runner ne contacte GitHub et le site qu’après un lancement explicite. Il
lit la branche GitHub par défaut et dix extraits au plus, avec exclusions des
fichiers de secrets/dépendances et plafond de taille. Il ne clone ni n’exécute
le dépôt. Le navigateur accepte uniquement les GET HTTPS sur l’hôte du site,
après rejet des IP privées/réservées et épinglage DNS ; aucun formulaire ni
lien externe n’est activé pour les projets ajoutés. Les ressources CDN sont
bloquées, ce qui peut limiter la fidélité visuelle.

La correspondance commit GitHub / production est inconnue sur les projets
ajoutés : une URL seule ne prouve pas ce lien. BoostMyBiz conserve son manifeste
et sa sonde de lien spécifiques. Aucun fournisseur API payant n’est activé et
le plafond d’appels existant reste appliqué.

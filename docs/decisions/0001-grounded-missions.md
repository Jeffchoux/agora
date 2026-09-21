# Décision 0001 — Missions ancrées dans des preuves

Statut : acceptée le 21 septembre 2026.

## Contexte

La première console Agora faisait converser des agents sur un brief, sans relier la
mission au dépôt ou au site. Une réponse pouvait ainsi paraître être un audit
BoostMyBiz alors qu'aucun agent n'avait vu son code ni son interface.

## Décision

Une mission peut sélectionner un projet explicitement enregistré côté serveur.
Après mise en file, le moteur Agora relève un commit GitHub précis, un échantillon déclaré de
fichiers, les checks de ce commit, la provenance de production lorsqu'elle est
connue et trois observations du site public (320, 768, 1440 px). Les captures
sont privées ; Codex les reçoit comme images, les autres agents reçoivent les
mesures DOM. Toutes les contributions doivent citer une preuve et signaler ce
qui n'a pas été vérifié. Une question du dernier tour appelle une réponse au
tour suivant. L'instantané est conservé avec la mission.

Le premier adaptateur est BoostMyBiz uniquement. Ni URL, ni commande, ni chemin
de fichier fournis par un participant ne deviennent une cible d'inspection.
Le collecteur exécute des commandes fixes de lecture GitHub ; il n'exécute
aucun code du dépôt et n'envoie aucune contribution à un shell. Le navigateur
charge le domaine enregistré et vérifie en GET un lien de repli public vers
un chemin Postpilot précisément autorisé, sans connexion ni soumission de
formulaire. La navigation par Tab et l'activation par Entrée sont relevées.
Aucun agent ne peut publier, fusionner ou déployer depuis Agora.

## Alternatives écartées

- Laisser les agents suivre une URL écrite dans le brief : leurs outils sont
  volontairement désactivés, et une URL non validée serait une surface SSRF.
- Cloner et exécuter les tests du dépôt sur le VPS de production : le code d'un
  commit distant serait exécutable avec les droits du service. Les checks CI
  existants sont relevés, mais ne sont pas présentés comme des tests lancés par
  Agora. Un exécuteur isolé et vérifié serait une décision séparée.
- Ouvrir librement le navigateur des agents : élargirait les accès et rendrait
  les actions issues de prompts non bornées.

## Conséquences et limites

Un résultat « vert » couvre seulement les checks rapportés et les mesures
collectées. Les extraits de code ne couvrent pas tout le dépôt. Les captures
visuelles ne sont vues que par Codex et l'opérateur. Les parcours connectés,
paiements, tests unitaires relancés et modifications de code restent hors de
ce premier incrément. Un échec de collecte marque la mission en échec et
n'appelle aucun modèle. Les anciennes missions sans cible restent lisibles et
sont explicitement marquées comme non vérifiées.

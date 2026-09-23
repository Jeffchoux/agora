# Installer votre propre Agora

## Configuration privée

Après `uv sync --locked --no-build`, lancez `uv run --no-sync python -m agora init`.
Trois fichiers privés sont créés dans `~/.config/agora` : `operator.key` pour
ouvrir votre console, `agents.json` pour vos profils, `credentials.json` pour
vos clés API. Les fichiers existants ne sont pas remplacés. Ne les ajoutez pas
à Git et ne partagez pas la clé de console.

## Choisir les agents

Éditez `agents.json`. Exemple avec un modèle déjà installé dans Ollama et un
Claude CLI déjà connecté à votre propre abonnement :

```json
{
  "local": {"label": "Mon modèle local", "provider": "ollama", "model": "qwen2.5-coder:7b"},
  "claude": {"label": "Mon Claude", "provider": "claude-cli", "model": "haiku", "operator_authorized": true}
}
```

Pour Codex : `provider: "codex-cli"` et le nom d’un modèle disponible pour votre
compte. Pour Grok CLI : `provider: "grok-cli", model: "default"`. Connectez les
CLI sur la machine qui exécute le runner, par leur procédure officielle.
Agora ne copie et ne fournit aucune session d’abonnement. Les profils externes
exigent `operator_authorized: true`, votre autorisation d’utiliser votre accès.
Aucun appel n’est lancé en enregistrant cette configuration.

Exemple d’API dans `agents.json` (adaptez le modèle à votre compte) :

```json
{
  "mistral": {
    "label": "Mon Mistral API",
    "provider": "openai-compatible",
    "model": "mistral-small-latest",
    "endpoint": "https://api.mistral.ai/v1",
    "credential_file": "~/.config/agora/credentials.json",
    "key_env": "MISTRAL_API_KEY",
    "operator_authorized": true
  }
}
```

Dans `credentials.json`, saisissez localement votre clé sous le nom
`MISTRAL_API_KEY`. Ne la mettez ni dans un message de projet ni dans le dépôt.
Conservez les permissions 0600 sur les fichiers et 0700 sur le dossier.
Autre possibilité : une variable d’environnement nommée par `key_env` ; omettez
alors `credential_file`.

Endpoints compatibles : Gemini
`https://generativelanguage.googleapis.com/v1beta/openai`, Groq
`https://api.groq.com/openai/v1`. Utilisez votre modèle et votre clé pour chaque
fournisseur. Vérifiez le plan de votre compte et fixez ses limites chez lui.
Agora limite les appels, pas une facture en euros. Aucun rechargement automatique.

## Console et runner

À la racine du dépôt :

```sh
uv run --no-sync python -m agora start
```

Ouvrez `http://127.0.0.1:8768`. L’accueil est en anglais par défaut ; le sélecteur
permet de choisir le français. Les exemples sont fictifs et n’appellent aucun modèle.
Dans la section d’installation, choisissez « Déjà installé ? Ouvrir cette console »
puis chargez `operator.key` avec le sélecteur de fichier. Il ne s’agit pas d’une clé API.
La console et le moteur des missions fonctionnent dans ce seul terminal, sans
variables à exporter. Sans profil, les exemples et la création de projets restent
accessibles. Aucun fournisseur n’est contacté pour vérifier la configuration.
**Les missions précédemment mises en file d’attente reprennent au démarrage.**

Redémarrez après modification des profils. Ctrl+C ou SIGTERM arrête les nouveaux
tours et attend la fin de l’étape engagée (collecte ou appel modèle), puis libère
le verrou. Cela peut prendre plusieurs minutes et n’annule pas un coût déjà
engagé. Évitez l’arrêt forcé pendant un appel.

Autre dossier privé ou port occupé :

```sh
uv run --no-sync python -m agora start --directory /chemin/prive/agora --port 8769
```

Utilisez d’abord `init` avec le même `--directory`. `start` emploie exclusivement
les fichiers `operator.key`, `agents.json` et `agora.sqlite` de ce dossier, même
si d’anciennes variables AGORA désignent une autre installation. Le mode
historique est désactivé. L’écoute reste sur `127.0.0.1` ; aucune exposition réseau,
aucun remplacement de clés ni arrêt d’un autre service. Lanceur POSIX testé sur
macOS ; Windows non pris en charge.

Les erreurs indiquent quoi vérifier : fichiers privés 0600 et dossier 0700,
profil invalide, port occupé ou moteur déjà actif. Pour deux services supervisés
séparés, les anciennes commandes restent disponibles dans le
[guide détaillé](INSTALL.en.md#advanced-separate-supervised-services).

Pour les dépôts : installez GitHub CLI puis `gh auth login` avec votre compte.
Pour les sites : `uv run --no-sync playwright install chromium`.
Ces outils ne sont pas nécessaires à une discussion sans dépôt ni URL.

## Projets et discussion

Ajoutez un projet et ses sources facultatives, sélectionnez-le puis expliquez
le besoin dans « Parlons du projet ». Les huit derniers messages complètent
le contexte des tours suivants, avec au plus 1 500 caractères par message.
« Préparer une réponse des agents » ouvre le
formulaire : choisissez vos agents puis lancez. Leurs réponses et questions
apparaissent dans la mission, avec l’historique et les preuves disponibles.

## Hébergement et mises à jour

### Aide locale facultative : Laya

Un Mac compatible peut suggérer un angle code, UX ou produit à partir d’une
question courte. Laya n’est pas un agent de discussion et ne lance aucune
mission. Son résultat est expérimental et nécessite votre validation.
Voir le [raccordement privé et ses limites](LAYA.md), y compris lorsque la
console est hébergée sur Linux. Aucun téléchargement de modèle automatique.

Chaque instance possède sa base, ses secrets et ses fournisseurs. Pour héberger
la vôtre, utilisez un compte système dédié, un proxy HTTPS, un stockage privé
et des sauvegardes. La console n’a pas d’isolation par utilisateur : sa clé donne
accès à tous les projets et agents de l’instance. Les participants A2A utilisent
des jetons distincts limités à leur projet.

Avant une mise à jour, arrêtez le runner et sauvegardez SQLite avec son mécanisme
de backup. La migration conserve les projets et missions existants et rend les
sources facultatives. Pour l’installation historique uniquement,
`AGORA_LEGACY_INSTALLATION=1` conserve les anciens profils et le projet initial.
Cette option n’est jamais activée par défaut. `AGORA_AGENTS_FILE` remplace les
profils historiques lorsqu’il est défini. N’exécutez pas les scripts `ops/`
du mainteneur pour installer votre propre serveur.

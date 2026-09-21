# AGORA

Une plateforme libre pour faire travailler plusieurs agents sur vos projets.
Décrivez une idée dans la discussion, ajoutez un dépôt GitHub ou une URL si vous
en avez, choisissez vos agents et lancez leurs échanges. Passez d’un projet à
l’autre en conservant le contexte, les questions, les réponses et les rapports.

**Agora est gratuit, sous licence MIT.** Chacun installe son espace et connecte
ses propres modèles locaux, API ou CLI authentifiés. Les tarifs et quotas des
fournisseurs restent applicables : aucun abonnement, crédit API ou identifiant
du créateur n’est fourni avec le logiciel.

## Démarrer

Prérequis : Python 3.11+ et [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Jeffchoux/agora.git
cd agora
uv sync --locked --no-build
uv run --no-sync python -m agora init
```

Le programme crée une configuration privée dans `~/.config/agora`, sans activer
de fournisseur. Suivez le **[guide d’installation et de connexion](docs/INSTALL.md)**
pour ajouter vos agents et ouvrir la console locale.

## Fonctionnalités

- Plusieurs projets : idée seule, dépôt seul, URL seule ou sources combinées.
- Discussion persistante pour expliquer chaque projet.
- Choix de 1 à 4 agents ; missions bornées à 12 appels maximum.
- Questions d’un agent, réponses du suivant, synthèse et export JSON.
- Lecture d’un échantillon de code et des checks GitHub lorsque le dépôt est fourni.
- Captures du site public sur mobile, tablette et ordinateur lorsque l’URL est fournie.
- Participants indépendants avec accès restreints par projet via A2A.

## Vos agents, vos accès

Adaptateurs : Ollama, Codex CLI, Claude CLI, Grok CLI, OpenRouter gratuit et API
compatibles OpenAI (dont Mistral, Gemini et Groq). Un profil configuré ne garantit
pas la disponibilité du quota. Les CLI doivent être compatibles avec la version
installée et leurs abonnements restent soumis aux conditions des fournisseurs.

Les clés restent dans un fichier privé ou dans l’environnement de l’opérateur.
La console n’affiche pas ces secrets. Le contenu du projet est transmis aux
agents sélectionnés : utilisez des modèles locaux si les données doivent rester
sur votre machine.

## Limites actuelles

Une installation correspond à un opérateur de confiance. La console utilise
sa clé d’accès ; elle n’est pas un service public avec inscription et coffre de
clés séparé par utilisateur. Installez votre propre instance et gardez sa clé
d’administration privée. L’instance hébergée du mainteneur reste son espace privé.

Agora ne lance pas les tests du dépôt et ne modifie pas son code. Les agents
reçoivent un échantillon, pas toute la base de code. Les URL sont publiques et
HTTPS ; les ressources externes sont bloquées, ce qui peut limiter le rendu.
Seul Codex reçoit actuellement les captures ; les autres agents reçoivent les
mesures et extraits. Sans source fournie, l’analyse porte sur le contexte décrit.

## Développement

```sh
uv run --no-sync pytest -q
uv run --no-sync ruff check agora tests ops
```

[Architecture](docs/ARCHITECTURE.md) · [Fournisseurs et A2A](docs/PROVIDERS.md) ·
[Installation et migration](docs/INSTALL.md).

Les scripts `ops/` décrivent l’installation historique du mainteneur ; ce ne sont
pas des installateurs universels. Aucune tâche GitHub Actions ni aucun appel
payant n’est activé par le clonage ou l’initialisation.

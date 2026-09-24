# Models & connections / Modèles et connexions

## English

Open **Models & connections** in the navigation, before or after signing in.
Search by provider or model family; filter API, subscription/CLI, local or
adapter-needed routes. Select routes and enter **exact model IDs, one per line**,
from the linked official provider catalogue. Multiple models from one provider
become separate agents. The directory is extensible, not an exhaustive list of
every model or a live statement of account availability.

Download the key-free selection, then on **your runner machine**, from the Agora
repository, import the downloaded file (adjust its path):

```sh
uv run --no-sync python -m agora import-agents ~/Downloads/agora-agents.json --authorize-external
```

Run `init` first for a new installation. Add `--directory /your/private/agora`
when using a non-default installation; the default credential-file reference is
adapted to that directory. The directory must be private (0700), owned by you,
without symlinks; `agents.json` must be private (0600). The source download has
no key values and need not be private. Do not publish your account-specific IDs.

The import makes no model calls. It rejects duplicate profile IDs, malformed
profiles, unsafe destination files and more than 32 total profiles. It merges
atomically without replacing existing agents or editing credentials. To import
additional models later, give their profile IDs unique names in the JSON export.
The `--authorize-external` flag is your explicit consent to subsequent use of
external providers; exported profiles cannot grant that consent on their own.
For an all-local selection, omit the flag.

For APIs, put your own keys under the displayed names (`ANTHROPIC_API_KEY`,
`MISTRAL_API_KEY`, etc.) in the runner's private `credentials.json` (0600).
For subscriptions, sign in using the supported official CLI **on the runner**.
Agora never imports browser cookies, copies subscriptions or offers maintainer
credentials. Restart Agora, choose the imported profiles in a mission, set its
call limit and start it to check real access. That check can consume your quota
or incur provider charges. No automatic connection test runs during import.

### Compatibility is not a promise of universal access

- API keys and consumer chat subscriptions are separate products. Only supported
  subscription CLI routes can use their own eligible signed-in accounts.
- API plans may have free allowances or be paid. Check your own provider billing
  controls. No blanket "free" claim or automatic upgrade is made. The separate
  OpenRouter free route requires `:free` and checks zero input/output token price
  at call time; it does not promise capacity.
- The existing Chat Completions adapter sends `max_tokens: 512` and
  `response_format: {"type":"json_object"}`. **Choose models supporting both.**
  Some reasoning models require other parameters or more tokens and will fail.
  A compatible endpoint does not establish every model's compatibility.
- Anthropic uses its native Messages adapter; see [its limits](ANTHROPIC.md).
  Ollama must already have a local model supporting structured output.
- Gemini CLI, Perplexity, AI21, Bedrock, Vertex, Azure, LM Studio and Z.ai Coding
  Plan are visible as **adapter needed**, not selectable integrations. This does
  not imply their services are unavailable, only that this route is not delivered.
- Custom HTTPS routes are advanced, operator-owned configurations. Use only a
  trusted endpoint. It receives your selected project context and API key.
  Alibaba endpoints depend on workspace and region; follow its official docs.
- Model names are not guessed or frozen into a supposedly complete dropdown.
  Provider docs are linked; model lists can differ by account and region.
  Automatic authenticated model discovery is **not implemented** yet.
- The public catalogue never reads installation profiles, requests a key or
  contacts providers. It only produces a local configuration download. It is
  not a public multi-user credential vault or a one-click OAuth connection.

Sources and review date live with each entry in
[`providers.json`](../agora/static/providers.json). Browser/transport tests use
fixtures; no paid provider call establishes live model compatibility in this release.

## Français

Ouvrez **Modèles & connexions**, recherchez un fournisseur ou une famille de
modèles, puis cochez les accès souhaités. Indiquez les identifiants exacts des
modèles de votre compte, un par ligne. Téléchargez la sélection sans clés et
importez-la avec la commande ci-dessus **sur la machine du runner**.

Pour une nouvelle installation, exécutez d'abord `init`. `--directory` permet
de choisir un autre dossier privé ; la référence au fichier de clés par défaut
est alors adaptée. L'import refuse les doublons et conserve les profils
existants. Pour ajouter d'autres modèles plus tard, attribuez-leur des
identifiants de profil uniques dans le JSON. Les fichiers privés restent en
0600, leur dossier en 0700, sans liens symboliques.

Ajoutez vos clés dans votre `credentials.json` privé, sous les noms indiqués,
ou connectez le CLI officiel à votre abonnement éligible. Redémarrez Agora ;
les profils apparaissent dans le choix des agents de mission. Lancez une
mission bornée pour vérifier réellement l'accès ; cette action peut consommer
votre quota ou être facturée. L'import n'appelle aucun modèle.

Le catalogue distingue **API**, **abonnement/CLI**, **local** et **adaptateur à
développer**. Il n'est ni exhaustif ni une garantie d'accès. Un abonnement chat
ne finance pas automatiquement son API. La gratuité dépend de votre compte ;
aucune clé ou session du mainteneur n'est fournie. La compatibilité Chat
Completions exige ici `max_tokens` et `json_object` ; certains modèles ne les
acceptent pas. Les modèles disponibles par compte ne sont pas découverts
automatiquement : consultez les liens officiels. Aucun appel API payant n'a
été utilisé pour tester cette livraison.

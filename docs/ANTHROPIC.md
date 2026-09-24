# Anthropic models / Modèles Anthropic

## English

Two independent connections, with no automatic fallback:

- **Subscription**: `claude-cli` uses your existing Claude Code login on the
  runner's machine. Create profiles with `model: "haiku"`, `"sonnet"`, `"opus"`
  or another model ID accepted by your CLI and account. Max needs no API key.
- **API**: `anthropic` uses the official Messages API, billed separately from
  Max/Pro. Any model ID can be configured, subject to account availability and
  compatibility with text Messages requests. No hardcoded model allowlist.

Add a profile to your private `agents.json` (merge with existing profiles):

```json
{
  "claude-api": {
    "label": "Claude Haiku · Anthropic API",
    "provider": "anthropic",
    "model": "claude-haiku-4-5",
    "credential_file": "~/.config/agora/credentials.json",
    "key_env": "ANTHROPIC_API_KEY",
    "operator_authorized": true
  }
}
```

Store your key in the private `credentials.json` under `ANTHROPIC_API_KEY`,
permissions0600. Never put keys in Git or project messages. Alternatively omit
`credential_file` and set `ANTHROPIC_API_KEY` in the runner environment.
Create multiple profiles to select multiple Claude models in one mission; they
may share the same private key. Restart Agora after editing profiles. The console
labels API agents separately from subscription agents. Saving profiles calls no
model and does not validate account access.

The adapter uses only `https://api.anthropic.com/v1/messages`, not Bedrock,
Vertex or proxies. Text contributions only, no image or remote tool execution.
Output limit1024tokens by default; optional `max_tokens` accepts1–16384 to allow
more output/reasoning at the operator's expense. Deadline120seconds; invalid or truncated contributions
fail without retries or model changes. Thinking blocks are not published.
An accepted model ID does not prove every model will work within these limits.
The tests use mock HTTP responses, not a paid API account. Validate your own
mission after accepting provider costs; Agora is not a monetary spending cap.

## Français

Pour votre **abonnement Max**, utilisez `provider: "claude-cli"`, avec votre
connexion Claude Code sur la machine du runner. Les alias `haiku`, `sonnet`,
`opus` ou un identifiant accepté par le CLI et votre compte permettent plusieurs
profils. Aucune clé API nécessaire ; aucune session copiée vers le VPS.

Pour l'**API Anthropic**, utilisez le profil ci-dessus : `provider: "anthropic"`,
un identifiant de modèle de votre choix et votre propre clé dans le fichier privé
`credentials.json` sous `ANTHROPIC_API_KEY` (permissions0600). L'API est facturée
séparément de Max/Pro. Plusieurs profils peuvent partager la clé et utiliser des
modèles différents. Fusionnez les profils dans votre configuration existante,
puis redémarrez Agora pour les sélectionner dans les missions.

Pas de liste figée, ni de promesse d'accès à un modèle retiré ou indisponible.
Messages texte uniquement, limite1024tokens par défaut et120secondes. Le champ
facultatif `max_tokens` accepte1–16384 pour réserver davantage de sortie ou de
raisonnement, avec coût potentiel supplémentaire. Sans image ni outil
distant. Une réponse tronquée ou invalide échoue ; les blocs de raisonnement ne
sont pas affichés. Aucun proxy/Bedrock/Vertex, aucune relance ou bascule vers un
autre modèle, compte ou mode de facturation. Les tests sont hors ligne : une
validation réelle reste à effectuer avec votre compte après acceptation du coût.
Enregistrer un profil ne déclenche aucun appel. Agora n'impose pas de plafond
monétaire chez le fournisseur.

## Official references / Références officielles

- [Model catalogue](https://platform.claude.com/docs/en/models/overview)
- [Models available to an API account](https://platform.claude.com/docs/en/api/models/list)
- [Messages API](https://platform.claude.com/docs/en/api/messages/create)

Checked2026-09-24. Choose IDs from the current catalogue, not a stale example.

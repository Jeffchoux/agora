# Laya: optional local review-focus suggestions

Laya reads a short question and suggests **code**, **UX**, or **product** focus.
It is not an extra chat agent. It does not inspect your repository, browse your
site, validate an answer, select providers, or start a mission. No paid API is
used by this helper. Your selected agents retain their own costs and quotas.

## Use it

Once configured, open a new mission and enter a question of 10–1,200 characters.
Choose **Suggest review focus · Laya**. Review the result and, if useful, click
**Add this focus to my question**. Choose your agents and explicitly start your
mission as usual. Your full question remains unchanged until you accept.
If the helper is unavailable, continue without it. No hidden fallback calls.

The model can misunderstand intent, especially negations. A suggestion is not
an evidence-backed conclusion. Longer questions or token-heavy content may be
rejected; Agora will not silently truncate them. Suggestions are not saved
unless you accept the guidance and later save/start your mission.

## Configure on a compatible Mac

Requires an existing, verified [laya-coreml](https://github.com/mizorewww/laya-coreml)
installation and a local general-purpose multilingual model with a 1,024-token
context. The tested package is `laya-coreml==0.1.0` with CPU compute. A 96-token
ANE export is not supported by this integration. Agora does not install or
download weights, and never enables unvalidated GPU execution.

Create a **dedicated** random bridge secret in a private folder. Do not reuse
your console key or a provider key. Keep the secret file owned by your user,
mode 0600, not a symlink, and outside Git. For example, create a new file with
`openssl rand -hex -out /absolute/private/path/laya.key 32` under `umask 077`.
Do not run that command over an existing configured key.

From the Agora checkout, use the Python interpreter of the existing Laya
environment, rather than installing Core ML in Agora's server environment:

```sh
/path/to/laya/python -m agora.laya_service \
  --model-dir /absolute/path/to/local/model \
  --token-file /absolute/private/path/laya.key
```

The helper listens only on `127.0.0.1:18769`. In another terminal, configure
the Agora **web process** with `AGORA_LAYA_TOKEN_FILE` pointing at that file
before startup. The normal mission runner needs no change. No inference occurs
until an authenticated operator presses the suggestion button.

## Agora hosted on Linux, Laya running on your Mac

Core ML does not run on the Linux host. Copy only the dedicated bridge secret
to a private file owned by Agora's server user (0600), over your authenticated
SSH connection. Set `AGORA_LAYA_TOKEN_FILE` on the web process to that server
path. Keep the helper running on your Mac, then open a private reverse tunnel:

```sh
ssh -N -T -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 127.0.0.1:18769:127.0.0.1:18769 your-user@your-server
```

Verify `GatewayPorts no` in your server's SSH configuration and that the remote
listener is `127.0.0.1:18769`, not `0.0.0.0` or `::`. Do not expose this port
through a public proxy or firewall. No browser-to-Mac connection or CORS change
is needed. Use the operating system's supervisor if you want the helper and
tunnel to reconnect after login; neither should run scheduled predictions.
The Mac must be awake and connected for suggestions to work.

Agora stops waiting after 15 seconds. That bounds the web request, not native
Core ML execution: if inference hangs, restart the dedicated Mac helper.
The rest of Agora does not depend on it.

To disable, unset `AGORA_LAYA_TOKEN_FILE`, restart Agora's web process, and stop
only the dedicated helper/tunnel. Existing missions and agents are unaffected.

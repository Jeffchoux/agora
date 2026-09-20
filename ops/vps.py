"""Deployment adapter for the new Agora service only; SSH never carries provider keys."""

import json
import subprocess
import sys
from pathlib import Path

HOST = "galaxia@188.34.188.200"
ROOT = "/home/galaxia/agora"
STATE = "/home/galaxia/.local/share/agora"
REPO = "jeffchoux/agora"


def command(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def inspect():
    script = """import json,pathlib,urllib.request
root=pathlib.Path('/home/galaxia/agora')
marker=pathlib.Path('/home/galaxia/.local/share/agora/deployment.json')
service=pathlib.Path('/etc/systemd/system/agora.service')
if not root.exists() and not marker.exists() and not service.exists():
 print(json.dumps({'state':'EMPTY','head':None,'evidence':'No release root, deployment manifest or system service exists'}))
else:
 data=json.loads(marker.read_text())
 health=json.load(urllib.request.urlopen('http://127.0.0.1:8768/health',timeout=5))
 assert health['source_sha']==data['source_sha']
 assert data['repository']=='jeffchoux/agora'
 current=root.joinpath('current').resolve()
 assert current.name==data['source_sha']
 import hashlib,subprocess
 tree=subprocess.check_output(['git','-C',str(current),'rev-parse','HEAD'],text=True).strip()
 assert tree==data['source_sha']
 assert not subprocess.check_output(['git','-C',str(current),'status','--porcelain','--untracked-files=no'],text=True).strip()
 print(json.dumps({'state':'READY','head':tree,'deployment':data['deployed_at'],'evidence':'health + active release + clean tracked Git tree'}))
"""
    data = json.loads(
        command(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                HOST,
                "python3 -",
            ],
            input=script,
        )
    )
    data.update(
        id="vps:agora", repo=REPO, name="Agora", kind="vps", aliases=[], url=None
    )
    return data


def deploy():
    root = Path(__file__).resolve().parents[1]
    sha = command(["git", "rev-parse", "HEAD"], cwd=root)
    current = inspect()
    github = json.loads(command(["gh", "api", "repos/Jeffchoux/agora/branches/main"]))[
        "commit"
    ]["sha"]
    if github != sha:
        raise RuntimeError("Only current GitHub main may deploy")
    if current["state"] == "READY":
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", current["head"], sha],
            cwd=root,
            check=True,
        )
    elif current["state"] != "EMPTY":
        raise RuntimeError("Unknown production state")
    # No tar of untracked local files or credentials. VPS fetches the exact verified Git commit.
    remote = f"""set -eu
mkdir -p {ROOT}/releases {STATE}
chmod 700 {STATE}
if [ ! -d {ROOT}/releases/{sha} ]; then
 git clone --quiet https://github.com/Jeffchoux/agora.git {ROOT}/releases/{sha}
fi
cd {ROOT}/releases/{sha}
git checkout --quiet --detach {sha}
$HOME/.local/bin/uv sync --locked --no-build --python 3.12
$HOME/.local/bin/uv run --no-sync pytest -q --disable-warnings
"""
    subprocess.run(["ssh", HOST, "sh -s"], input=remote, text=True, check=True)
    # Narrow administration: install reviewed unit, no other services touched.
    subprocess.run(
        [
            "scp",
            str(root / "ops/agora.service"),
            "root@188.34.188.200:/etc/systemd/system/agora.service",
        ],
        check=True,
    )
    prior = command(["ssh", HOST, "readlink " + ROOT + "/current || true"])
    try:
        subprocess.run(
            ["ssh", HOST, f"ln -sfn {ROOT}/releases/{sha} {ROOT}/current"], check=True
        )
        subprocess.run(
            [
                "ssh",
                "root@188.34.188.200",
                "systemctl daemon-reload && systemctl enable --now agora.service && systemctl restart agora.service",
            ],
            check=True,
        )
        script = f"""import json,time,urllib.request,pathlib,os,datetime
for i in range(30):
 try:
  r=json.load(urllib.request.urlopen('http://127.0.0.1:8768/health',timeout=2))
  if r['source_sha']=='{sha}':break
 except Exception:pass
 time.sleep(1)
else:raise RuntimeError('deployment health not verified')
p=pathlib.Path('{STATE}/deployment.json')
t=p.with_suffix('.tmp');t.write_text(json.dumps({{'source_sha':'{sha}','repository':'{REPO}','deployed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}}));os.replace(t,p)
"""
        subprocess.run(["ssh", HOST, "python3 -"], input=script, text=True, check=True)
    except Exception:
        if prior:
            subprocess.run(
                ["ssh", HOST, "ln -sfn " + prior + " " + ROOT + "/current"], check=True
            )
            subprocess.run(
                ["ssh", "root@188.34.188.200", "systemctl restart agora.service"],
                check=True,
            )
        else:
            subprocess.run(
                ["ssh", "root@188.34.188.200", "systemctl stop agora.service"],
                check=False,
            )
        raise
    subprocess.run(
        [
            "scp",
            str(root / "ops/install_route.py"),
            "root@188.34.188.200:/root/agora-install-route.py",
        ],
        check=True,
    )
    subprocess.run(
        ["ssh", "root@188.34.188.200", "python3 /root/agora-install-route.py"],
        check=True,
    )
    print(json.dumps(inspect()))


if __name__ == "__main__":
    if sys.argv[1:] == ["inspect"]:
        print(json.dumps(inspect()))
    elif sys.argv[1:] == ["deploy"]:
        deploy()
    else:
        raise SystemExit("use inspect or deploy")

"""Ops console: a fixed lookup table of read-only outputs. Nothing is ever executed."""

DENIED = "permission denied"
PROCESSES = (
    "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
    "svc-hla+       1  0.4  1.9 412336 98112 ?        Ssl  Oct04 192:11 uvicorn app.main:app --port 8000\n"
    "svc-hla+      27  0.0  0.1   7236  3912 pts/0    Ss   22:40   0:00 /bin/sh\n"
    "svc-hla+      41  0.0  0.1  10884  4232 pts/0    R+   22:41   0:00 ps aux"
)


def outputs(node: str) -> dict[str, str]:
    return {
        "help": "available: whoami id hostname pwd uname -a uptime date ls ls -la ls config "
                "cat config/app.yaml cat /etc/os-release df -h free -m ps aux",
        "whoami": "svc-hlabs",
        "id": "uid=1001(svc-hlabs) gid=1001(svc-hlabs) groups=1001(svc-hlabs)",
        "hostname": node,
        "pwd": "/srv/hlabs",
        "uname -a": f"Linux {node} 6.8.0-49-generic #49-Ubuntu SMP PREEMPT_DYNAMIC Mon Oct 21 10:42:14 UTC 2026 "
                    "x86_64 x86_64 x86_64 GNU/Linux",
        "uptime": " 22:41:07 up 41 days,  3:12,  0 users,  load average: 0.42, 0.38, 0.35",
        "date": "Sat Nov 14 22:41:07 UTC 2026",
        "ls": "app  config  logs  requirements.txt  static  templates",
        "ls -la": "total 32\n"
                  "drwxr-xr-x 1 svc-hlabs svc-hlabs 4096 Nov 12 03:14 .\n"
                  "drwxr-xr-x 1 root      root      4096 Nov 12 03:14 ..\n"
                  "-rw------- 1 root      root       812 Nov 12 03:14 .env\n"
                  "drwxr-xr-x 1 svc-hlabs svc-hlabs 4096 Nov 12 03:14 app\n"
                  "drwxr-xr-x 1 svc-hlabs svc-hlabs 4096 Nov 12 03:14 config\n"
                  "drwxr-xr-x 1 svc-hlabs svc-hlabs 4096 Nov 14 00:00 logs\n"
                  "-rw-r--r-- 1 svc-hlabs svc-hlabs  214 Nov 12 03:14 requirements.txt\n"
                  "drwxr-xr-x 1 svc-hlabs svc-hlabs 4096 Nov 12 03:14 static\n"
                  "drwxr-xr-x 1 svc-hlabs svc-hlabs 4096 Nov 12 03:14 templates",
        "ls config": "app.yaml  logging.yaml",
        "cat config/app.yaml": "service: hlabs-web\n"
                               "listen: 0.0.0.0:8000\n"
                               "database:\n  host: db-primary.internal\n  name: hlabs\n  pool: 10\n"
                               "storage:\n  bucket: hlabs-model-artifacts\n  region: us-east-2\n"
                               "backups:\n  host: backup-01\n  schedule: \"0 3 * * *\"\n"
                               "registry:\n  host: model-vault\n",
        "cat /etc/os-release": 'PRETTY_NAME="Ubuntu 24.04.1 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\n'
                               'VERSION="24.04.1 LTS (Noble Numbat)"\nID=ubuntu\nID_LIKE=debian',
        "df -h": "Filesystem      Size  Used Avail Use% Mounted on\n"
                 "overlay         124G   61G   58G  52% /\n"
                 "tmpfs            64M     0   64M   0% /dev\n"
                 "/dev/nvme0n1p1  124G   61G   58G  52% /srv/hlabs/logs\n"
                 "shm              64M     0   64M   0% /dev/shm",
        "free -m": "               total        used        free      shared  buff/cache   available\n"
                   "Mem:           15991        6120        1874          12        7996        9531\n"
                   "Swap:              0           0           0",
        "ps": PROCESSES,
        "ps aux": PROCESSES,
    }


def run(command: str, node: str) -> str:
    normalized = " ".join(command.split())
    if not normalized:
        return ""
    return outputs(node).get(normalized, f"sh: {normalized.split()[0]}: {DENIED}")

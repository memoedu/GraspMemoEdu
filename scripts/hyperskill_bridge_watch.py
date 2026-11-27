"""Check the local bridge quietly, using its original starter for recovery."""
from contextlib import closing
from datetime import datetime
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

try:
    import psutil
except ImportError:
    psutil = None


def read_health(origin):
    with closing(HTTPConnection("127.0.0.1", 18769, timeout=2)) as connection:
        connection.request("POST", "/health", body=b"{}", headers={
            "Origin": origin, "X-Grasp-Local": "1", "Content-Type": "application/json",
        })
        reply = connection.getresponse()
        if reply.status != 200:
            return {}
        body = reply.read(4097)
        return json.loads(body) if len(body) <= 4096 else {}


def already_running(config_path):
    if psutil is None:
        return False
    try:
        config_path = config_path.resolve(strict=True)
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if config["port"] != 18769:
            return False
        runtime = config_path.parent
        marker = json.loads((runtime / "bridge-instance.json").read_text(encoding="utf-8-sig"))
        saved_pid = int((runtime / "bridge.pid").read_text(encoding="utf-8-sig").strip())
        health = read_health(config["origins"][0])
        if (health["ready"] is not True or health["provider"] != "hyperskill"
                or not re.fullmatch(r"[0-9a-f]{32}", health["instance_id"])
                or health["instance_id"] != marker["instance_id"]
                or health["pid"] != marker["pid"] or health["pid"] != saved_pid):
            return False
        process = psutil.Process(saved_pid)
        with process.oneshot():
            command = process.cmdline()
            script = Path(__file__).with_name("hyperskill_bridge.mjs").resolve(strict=True)
            node = shutil.which("node.exe")
            # CIM stores the creation timestamp to microseconds; psutil returns float seconds.
            born = datetime.fromisoformat(marker["started_at"]).timestamp()
            return (len(command) == 3 and node is not None
                    and Path(process.exe()).resolve() == Path(node).resolve()
                    and Path(command[1]).resolve() == script
                    and Path(command[2]).resolve() == config_path
                    and abs(process.create_time() - born) <= 0.000002
                    and process.is_running())
    except (psutil.Error, OSError, ValueError, KeyError, IndexError, TypeError, HTTPException):
        return False


def main(config_path, starter, powershell):
    if already_running(Path(config_path)):
        return 0
    # The existing hidden task owns the process tree and its startup timeout.
    return subprocess.call([powershell, "-NoLogo", "-NoProfile", "-NonInteractive",
                            "-WindowStyle", "Hidden", "-File", starter, "-ConfigPath", config_path],
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))

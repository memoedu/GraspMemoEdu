"""Root-only existing-host release step; invoked through managed run-stage."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

if __package__:
    from .release_academy_production import wait_for_health
else:
    from release_academy_production import wait_for_health


def main():
    stage = Path(sys.argv[1]).resolve()
    if os.geteuid() != 0 or stage.parent != Path('/tmp') or not stage.name.startswith('graspmemoedu-ma-') or stage.is_symlink():
        raise ValueError('Use the configured root release wrapper and exact staging path')
    data = Path('/var/lib/graspmemoedu')
    pointer = data / 'active-content.json'
    before = pointer.read_bytes() if pointer.exists() else None
    with tarfile.open(stage / 'package.tar.gz', 'r:gz') as archive:
        for member in archive.getmembers():
            target = (stage / member.name).resolve()
            if not target.is_relative_to(stage / 'package') or not (member.isfile() or member.isdir()):
                raise ValueError('Invalid prepared package member')
        archive.extractall(stage, filter='data')
    subprocess.run(['chown', '-R', 'graspmemoedu:graspmemoedu', str(stage / 'package')], check=True)
    manifest = json.loads((stage / 'package/manifest.json').read_text(encoding='utf-8'))
    module = 'graspmemoedu.mathacademy_graphics' if manifest.get('kind') == 'mathacademy-inline-graphics' else 'graspmemoedu.mathacademy_import'
    # Enrichment checks that the selected Topics have no existing learner rows.
    # Quiesce writers for that check. Additions and graphics can install online.
    quiesce = manifest.get('kind') == 'mathacademy-practice-enrichment'
    if quiesce:
        subprocess.run(['runuser', '-u', 'graspmemoedu', '--', '/opt/graspmemoedu/venv/bin/python', '-m',
                        'graspmemoedu.mathacademy_formula_audit', '--enrichment-package', str(stage / 'package')],
                       cwd='/opt/graspmemoedu/app', check=True)
    timer = quiesce and subprocess.run(['systemctl', 'is-active', '--quiet', 'graspmemoedu-healthcheck.timer']).returncode == 0
    service_stopped = False
    try:
        if timer:
            subprocess.run(['systemctl', 'stop', 'graspmemoedu-healthcheck.timer', 'graspmemoedu-healthcheck.service'], check=True)
        if quiesce:
            subprocess.run(['systemctl', 'stop', 'graspmemoedu'], check=True)
            service_stopped = True
        result = subprocess.run(['runuser', '-u', 'graspmemoedu', '--', '/opt/graspmemoedu/venv/bin/python',
            '-m', module, '--install-package', str(stage / 'package'), '--data-dir', str(data)],
            cwd='/opt/graspmemoedu/app', text=True, capture_output=True, check=True)
        receipt = json.loads(result.stdout.strip().splitlines()[-1])
        after = pointer.read_bytes() if pointer.exists() else None
        # A separate host monitor may have started the service before activation.
        # Reload the selected generation even when that process is already active.
        if after != before or service_stopped:
            subprocess.run(['systemctl', 'restart', 'graspmemoedu'], check=True)
        wait_for_health()
        receipt.update(target='production', health='passed', learning_database_unchanged=True,
                       pointer_sha256=hashlib.sha256(after).hexdigest() if after is not None else None)
        if after != before:
            record = data / 'content-activation-history' / (receipt['generation'] + '.production.json')
            record.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
    except Exception:
        current = pointer.read_bytes() if pointer.exists() else None
        if current != before:
            subprocess.run(['systemctl', 'stop', 'graspmemoedu'], check=True)
            if before is None:
                pointer.unlink(missing_ok=True)
            else:
                pending = pointer.with_suffix('.rollback'); pending.write_bytes(before); os.replace(pending, pointer)
        if current != before or service_stopped:
            subprocess.run(['systemctl', 'restart', 'graspmemoedu'], check=True)
            wait_for_health()
        raise
    finally:
        if timer:
            subprocess.run(['systemctl', 'start', 'graspmemoedu-healthcheck.timer'], check=True)


if __name__ == '__main__':
    import fcntl

    with open('/run/lock/graspmemoedu-content-release.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()

"""Build the isolated TINE Topic editor using the upstream v0.9.2 npm lockfile."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile


UPSTREAM = '7469b6425904301a2294432a880a68bb6819f072'
ARCHIVE_HASH = '98cd8361a9756b813938d100c23f81001a2a798560a258afe5be443aa2289734'
OVERLAY = Path(__file__).resolve().parents[1] / 'integrations' / 'tine'
FILES = ('index.html', 'outline.tsx', 'outline.css', 'vite.config.ts')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='Pinned GitHub source ZIP from codeload')
    parser.add_argument('upstream', type=Path, help='Disposable TINE build directory with npm ci installed')
    parser.add_argument('output', type=Path, help='New release directory')
    args = parser.parse_args()
    upstream, output = args.upstream.resolve(), args.output.resolve()
    with args.archive.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != ARCHIVE_HASH:
            raise ValueError('TINE source archive does not match the pinned commit')
    with ZipFile(args.archive) as source:
        prefix = f'tine-{UPSTREAM}/'
        for name in source.namelist():
            relative = name.removeprefix(prefix)
            if name.endswith('/') or not (relative.startswith('src/') or relative in ('package-lock.json', 'package.json', 'LICENSE')):
                continue
            if (upstream / relative).read_bytes().replace(b'\r\n', b'\n') != source.read(name).replace(b'\r\n', b'\n'):
                raise ValueError('Modified TINE build input: ' + relative)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Use an empty output directory')
    overlay = upstream / 'graspmemoedu-topic'
    overlay.mkdir(exist_ok=True)
    for name in FILES:
        shutil.copyfile(OVERLAY / name, overlay / name)
    subprocess.run(['node', str(upstream / 'node_modules/vite/bin/vite.js'), 'build', '--config',
                    str(overlay / 'vite.config.ts')], cwd=upstream, check=True,
                   env={**os.environ, 'GRASPMEMOEDU_TINE_OUT': str(output)})
    shutil.copyfile(args.archive, output / 'source.zip')
    with ZipFile(output / 'source.zip', 'a', compression=ZIP_DEFLATED) as combined:
        for name in FILES:
            combined.write(OVERLAY / name, prefix + 'graspmemoedu-topic/' + name)
        combined.write(__file__, prefix + 'graspmemoedu-build.py')
        combined.writestr(prefix + 'graspmemoedu-topic/BUILD.txt',
                          'Run npm ci at the root. Set GRASPMEMOEDU_TINE_OUT to an empty release directory.\n'
                          'Run node node_modules/vite/bin/vite.js build --config graspmemoedu-topic/vite.config.ts\n')


if __name__ == '__main__':
    main()

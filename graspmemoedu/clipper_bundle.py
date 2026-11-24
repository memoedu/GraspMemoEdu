"""Materialize the portable desktop workflow from an immutable upstream software release."""
import argparse
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
from tempfile import NamedTemporaryFile
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'scripts/clipper-assets.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ensure(destination, archive=None):
    lock = json.loads(LOCK.read_text(encoding='utf-8'))
    files = lock['files']
    if not re.fullmatch(r'[a-f0-9]{40}', lock['revision']) or digest(
            (ROOT / 'graspmemoedu/clipper_catalog.json').read_bytes().replace(b'\r\n', b'\n')) != lock['catalog_sha256']:
        raise ValueError('The clipper catalog differs from its release.')
    for name in files:
        parts = PurePosixPath(name).parts
        if not parts or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name) or any(v.startswith('.') for v in parts) or name.startswith('/'):
            raise ValueError('Invalid clipper runtime path.')
    destination = Path(destination)
    def matches(name):
        file = destination / name
        return file.is_file() and digest(file.read_bytes()) == files[name]
    missing = [name for name in files if not matches(name)]
    if not missing:
        return files
    archive = archive or os.environ.get('GRASPMEMOEDU_CLIPPER_BUNDLE')
    if archive:
        data = Path(archive).read_bytes()
    else:
        url = ('https://github.com/memoedu/KnowledgeClipper/releases/download/floating-' + lock['revision'][:12] +
               '/knowledge-clipper-web.zip')
        with closing(urlopen(url, timeout=120)) as response:
            data = response.read(60 * 1024 * 1024)
    if digest(data) != lock['sha256']:
        raise ValueError('The clipper archive differs from its release.')
    with ZipFile(io.BytesIO(data)) as package:
        if sorted(package.namelist()) != sorted(files):
            raise ValueError('Unexpected clipper archive entries.')
        for name in missing:
            contents = package.read(name)
            if digest(contents) != files[name]:
                raise ValueError('Invalid clipper runtime file: ' + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
                tmp.write(contents)
            os.replace(tmp.name, target)
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'web/vendor/knowledge-clipper')
    parser.add_argument('--archive', type=Path)
    options = parser.parse_args()
    ensure(options.destination, options.archive)

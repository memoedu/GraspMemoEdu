"""Round-trip one stable synthetic outline using the site's configured private repository."""
import json
from graspmemoedu.topic_sync_storage import configured_snapshots


def canary(store):
    scope = ('acceptance', 'topic-storage', 'roundtrip')
    marker = 'Synthetic outline for verifying private Topic storage'
    document = {'format': 'topic-outline-v1', 'title': marker, 'blocks': []}
    revision = store.save(scope, document)
    path, _ = store._location(scope, revision)
    ciphertext = store.files.read(path)
    if not ciphertext.startswith(b'GME1') or marker.encode() in ciphertext or store.load(scope, revision) != document:
        raise RuntimeError('Private repository snapshot readback failed')
    return {'repository': store.files.repo, 'ciphertext_bytes': len(ciphertext), 'authenticated_readback': True,
            'plaintext_marker_absent': True, 'file': path}


if __name__ == '__main__':
    print(json.dumps(canary(configured_snapshots())))

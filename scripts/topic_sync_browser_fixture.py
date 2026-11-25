"""Serve a synthetic account pair and Topic for Navigator browser acceptance."""

import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graspmemoedu.api import create_app
from graspmemoedu.config import Settings
from graspmemoedu.service import LearningService
from graspmemoedu.topic_sync_storage import SealedSnapshots
from tests.fixtures import DeterministicJudge, synthetic_course
from tests.test_topic_sync import MemoryFiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--port', type=int, default=18948)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=False)
    course = synthetic_course()
    course['introduction']['html'] += (
        '<h4>Outline formula section</h4><div class="outlineNode"><p>Outline parent \\(x_1^2\\)</p>'
        '<div class="outlineChildren"><div class="outlineNode"><p>Outline child</p></div></div></div>'
        '<div>Preserve <strong>inline formatting</strong> in one row.</div>'
        '<p><span class="mathDisplay" data-tex="\\frac{2}{3}"><mjx-container display="true">'
        '<svg><title>SVG replica</title></svg></mjx-container></span></p>'
    )
    settings = Settings(data_dir=args.root, port=args.port)
    with patch('graspmemoedu.api.configured_snapshots', return_value=SealedSnapshots(MemoryFiles(), bytes(32))):
        app = create_app(settings, LearningService(course, args.root, DeterministicJudge()))
    invitations = [app.state.access_store.create_account(name, purpose='test')['invitation_code']
                   for name in ('Original fixture', 'Other fixture')]
    (args.root / 'topic-sync-browser.json').write_text(json.dumps({'invitations': invitations, 'topic_id': course['id']}),
                                                       encoding='utf-8')
    print('READY isolated Topic sync fixture', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()

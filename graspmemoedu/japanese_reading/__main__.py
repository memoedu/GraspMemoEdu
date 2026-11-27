"""Run the Japanese reading interface on the local machine."""

import argparse
from pathlib import Path

import uvicorn

from .app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18784)
    parser.add_argument("--topic-file", type=Path, help="Local 丁寧語 topic.json used by your Japanese lesson service")
    parser.add_argument("--progress-db", type=Path, help="Local learning.sqlite3, opened read-only")
    parser.add_argument("--lesson-port", type=int, default=18782, help="Port for the link to your local Japanese lesson")
    args = parser.parse_args()
    if not all(1 <= port <= 65535 for port in (args.port, args.lesson_port)):
        parser.error("ports must be between 1 and 65535")
    if (args.topic_file is None) != (args.progress_db is None):
        parser.error("--topic-file and --progress-db must be provided together")
    for file in (args.topic_file, args.progress_db):
        if file is not None and not file.is_file():
            parser.error("both local data files must already exist")
    app = create_app(topic_file=args.topic_file, progress_db=args.progress_db, lesson_port=args.lesson_port)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

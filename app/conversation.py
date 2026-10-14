"""Single-user conversation on the same persistent volume as the browser profile."""
import json
import os
from pathlib import Path
import uuid

PATH = Path('/data/assistant/conversation.json')


class Conversation:
    def __init__(self, path=None):
        self.path = path or PATH
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {'id': uuid.uuid4().hex, 'turns': []}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            os.chmod(temporary, 0o600)
            json.dump(self.data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def start(self, task, model, job_id):
        self.data['turns'].append({'job_id': job_id, 'task': task, 'model': model,
                                   'state': 'running', 'result': '', 'page': {}, 'progress': ''})
        self.save()

    def update(self, job_id, **details):
        if not self.data['turns'] or self.data['turns'][-1]['job_id'] != job_id:
            return
        turn = self.data['turns'][-1]
        before = dict(turn)
        for key in ('state', 'result', 'page', 'progress'):
            if key in details:
                turn[key] = details[key]
        if turn != before:
            self.save()

    def reset(self):
        self.data = {'id': uuid.uuid4().hex, 'turns': []}
        self.save()

    def context(self):
        # Keep the initial request plus recent turns; full transcript remains on disk.
        turns = self.data['turns']
        selected = turns if len(turns) <= 21 else [turns[0], *turns[-20:]]
        return json.dumps(selected, ensure_ascii=False)

"""Explicit local residency management for the routing experiment, not an agent tool."""
import http.client
import json
from pathlib import Path
import subprocess
import time
from models import MODELS, model_id
from configuration import load


def api(path, body=None):
    connection = http.client.HTTPConnection('localhost', load()['port'], timeout=120)
    try:
        connection.request('POST' if body is not None else 'GET', path,
                           json.dumps(body) if body is not None else None,
                           {'Content-Type': 'application/json'})
        response = connection.getresponse()
        result = json.loads(response.read())
        if response.status != 200:
            raise RuntimeError(f'Local residency API HTTP {response.status}')
        return result
    finally:
        connection.close()


class ModelSession:
    def __init__(self, request=api, process=subprocess.run):
        self.request, self.process = request, process
        self.events = []

    def ensure(self, role):
        target = model_id(role)
        started = time.perf_counter()
        event = {'target': role, 'unload_s': 0.0, 'load_s': 0.0}
        self.events.append(event)
        del self.events[:-20]
        try:
            models = self.request('/api/v1/models')['models']
            loaded = [i['id'] for m in models for i in m.get('loaded_instances', [])]
            if target in loaded:
                event['reused'] = True
                return event
            # Only our configured model identities may be unloaded. No arbitrary model control.
            for other in MODELS.values():
                if other in loaded:
                    mark = time.perf_counter()
                    self.request('/api/v1/models/unload', {'instance_id': other})
                    event['unload_s'] += time.perf_counter() - mark
            mark = time.perf_counter()
            try:
                result = self.process([str(Path.home() / '.lmstudio/bin/lms'), 'load', target,
                    '--context-length', '8192' if role == 'fast' else '16384', '--parallel', '1',
                    '--identifier', target, '-y'], capture_output=True, text=True, timeout=120)
            finally:
                event['load_s'] = time.perf_counter() - mark
            if result.returncode:
                event['load_error'] = result.stderr[-1000:]
                raise RuntimeError('Local model load failed')
            models = self.request('/api/v1/models')['models']
            instances = [i for m in models for i in m.get('loaded_instances', []) if i['id'] == target]
            if not instances:
                raise RuntimeError('Requested local model did not become available')
            event['config'] = instances[0]['config']
            return event
        except Exception as error:
            event['error'] = str(error)
            raise
        finally:
            event['total_s'] = time.perf_counter() - started

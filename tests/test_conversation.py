import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
from conversation import Conversation
import agent_api as api


class ConversationTests(unittest.TestCase):
    def test_restart_preserves_goal_offer_and_interrupted_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'conversation.json'
            conversation = Conversation(path)
            conversation.start('Suche eine Gimbal-Kamera bis 300 Euro', 'gpt-6.1-sol', 'first')
            conversation.update('first', state='done', result='Angebot A: https://example.com/a',
                                page={'url': 'https://example.com/a', 'title': 'Kamera A'})
            conversation.start('Öffne dieses Angebot', 'gpt-6.1-sol', 'second')
            conversation.update('second', progress='Kamera A wird geprüft')
            jobs = api.Jobs(Conversation(path))
            restored = jobs.conversation.data['turns']
            self.assertEqual(restored[0]['page']['url'], 'https://example.com/a')
            self.assertEqual(restored[1]['state'], 'interrupted')
            self.assertIn('300 Euro', jobs.conversation.context())
            self.assertIn('Kamera A wird geprüft', jobs.conversation.context())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            jobs.reset()
            self.assertEqual(Conversation(path).data['turns'], [])

    def test_persistent_worker_reused_and_stopped_turn_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(api, 'STATE', Path(directory)), \
                patch.dict(api.os.environ, {'OPENAI_API_KEY': 'test'}), \
                patch.object(api, 'cdp_ready', return_value=True), patch.object(api.threading, 'Thread'), \
                patch.object(api.subprocess, 'Popen') as worker:
            process = worker.return_value
            process.poll.return_value = None
            jobs = api.Jobs(Conversation(Path(directory) / 'conversation'))
            jobs.start('Suche Kamera bis 300 Euro', 'gpt-6.1-sol')
            first = jobs.job_id
            (api.STATE / (first + '.json')).write_text(json.dumps({
                'state': 'done', 'result': 'Angebot A', 'page': {'url': 'https://example.com/a'}}))
            jobs.start('Ist dieses Angebot gut?', 'gpt-6.1-sol')
            self.assertEqual(worker.call_count, 1)
            payload = json.loads(process.stdin.write.call_args.args[0])
            self.assertIn('300 Euro', payload['context'])
            self.assertIn('https://example.com/a', payload['context'])
            (api.STATE / (jobs.job_id + '.json')).write_text(json.dumps({'state': 'running', 'progress': 'Prüfe A'}))
            with patch.object(api.os, 'killpg'):
                jobs.terminate('stopped', 'Gestoppt')
            jobs.status()
            self.assertEqual(jobs.conversation.data['turns'][-1]['state'], 'stopped')
            self.assertEqual(jobs.conversation.data['turns'][-1]['progress'], 'Prüfe A')



class WorkerTests(unittest.TestCase):
    def test_followup_reuses_agent_and_active_tab_model_change_restores_context(self):
        fake = ModuleType('browser_use')
        fake.Agent, fake.Browser, fake.ChatOpenAI = Mock(), Mock(), Mock()
        with patch.dict(sys.modules, {'browser_use': fake}):
            spec = importlib.util.spec_from_file_location('session_worker', Path(__file__).parents[1] / 'app/agent_worker.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        browser = fake.Browser.return_value
        browser.start = AsyncMock()
        browser.get_current_page_url = AsyncMock(return_value='https://example.com/current-offer')
        browser.get_current_page_title = AsyncMock(return_value='Aktuelle Kamera')
        agent = fake.Agent.return_value
        agent.history.history = []
        agent.state.n_steps = 1
        agent.run = AsyncMock(return_value=SimpleNamespace(history=[], final_result=lambda: 'Angebot geprüft'))
        async def scenario():
            session = module.Session()
            session.report = Mock()
            request = {'job_id': 'a', 'model': 'gpt-6.1-sol', 'conversation_id': 'chat',
                       'task': 'Suche Kamera bis 300 Euro', 'context': 'Kamera bis 300 Euro'}
            await session.run(request)
            agent.state.n_steps = 9
            await session.run({**request, 'job_id': 'b', 'task': 'Prüfe dieses Angebot'})
            self.assertEqual(agent.run.call_args.kwargs["max_steps"], 16)
            self.assertEqual(fake.Agent.call_count, 1)
            self.assertIn('current-offer', agent.add_new_task.call_args.args[0])
            self.assertIn('Prüfe dieses Angebot', agent.add_new_task.call_args.args[0])
            await session.run({**request, 'model': 'gpt-5.6-terra'})
            self.assertEqual(fake.Agent.call_count, 2)
            self.assertIn('Kamera bis 300 Euro', fake.Agent.call_args.kwargs['task'])
        asyncio.run(scenario())

    def test_visible_tab_overrides_previous_agent_focus(self):
        fake = ModuleType('browser_use')
        fake.Agent, fake.Browser, fake.ChatOpenAI = Mock(), Mock(), Mock()
        with patch.dict(sys.modules, {'browser_use': fake}):
            spec = importlib.util.spec_from_file_location('focus_worker', Path(__file__).parents[1] / 'app/agent_worker.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        browser = fake.Browser.return_value
        browser.cdp_client.send.Target.getTargets = AsyncMock(return_value={'targetInfos': [
            {'type': 'page', 'targetId': 'old'}, {'type': 'page', 'targetId': 'current'}]})
        cdp = Mock()
        cdp.session_id = 'session'
        cdp.cdp_client.send.Runtime.evaluate = AsyncMock(side_effect=[
            {'result': {'value': json.dumps({'visible': False, 'url': 'https://example.com/old', 'title': 'Old'})}},
            {'result': {'value': json.dumps({'visible': True, 'url': 'https://example.com/current', 'title': 'Current'})}}])
        browser.get_or_create_cdp_session = AsyncMock(return_value=cdp)
        session = module.Session()
        asyncio.run(session.current_page())
        self.assertEqual(session.page['url'], 'https://example.com/current')
        browser.get_or_create_cdp_session.assert_called_with('current', focus=True)

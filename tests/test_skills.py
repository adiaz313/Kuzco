"""Skill contracts are tested without a live model, microphone or network."""
import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch
import main
from skills import select, REGISTRY
from routed import RoutingAgent


def answer(text='Done.'):
    return {'content':json.dumps({'answer':text})}

class SkillTests(unittest.TestCase):
    def test_registry_metadata(self):
        self.assertEqual({s.name for s in REGISTRY},{'web_research','document_analysis','mac_utility'})
        for s in REGISTRY:
            self.assertTrue(s.description and s.tools and s.execution and s.context and s.output)

    def test_web_selection(self):
        for p in ['Research current prices','Read https://example.org','Who is the governor?']:
            self.assertEqual(select(p).name,'web_research')

    def test_document_selection(self):
        for p in ['What does this document say about oats?','What was the Northwind product idea?']:
            self.assertEqual(select(p).name,'document_analysis')

    def test_mac_selection(self):
        for p in ['What time is it?','Open Calculator.','Launch TextEdit.']:
            self.assertEqual(select(p).name,'mac_utility')

    def test_general_and_mixed_fallback(self):
        for p in ['Hello Kuzco.','Explain quantum entanglement','Compare my documents with web research','Open it']:
            if p == 'Open it':
                self.assertEqual(select(p).name,'general')
                # A named app is not inferred: the existing router still sends it to 8B.
                from router import route,Destination
                self.assertNotEqual(route(p).destination,Destination.DIRECT)
            else:self.assertEqual(select(p).name,'general')

    def test_time_stays_zero_model(self):
        model=Mock(side_effect=AssertionError('No model'))
        session=Mock()
        result=RoutingAgent('direct',session)('What time is it?',send=model,personality='kuzco')
        self.assertIn('sir',result);model.assert_not_called();session.ensure.assert_not_called()

    def test_calculator_and_app_stay_zero_model(self):
        for app in ['Calculator','TextEdit']:
            model=Mock();session=Mock()
            with patch('main.open_application',return_value={'opened':True,'application_name':app}):
                self.assertIn(app,RoutingAgent('direct',session)('Open '+app,send=model))
            model.assert_not_called();session.ensure.assert_not_called()

    def test_scoped_context_and_personality(self):
        for prompt, present, absent in [('My document contents?', 'search_documents','read_webpage'),
                ('Who is the governor?', 'search_web','open_application'),
                ('What time is it?', 'get_current_time','search_documents')]:
            sent=[]
            main.run(prompt,personality='kuzco',send=lambda p:sent.append(p) or answer())
            system=sent[0]['messages'][0]['content']
            self.assertIn(present,system);self.assertNotIn('"name": "'+absent+'"',system)
            self.assertIn('Your name is Kuzco',system)

    def test_plain_greeting_has_no_tool_definitions(self):
        sent=[];main.run('Hello Kuzco.',send=lambda p:sent.append(p) or answer())
        self.assertIn('No tools are active',sent[0]['messages'][0]['content'])
        self.assertEqual(sent[0]['response_format']['json_schema']['schema'],main.DECISION_SCHEMA['oneOf'][0])
        self.assertNotIn('publication/update',sent[0]['messages'][0]['content'])

    def test_document_evidence_and_qualification(self):
        history=[];sent=[]
        choices=iter([{'content':json.dumps({'tool':'search_documents','arguments':{'query':'oats'}})},answer('The document says oats may help [notes, chunk 1].')])
        with patch('main.search_documents',return_value={'matches':[{'source':'notes','chunk':1,'text':'Oats may help.'}]}):
            result=main.run('What does my document say?',history=history,send=lambda p:sent.append(p) or next(choices))
        self.assertIn('may help',result);self.assertIn('never turn a proposed benefit',sent[0]['messages'][0]['content'])
        self.assertIn('Oats may help',json.dumps(history))

    def test_unavailable_skill_tool_is_not_executed(self):
        choices=iter([{'content':json.dumps({'tool':'open_application','arguments':{'application_name':'Safari'}})},answer()])
        with patch('main.open_application') as app:
            main.run('What does my document say?',send=lambda p:next(choices))
        app.assert_not_called()

    def test_debug_selection_and_failure_recovery(self):
        with contextlib.redirect_stderr(io.StringIO()) as log:
            main.run('My documents?',debug=True,send=lambda p:answer())
        self.assertIn('Selected Skill',log.getvalue());self.assertIn('document_analysis',log.getvalue())
        with self.assertRaises(ConnectionError):
            main.run('My documents?',send=Mock(side_effect=ConnectionError()))
        self.assertEqual(main.run('Hello',send=lambda p:answer('Hello.')),'Hello.')

    def test_web_skill_preserves_direct_plan(self):
        plan=select('Research Python').plan('Research Python')
        self.assertEqual(plan,{'tool':'research_web','arguments':{'query':'Python'}})

    def test_no_arithmetic_capability_invented(self):
        self.assertNotIn('calculate',select('Open Calculator').tools)
        self.assertEqual(select('What is 17 times 23?').name,'general')

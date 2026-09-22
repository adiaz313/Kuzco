import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock
import configuration
import doctor
import install_assets


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.environment = patch.dict(os.environ, {'KUZCO_HOME':str(self.root)})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_fresh_user_has_no_memories_documents_or_secrets(self):
        configuration.initialize()
        self.assertFalse((self.root/'kuzco.db').exists())
        self.assertEqual(configuration.documents(), [])
        self.assertEqual(set(configuration.load()), {'model','port','personality','documents'})
        self.assertEqual((self.root/'config/kuzco.toml').stat().st_mode & 0o777, 0o600)

    def test_missing_configured_document_does_not_disable_unrelated_requests(self):
        configuration.initialize()
        missing = self.root / 'moved-private-document.docx'
        (self.root/'config/kuzco.toml').write_text(
            'port = 1234\nmodel = "meta-llama-3.1-8b-instruct"\n'
            'personality = "kuzco"\ndocuments = ["' + str(missing) + '"]\n')
        self.assertEqual(configuration.documents(), [])

    def test_setup_does_not_overwrite_user_settings(self):
        configuration.initialize()
        p=self.root/'config/security_settings.json'
        p.write_text('{"disabled_tools":["open_application"]}')
        configuration.initialize()
        self.assertIn('open_application',p.read_text())
        self.assertEqual(configuration.settings_path(p.name),p)

    def test_config_rejects_cloud_host_and_credentials(self):
        configuration.initialize()
        for entry in ['host = "cloud.example"','api_key = "synthetic"','port = true', 'documents = ["relative.txt"]']:
            (self.root/'config/kuzco.toml').write_text(entry)
            with self.assertRaises(ValueError): configuration.load()

    def test_asset_and_memory_locations_are_outside_source(self):
        from memory import database_path
        self.assertEqual(configuration.asset('models/test.bin'),self.root/'assets/models/test.bin')
        with patch.dict(os.environ, {}, clear=True), patch('configuration.home',return_value=self.root):
            self.assertEqual(database_path(),self.root/'kuzco.db')

    def test_security_override_is_enforced_in_candidate(self):
        import security_policy as policy
        import main
        configuration.initialize()
        p=self.root/'config/security_settings.json'
        p.write_text('{"disabled_tools":["open_application"]}')
        @policy.request_scope
        def proposed(prompt):
            return main.execute_tool({'function':{'name':'open_application','arguments':'{"application_name":"Calculator"}'}},())
        with patch.object(policy,'CONFIG',p), patch('main.subprocess.run') as execute:
            result=proposed('Open Calculator.')
            self.assertIn('error',result)
            execute.assert_not_called()
            p.write_text('{"disabled_tools":[]}')
            execute.return_value=Mock(returncode=0)
            result=proposed('Open Calculator.')
            self.assertNotIn('error',result)
            execute.assert_called_once()

    def test_archive_rejects_traversal_and_links(self):
        for name,kind in [('../escape',tarfile.REGTYPE),('root/link',tarfile.SYMTYPE)]:
            archive=self.root/'input.tar'
            with tarfile.open(archive,'w') as output:
                member=tarfile.TarInfo(name);member.type=kind;member.linkname='/etc/passwd'
                output.addfile(member)
            with self.assertRaises(ValueError): install_assets.unpack(archive,self.root/'output')
            self.assertFalse((self.root/'output').exists())

    def test_download_reuses_only_verified_bytes(self):
        p=configuration.asset('fixture');p.parent.mkdir(parents=True);p.write_bytes(b'fixture')
        entry={'path':'fixture','sha256':hashlib.sha256(b'fixture').hexdigest()}
        with patch('urllib.request.urlopen') as network:
            self.assertEqual(install_assets.download(entry),p)
            network.assert_not_called()

    def test_bad_download_keeps_existing_asset(self):
        p=configuration.asset('fixture');p.parent.mkdir(parents=True);p.write_bytes(b'old')
        entry={'path':'fixture','sha256':hashlib.sha256(b'expected').hexdigest(),'url':'https://example.org/fixture','max_bytes':100}
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.side_effect=[b'incorrect',b'']
        with patch('urllib.request.OpenerDirector.open',return_value=response), self.assertRaisesRegex(ValueError,'checksum'):
            install_assets.download(entry)
        self.assertEqual(p.read_bytes(),b'old')
        self.assertEqual(list(p.parent.iterdir()),[p])

    def test_installer_rejects_non_https_and_redirect_downgrade(self):
        entry={'path':'fixture','url':'file:///etc/passwd','sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            install_assets.download(entry)
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            install_assets.HTTPSRedirects().redirect_request(None,None,302,'',{},'http://example.org/file')

    def test_exact_saved_template_is_verified(self):
        template=(configuration.ROOT/'runtime/llama31.jinja').read_text()
        p=self.root/'model.json'
        p.write_text(json.dumps({'load':{'fields':[{'key':'llm.load.promptTemplate','value':{'jinjaPromptTemplate':{'template':template}}}]}}))
        self.assertEqual(doctor.verify_template(p),hashlib.sha256(template.encode()).hexdigest())
        p.write_text('{}')
        with self.assertRaises(ValueError): doctor.verify_template(p)

    def test_corrected_template_does_not_inject_empty_function_mode(self):
        from jinja2 import Environment
        template=(configuration.ROOT/'runtime/llama31.jinja').read_text()
        context={'bos_token':'<|begin_of_text|>','messages':[{'role':'user','content':'Hello'}], 'add_generation_prompt':True}
        for tools in [None, []]:
            rendered=Environment().from_string(template).render(**context,tools=tools)
            self.assertNotIn('Given the following functions',rendered)
            self.assertIn('Hello',rendered)
        rendered=Environment().from_string(template).render(**context)
        self.assertNotIn('Given the following functions',rendered)

    def test_explicit_real_tools_still_render_in_template(self):
        from jinja2 import Environment
        template=(configuration.ROOT/'runtime/llama31.jinja').read_text()
        rendered=Environment().from_string(template).render(bos_token='',messages=[{'role':'user','content':'Hello'}],
            tools=[{'name':'fixture','description':'Test only'}],add_generation_prompt=True)
        self.assertIn('Given the following functions',rendered)
        self.assertIn('fixture',rendered)

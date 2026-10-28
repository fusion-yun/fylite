"""Object/clone invariants without a kernel, network, or historical mutation."""
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / 'delivery/eq/apps/workflow/workflow.py'
spec = importlib.util.spec_from_file_location('wf_objects', source)
w = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = w
spec.loader.exec_module(w)

class Objects(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root/'reference'
        self.data.mkdir()
        w.write(self.data/'manifest.json', {'files': {}})
        self.env = patch.dict(w.os.environ, {'FYLITE_EQ_DATA': str(self.data)})
        self.env.start()
        self.roots = [self.root/'personal']
        self.case = w.save({'name':'source','parameters':w.DEFAULT},self.roots)
        self.casepath = w.casepath(self.case['case_id'],self.roots)
        data = self.casepath/'datasets/data-original'
        data.mkdir(parents=True)
        w.write(data/'sources.json',{'source':'test'})
        (data/'acquired-waveforms.json.gz').write_bytes(b'fixture-not-a-real-waveform')
        w.processing_tools.publish(w,data,{'dataset_id':'data-original'},('sources.json','acquired-waveforms.json.gz'))
        preview = self.casepath/'previews/preview-original'
        preview.mkdir(parents=True)
        for name in ('sources.json','acquired-waveforms.json.gz'):
            (preview/name).write_bytes((data/name).read_bytes())
        w.write(preview/'quality.json',{'passed':True})
        w.write(preview/'magnetics.json',{'fixture':True})
        w.processing_tools.publish(w,preview,{'preview_id':'preview-original','dataset_id':'data-original','parameters':w.processing_tools.subset(w.DEFAULT),'tool_sha256':w.tool_identity(),'base_revision':1},('sources.json','acquired-waveforms.json.gz','quality.json','magnetics.json'))
        self.case['processing']={'preview_id':'preview-original','sha256':w.sha(preview/'object.json')}
        w.write(self.casepath/'case.json',self.case)
        self.before=self.hashes()

    def tearDown(self):
        self.env.stop();self.temp.cleanup()

    def hashes(self):
        return {str(p.relative_to(self.casepath)):w.sha(p) for p in self.casepath.rglob('*') if p.is_file()}

    def fork(self,**kwargs):
        return w.save({'name':'copy','parameters':w.DEFAULT,'source_case_id':self.case['case_id'],'source_revision':1,**kwargs},self.roots)

    def test_complete_clone_and_unchanged_source(self):
        new=self.fork();dest=w.casepath(new['case_id'],self.roots)
        self.assertEqual(new['processing'],self.case['processing'])
        w.processing_tools.adopted(w,dest,new['processing'],new['parameters'])
        for rel,digest in self.before.items():
            if rel.startswith(('datasets/','previews/')):self.assertEqual(w.sha(dest/rel),digest)
        self.assertEqual(self.hashes(),self.before)

    def test_changed_window_retains_data_but_invalidates_adoption(self):
        new=self.fork(parameters={**w.DEFAULT,'half_window_s':.003})
        self.assertNotIn('processing',new)
        self.assertTrue((w.casepath(new['case_id'],self.roots)/'datasets/data-original/object.json').exists())
        self.assertEqual(self.hashes(),self.before)

    def test_pressure_keeps_adoption(self):
        self.assertIn('processing',self.fork(parameters={**w.DEFAULT,'pressure_scale':1.1}))

    def test_stale_source_revision_rejected(self):
        with self.assertRaises(ValueError):self.fork(source_revision=0)

    def test_corrupt_reference_does_not_publish_case(self):
        (self.casepath/'datasets/data-original/sources.json').write_text('{}')
        before=set(w.base(self.roots).iterdir())
        with self.assertRaises(ValueError):self.fork()
        self.assertEqual(set(w.base(self.roots).iterdir()),before)

    def test_legacy_hash_profile_and_copied_envelope(self):
        value={'x':[1,1.0], 'text':'中文'}
        self.assertEqual(w.hobj(value),w.object_contracts.digest(value))
        obj=w.object_contracts.envelope('Dataset','data-x',value)
        value['x'].append(3)
        self.assertEqual(obj['payload']['x'],[1,1.0])
        self.assertEqual(obj['hash_profile'],'legacy-python-json-sort-keys-v1')

    def test_readonly_legacy_definition_revisions(self):
        for revision in (2,3,4):
            run=self.casepath/'runs'/('run-legacy-'+str(revision));run.mkdir(parents=True)
            snapshot={'revision':1,'case_id':self.case['case_id'],'target':'magnetics',
                      'parameters':w.DEFAULT,'workflow_definition':{'schema':'fylite.workflow/1','version':revision},'plan':[]}
            w.write(run/'snapshot.json',snapshot)
            w.write(run/'magnetics.json',{'test':'legacy record'})
            w.write(run/'status.json',{'steps':{'magnetics':{'state':'completed','sha256':w.sha(run/'magnetics.json')}}})
            before={p.name:w.sha(p) for p in run.iterdir()}
            view=w.object_contracts.run_objects(w,run)
            self.assertEqual(view['definition_revision'],revision)
            self.assertTrue(view['legacy'])
            self.assertEqual(before,{p.name:w.sha(p) for p in run.iterdir()})
            self.assertEqual(view,w.object_contracts.run_objects(w,run))

    def test_unknown_definition_is_readable_not_invented(self):
        run=self.casepath/'runs/run-unknown';run.mkdir(parents=True)
        w.write(run/'snapshot.json',{'target':'report'})
        w.write(run/'status.json',{'steps':{}})
        view=w.object_contracts.run_objects(w,run)
        self.assertIsNone(view['definition_revision'])
        self.assertFalse(view['objects'][0]['payload']['definition_known'])

    def test_artifact_corruption_rejected(self):
        run=self.casepath/'runs/run-bad';run.mkdir(parents=True)
        w.write(run/'snapshot.json',{'target':'magnetics'})
        w.write(run/'magnetics.json',{'changed':True})
        w.write(run/'status.json',{'steps':{'magnetics':{'state':'completed','sha256':'wrong'}}})
        with self.assertRaises(ValueError):w.object_contracts.run_objects(w,run)

    def test_dag_reuse_and_invalidation(self):
        definition=w.DEFINITION
        root=self.casepath/'runs';root.mkdir(exist_ok=True)
        def run(name,pars):
            path=root/name;path.mkdir()
            nodes=w.plan_nodes(definition,'report')
            snap={'parameters':pars,'workflow_definition':definition,'workflow_sha256':w.hobj(definition),
                  'target':'report','dataset_manifest_sha256':w.sha(self.data/'manifest.json'),
                  'tool_sha256':w.tool_identity(),'kernel_identity':{'fixture':'no kernel'}}
            w.write(path/'snapshot.json',snap)
            before=w.sha(path/'snapshot.json')
            w.write(path/'status.json',{'steps':{n['id']:{'state':'pending'} for n in nodes}})
            receipts={}
            for n in nodes:
                if n.get('review'):
                    w.write(path/(n['id']+'.json'),{'test_review_fixture':True})
                    receipts[n['id']]={'identity':'fixture'}
            w.write(path/'approvals.json',receipts)
            def fake(key):
                names=next(n['parameters'] for n in nodes if n['id']==key)
                deps=next(n['deps'] for n in nodes if n['id']==key)
                return lambda data,pars,out:{'node':key,'parameters':{k:pars[k] for k in names},'deps':{d:w.sha(out/(d+'.json')) for d in deps},'converged':True}
            tools={n.get('tool',n['id']):fake(n['id']) for n in nodes if not n.get('review')}
            with patch.dict(w.TOOLS,tools),patch.object(w,'review_identity',return_value='fixture'):
                w.worker(path,self.data)
            self.assertEqual(w.sha(path/'snapshot.json'),before)
            return path,w.read(path/'status.json')
        first,a=run('run-a',dict(w.DEFAULT))
        before={p.name:w.sha(p) for p in first.iterdir() if p.is_file()}
        _,b=run('run-b',{**w.DEFAULT,'q_target':1.1})
        for key in ('quality','magnetics','pressure'):self.assertEqual(b['steps'][key]['state'],'reused')
        for key in ('constraints','assemble','solve','report'):self.assertEqual(b['steps'][key]['state'],'completed')
        _,c=run('run-c',{**w.DEFAULT,'half_window_s':.003})
        for key in ('quality','magnetics','assemble','solve'):self.assertEqual(c['steps'][key]['state'],'completed')
        self.assertEqual(before,{p.name:w.sha(p) for p in first.iterdir() if p.is_file()})

    def test_review_node_identifiers_are_valid_artifacts(self):
        run=self.casepath/'runs/run-reviewed';run.mkdir(parents=True)
        w.write(run/'snapshot.json',{'target':'review_results','workflow_definition':w.DEFINITION})
        w.write(run/'review_data.json',{'identity':'test-review'})
        w.write(run/'status.json',{'steps':{'review_data':{'state':'completed','sha256':w.sha(run/'review_data.json')}}})
        result=w.object_contracts.run_objects(w,run)
        self.assertEqual(result['objects'][-1]['payload']['name'],'review_data.json')

if __name__=='__main__':unittest.main()

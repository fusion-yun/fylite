"""Frozen 94048 preprocessing regression, no solver or network.
Run with FYLITE_EQ_DATA pointing to the manifested audited dataset.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

p=Path(__file__).resolve().parents[1]/'delivery/eq/apps/workflow/workflow.py'
spec=importlib.util.spec_from_file_location('wf_golden',p);w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
# Baseline develop eaeeb83, default frozen 94048 recipe. Legacy hash profile.
EXPECTED={'magnetics':'c3e61a3fdb9af57f7221ce980d9cec61e7a6e38b29c9839bd659ae52338233b6',
'pressure':'a63af1922f9c18efa4213714c64c80b5a6476d3706c74d403587da6037106821',
'constraints':'8a327290de3b423c039aa014786d7c02f00754bfe97a76978740b0c252f24c15',
'assemble':'c80b1512d425021eb5096466ef811e2ad4d104ac7b7b1e676c6a8b39d9950321'}

class Golden(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('FYLITE_EQ_DATA'),'NOT_RUN: audited frozen dataset required')
    def test_default_effective_input(self):
        with tempfile.TemporaryDirectory() as name:
            run=Path(name);data=w.dataset();pars=dict(w.DEFAULT)
            for key,fun in [('sources',w.sources),('quality',w.pipeline_tools.quality),('magnetics',w.magnetics),('pressure',w.pressure),('constraints',w.pipeline_tools.constraints),('assemble',w.assemble)]:
                w.write(run/(key+'.json'),fun(data,pars,run))
            for key,expected in EXPECTED.items():
                self.assertEqual(w.hobj(w.read(run/(key+'.json'))),expected,key)
            self.assertEqual(len(w.read(run/'magnetics.json')['audit']),85)
            self.assertEqual(len(w.read(run/'pressure.json')['pressure_Pa']),51)

if __name__=='__main__':unittest.main()

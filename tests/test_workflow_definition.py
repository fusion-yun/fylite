import importlib.util,copy
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'delivery/eq/apps/workflow/workflow.py';spec=importlib.util.spec_from_file_location('wf',p);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
d={'nodes':[{'id':'b','tool':'pressure','deps':['a'],'parameters':[]},{'id':'a','tool':'sources','deps':[],'parameters':[]}]}
assert [n['id'] for n in w.plan_nodes(d,'b')]==['a','b']
for bad in [{'nodes':[{'id':'a','tool':'sources','deps':['bad'],'parameters':[]}]},{'nodes':[{'id':'sources','deps':['sources'],'parameters':[]}]},{'nodes':[{'id':'sources','deps':[]},{'id':'sources','deps':[]}]}]:
 try:w.plan_nodes(bad,bad['nodes'][0]['id']);raise AssertionError('accepted invalid graph')
 except ValueError:pass
assert len(w.plan_nodes(w.DEFINITION,'report'))==10
print('PASS dynamic DAG validation, topological order, invalid dependency/cycle/duplicate rejection')


def test_workflow_definition_contract():
    """Run the existing standalone assertions under pytest as well."""
    import runpy
    runpy.run_path(str(Path(__file__).resolve()), run_name="workflow_contract_check")

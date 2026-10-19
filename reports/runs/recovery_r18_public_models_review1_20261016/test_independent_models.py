"""Independent public-package callers and frozen schema oracle checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import ai_intel_client as public_client
import pytest
from ai_intel_client.models import PublicRecord
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import TypeAdapter, ValidationError

ROOT = Path('D:/wt/r18pm-r1')
SCHEMA = json.loads((ROOT/'contracts/schemas/public_api_extensions_v1.json').read_bytes())
ID = 'fa349f76-0b1d-47ca-a128-4655f6ac8a4c'
OTHER_ID = '5be26f2c-45c6-40d3-bbfa-18f87bfa2e02'
STAMP = '2026-10-16T13:00:00Z'
CITE = {'evidence_id':ID,'revision_id':OTHER_ID,'quote':'Synthetic assessment support.',
        'locator':'/body/1','source_uri':'https://example.invalid/advisory'}
FINDING = {'component_index':0,'event_id':OTHER_ID,'assessment_id':ID,'rule_id':OTHER_ID,
           'rule_version':2,'grading_claim_id':OTHER_ID,'severity':'medium','cvss_score':6.0,
           'cvss_version':'4.0','citations':[CITE],'freshness':'current'}
SUMMARY = {'policy_version':'r18-risk-policy-1','minimum_severity':'high',
           'confirmation':'none_confirmed','coverage':'complete','freshness':'current',
           'evaluated_components':1,'unknown_component_indices':[],'findings':[FINDING]}
ASSESSMENT = {'component':{'ecosystem':'npm','package_name':'synthetic-independent','version':'2.1'},
              'status':'supported_applicability','reason_code':'rule_supported',
              'assessment_id':ID,'citations':[CITE],'freshness':'current'}
STACK = {'result':{'kind':'completed','results':[ASSESSMENT],'limitations':[]},'risk_summary':SUMMARY}
VULN = {'intel_id':ID,'event_id':OTHER_ID,'title':'Synthetic independent event','external_ids':[],
        'enrichments':[],'relations':[],'freshness':'current'}
SOURCE = {'source_id':'review-fixture','name':'Review fixture','category':'technical_blog',
          'enabled':False,'health':'never_polled','last_attempt_at':None,'last_success_at':None,
          'reason_code':None,'data_mode':'fixture'}
TASK = {'task_id':ID,'task_type':'stack_check','status':'succeeded','poll_uri':'/api/v1/tasks/'+ID,
        'created_at':STAMP,'updated_at':STAMP}
PROBLEM = {'type':'urn:dianzi:problem:review-fixture','title':'Fixture failure','status':503,
           'error':'not_configured','trace_id':ID}
SAMPLES = {'RiskFinding':FINDING,'RiskSummary':SUMMARY,'StackCheckEnvelope':STACK,
           'VulnerabilityPage':{'items':[VULN],'next_cursor':None,'data_mode':'fixture'},
           'VulnerabilityDetailPage':{'vulnerability':VULN,'advisories':[],'next_cursor':None,
                                      'mapping_limits':[],'data_mode':'fixture'},
           'SourceDescriptor':SOURCE,'SourcePage':{'items':[SOURCE],'next_cursor':None,'data_mode':'fixture'},
           'TaskDescriptor':TASK,'PublicProblem':PROBLEM,
           'TaskResultEnvelope':{'task':TASK,'result':STACK,'error':None,'completed_steps':['assess'],
                                 'pending_steps':[],'failed_steps':[]}}

def valid_in_schema(name: str, value: object) -> bool:
    return Draft202012Validator({**SCHEMA,'$ref':'#/$defs/'+name},format_checker=FormatChecker()).is_valid(value)

def parse_public(name: str, value: object) -> PublicRecord:
    return getattr(public_client,name).model_validate_json(json.dumps(value))

@pytest.mark.parametrize('name',SAMPLES)
def test_public_package_roundtrip_uses_frozen_fields(name: str) -> None:
    value = copy.deepcopy(SAMPLES[name])
    assert valid_in_schema(name,value)
    parsed = parse_public(name,value)
    assert json.loads(parsed.wire_json()) == value
    assert valid_in_schema(name,json.loads(parsed.wire_json()))
    generated = parsed.model_json_schema()
    approved = SCHEMA['$defs'][name]
    assert set(generated['properties']) == set(approved['properties'])
    assert set(generated['required']) == set(approved['required'])
    assert generated['additionalProperties'] is False

@pytest.mark.parametrize('name',SAMPLES)
def test_frozen_required_and_extra_field_oracle(name: str) -> None:
    for field in SCHEMA['$defs'][name]['required']:
        payload = copy.deepcopy(SAMPLES[name])
        payload.pop(field)
        assert not valid_in_schema(name,payload)
        with pytest.raises(ValidationError):
            parse_public(name,payload)
    payload = {**copy.deepcopy(SAMPLES[name]),'skip_validation':True}
    assert not valid_in_schema(name,payload)
    with pytest.raises(ValidationError):
        parse_public(name,payload)

@pytest.mark.parametrize('name',SAMPLES)
def test_frozen_field_limits_and_type_negative_oracle(name: str) -> None:
    for field, definition in SCHEMA['$defs'][name]['properties'].items():
        mutations = [False,123,{},'']
        if 'enum' in definition or 'const' in definition:
            mutations.append('independent-invalid-enum')
        if 'maxLength' in definition:
            mutations.append('x'*(definition['maxLength']+1))
        if 'maximum' in definition:
            mutations.append(definition['maximum']+1)
        if 'minimum' in definition:
            mutations.append(definition['minimum']-1)
        if definition.get('type') == 'array' and 'maxItems' in definition:
            sample = SAMPLES[name][field]
            mutations.append([copy.deepcopy(sample[0] if sample else 'invalid-item')]*(definition['maxItems']+1))
        for replacement in mutations:
            payload = copy.deepcopy(SAMPLES[name])
            payload[field] = replacement
            if not valid_in_schema(name,payload):
                with pytest.raises(ValidationError):
                    parse_public(name,payload)

@pytest.mark.parametrize('confirmation',['unknown','conflict'])
def test_complete_scope_rejects_unknown_or_conflict_summary_from_public_caller(confirmation: str) -> None:
    payload = copy.deepcopy(STACK)
    payload['result']['results'][0]['status'] = 'excluded_with_evidence'
    payload['risk_summary'].update(confirmation=confirmation,findings=[])
    assert valid_in_schema('StackCheckEnvelope',payload)
    with pytest.raises(ValidationError):
        parse_public('StackCheckEnvelope',payload)

@pytest.mark.parametrize('confirmation',['unknown','conflict'])
def test_succeeded_task_rejects_complete_unknown_result_through_union_caller(confirmation: str) -> None:
    payload = copy.deepcopy(SAMPLES['TaskResultEnvelope'])
    payload['result']['result']['results'][0]['status'] = 'excluded_with_evidence'
    payload['result']['risk_summary'].update(confirmation=confirmation,findings=[])
    assert valid_in_schema('TaskResultEnvelope',payload)
    with pytest.raises(ValidationError):
        TypeAdapter(public_client.TaskResultEnvelope).validate_json(json.dumps(payload))

def test_partial_actual_evaluation_can_include_unknown_and_smaller_count() -> None:
    payload = copy.deepcopy(STACK)
    payload['result']['results'][0].update(status='insufficient_evidence',reason_code='missing_version')
    payload['risk_summary'].update(confirmation='unknown',coverage='partial',evaluated_components=1,
                                   unknown_component_indices=[0],findings=[])
    parsed = parse_public('StackCheckEnvelope',payload)
    assert parsed.risk_summary.evaluated_components == 1
    payload['result']['results'].append(copy.deepcopy(ASSESSMENT))
    assert parse_public('StackCheckEnvelope',payload).risk_summary.evaluated_components == 1

@pytest.mark.parametrize('mode',['fixture','live'])
def test_source_page_empty_marker_and_nonempty_mode_binding(mode: str) -> None:
    assert parse_public('SourcePage',{'items':[],'next_cursor':None,'data_mode':mode}).data_mode == mode
    payload = {'items':[{**SOURCE,'data_mode':'live' if mode == 'fixture' else 'fixture'}],
               'next_cursor':None,'data_mode':mode}
    assert valid_in_schema('SourcePage',payload)
    with pytest.raises(ValidationError):
        parse_public('SourcePage',payload)

def test_task_owner_binding_rejects_a_different_valid_uuid() -> None:
    payload = {**TASK,'poll_uri':'/api/v1/tasks/'+OTHER_ID}
    assert valid_in_schema('TaskDescriptor',payload)
    with pytest.raises(ValidationError):
        parse_public('TaskDescriptor',payload)

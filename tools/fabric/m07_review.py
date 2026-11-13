"""M07: revisao somente leitura da configuracao real; nao simula leitor."""
import hashlib
import json
import re
from datetime import datetime, timezone
from client import ROOT, request
from warehouse import connect, results

config = json.loads((ROOT / '.local/fabric-environment.json').read_text())
queries = {
 'function': "SELECT OBJECT_DEFINITION(OBJECT_ID('lab_m07.allow_uf')) AS definition, OBJECTPROPERTY(OBJECT_ID('lab_m07.allow_uf'),'IsSchemaBound') AS schema_bound",
 'policy': "SELECT p.name,p.is_enabled,p.is_schema_bound,s.predicate_definition,s.predicate_type_desc,OBJECT_SCHEMA_NAME(s.target_object_id) AS target_schema,OBJECT_NAME(s.target_object_id) AS target_table FROM sys.security_policies p JOIN sys.security_predicates s ON p.object_id=s.object_id WHERE SCHEMA_NAME(p.schema_id)='lab_m07'",
 'mask': "SELECT name,is_masked,masking_function FROM sys.masked_columns WHERE object_id=OBJECT_ID('lab_m07.access_fixture')",
 'fixture': "SELECT fixture_id,uf,preco_sintetico,contato_ficticio,is_synthetic FROM lab_m07.access_fixture ORDER BY fixture_id",
 'permissions': "SELECT grantee_principal_id,class_desc,major_id,minor_id,permission_name,state_desc,OBJECT_SCHEMA_NAME(major_id) AS target_schema,OBJECT_NAME(major_id) AS target_name FROM sys.database_permissions ORDER BY grantee_principal_id,permission_name",
 'memberships': "SELECT role_principal_id,member_principal_id FROM sys.database_role_members",
 'principals': "SELECT principal_id,name,type_desc,is_fixed_role FROM sys.database_principals",
 'author_context': "SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL') AS has_control,IS_MEMBER('db_owner') AS is_db_owner",
}
raw = {}
with connect(config) as conn:
 for name, sql in queries.items():
  raw[name] = results(conn.cursor().execute(sql))[0]
roles = request('GET', f"workspaces/{config['workspace_id']}/roleAssignments").json()
assert not roles.get('continuationToken'), 'Consultar demais papeis antes de concluir'
raw['workspace_roles'] = roles
private = ROOT / '.local/m07-review';private.mkdir(exist_ok=True)
(private/'catalog.json').write_text(json.dumps(raw,default=str,indent=2))
f = raw['function'][0];source = (ROOT/'sql/labs/security.sql').read_text()
expected = source.split('CREATE FUNCTION lab_m07.allow_uf',1)[1].split('\nGO',1)[0]
normalize=lambda s: re.sub(r'\s+','',s.replace('[','').replace(']','')).lower()
assert normalize(f['definition']).endswith(normalize('CREATE FUNCTION lab_m07.allow_uf'+expected))
assert f['schema_bound']==1
assert len(raw['policy'])==1
p=raw['policy'][0]
assert p['is_enabled']==p['is_schema_bound']==1
assert (p['target_schema'],p['target_table'],p['predicate_type_desc'])==('lab_m07','access_fixture','FILTER')
assert normalize(p['predicate_definition']) in {'lab_m07.allow_uf(uf)', '(lab_m07.allow_uf(uf))'}
masks=[m for m in raw['mask'] if m['is_masked']]
assert len(masks)==1 and masks[0]['name']=='contato_ficticio' and masks[0]['masking_function']=='email()'
assert [(x['fixture_id'],x['uf'],str(x['preco_sintetico']),bool(x['is_synthetic'])) for x in raw['fixture']]==[(1,'RJ','6.100',True),(2,'SP','7.200',True)]
assert raw['author_context'][0]['has_control']==1
public_id=next(x['principal_id'] for x in raw['principals'] if x['name']=='public')
public_grants=[x for x in raw['permissions'] if x['grantee_principal_id']==public_id and x['state_desc'] in {'GRANT','GRANT_WITH_GRANT_OPTION'}]
assert not any(x['permission_name'] in {'CONTROL','UNMASK','ALTER ANY SECURITY POLICY','INSERT','UPDATE','DELETE','ALTER','TAKE OWNERSHIP','IMPERSONATE'} for x in public_grants)
assert all(x['major_id'] < 0 or x['target_schema'] in {'sys', 'INFORMATION_SCHEMA'} for x in public_grants)
role_counts={r:sum(x['role']==r for x in roles['value']) for r in sorted({x['role'] for x in roles['value']})}
report={'status':'implementation_review_passed','environment':'fabric','review_method':'source plus live SQL catalog and workspace role assignments, author identity, read-only',
 'checked_at_utc':datetime.now(timezone.utc).isoformat(),'function_matches_source':True,'function_definition_sha256':hashlib.sha256(f['definition'].encode()).hexdigest(),
 'rls_policy_enabled_schema_bound':True,'rls_target':'lab_m07.access_fixture','predicate_type':'FILTER','mask':masks[0],
 'synthetic_rows':2,'author_context':raw['author_context'][0],'workspace_role_counts':role_counts,
 'public_explicit_grant_count':len(public_grants),'public_grants_only_system_objects':True,
 'reader_identity_created':False,'restricted_identity_tests_executed':False,
 'scope_decision':'User replaced reader acceptance tests with implementation review; no second account required',
 'limits':['No end-to-end permission denial, RLS or masking test with nonprivileged identity',
 'RJ is a fixed lab rule for any non-CONTROL SQL caller, not a per-user region mapping',
 'FILTER predicate is not a write-blocking policy; no writer regional isolation claimed',
 'Warehouse RLS and masking do not automatically secure OneLake files or other tables',
 'Workspace role inventory does not prove absence of all item-level or inherited access grants']}
out=ROOT/'evidence/fabric/security/implementation-review-2026-11-13.json';out.write_text(json.dumps(report,default=str,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ['status','checked_at_utc','function_matches_source','rls_policy_enabled_schema_bound','workspace_role_counts','public_grants_only_system_objects','restricted_identity_tests_executed']}),flush=True)

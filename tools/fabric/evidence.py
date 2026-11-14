"""Gravacao duravel e releitura de evidencia JSON antes de registrar sucesso."""
import json,os,uuid
from pathlib import Path

def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(data,default=str,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    temp=path.with_name(path.name+'.'+str(uuid.uuid4())+'.tmp')
    with temp.open('wb') as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    assert temp.read_bytes()==payload,'Evidencia temporaria divergiu'
    temp.replace(path)
    assert path.read_bytes()==payload and json.loads(path.read_bytes())==json.loads(payload),'Evidencia persistida divergiu'

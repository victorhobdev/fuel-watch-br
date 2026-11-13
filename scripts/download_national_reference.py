import urllib.request,json,hashlib,gzip
from pathlib import Path
from datetime import datetime,timezone
root=Path('.local/national');root.mkdir(exist_ok=True)
for name,url in [('municipios','https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome'),('estados','https://servicodados.ibge.gov.br/api/v1/localidades/estados')]:
 p=root/(name+'.json')
 if not p.exists():
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FuelWatchBR/0.2','Accept-Encoding':'identity'}),timeout=90) as r:raw=r.read()
  decoded=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw;json.loads(decoded);p.with_suffix('.http').write_bytes(raw);p.write_bytes(decoded);(root/(name+'-source.json')).write_text(json.dumps({'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'bytes':len(raw)},indent=2))
 print(name,len(json.loads(p.read_bytes())),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)

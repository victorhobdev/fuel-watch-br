"""Fingerprint completo, com multiplicidade, para comparar publicacoes Warehouse."""
import hashlib,json

def publication_fingerprint(cur,schema='gold_hist'):
    assert schema in {'gold_hist','lab_gold_hist'}
    snapshots={}
    for table in ['business_published','dim_posto','dim_data','dim_municipio','dim_produto','source_versions','publication']:
        cur.execute('SELECT * FROM '+schema+'.'+table);hashes=[]
        while True:
            batch=cur.fetchmany(10000)
            if not batch:break
            hashes.extend(hashlib.sha256(json.dumps([None if x is None else str(x) for x in row],ensure_ascii=False,separators=(',',':')).encode()).hexdigest() for row in batch)
        snapshots[table]={'rows':len(hashes),'sha256':hashlib.sha256('\n'.join(sorted(hashes)).encode()).hexdigest()}
        print('Publication fingerprint',schema,table,len(hashes),flush=True)
    return snapshots

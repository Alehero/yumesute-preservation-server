"""Isolated PostgreSQL backup/restore check; requires initdb/pg_ctl client tools."""
import argparse, json, os
from pathlib import Path
import shutil, socket, subprocess, sys, tempfile, zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lifecycle
import yaml
binpath=Path(shutil.which('pg_dump')).resolve().parent
with tempfile.TemporaryDirectory(prefix='yumesute-backup-check-') as folder:
    temp=Path(folder);cluster=temp/'cluster';root=temp/'installation';(root/'vendor/server-of-dreams').mkdir(parents=True);(root/'private').mkdir()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def run(*args,**kw):return subprocess.run([str(x) for x in args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
    run(binpath/'initdb','-D',cluster,'-A','trust','-U','backup_test')
    run(binpath/'pg_ctl','-D',cluster,'-l',temp/'postgres.log','-o',f'-h 127.0.0.1 -p {port} -k {temp}','-w','start')
    try:
        common=['-h','127.0.0.1','-p',str(port),'-U','backup_test']
        run(binpath/'createdb',*common,'preservation_backup_test')
        run(binpath/'psql',*common,'-d','preservation_backup_test','-c',"CREATE TABLE progress (id integer primary key, score integer); INSERT INTO progress VALUES (1,123456);")
        config={'database':{'host':'127.0.0.1','port':port,'username':'backup_test','password':'','database':'preservation_backup_test'}}
        (root/'vendor/server-of-dreams/config.yml').write_text(yaml.safe_dump(config))
        (root/'private/account.json').write_text(json.dumps({'test_fixture':True}))
        (root/'private/photo.bin').write_bytes(b'preserved photo fixture')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));server_port=sock.getsockname()[1]
        (root/'private/start-options.json').write_text(json.dumps({'port':server_port}))
        out=temp/'save.zip'
        lifecycle.backup(root,argparse.Namespace(output=str(out)))
        with zipfile.ZipFile(out) as z:z.extract('database.dump',temp/'restore')
        run(binpath/'createdb',*common,'preservation_backup_restored')
        run(binpath/'pg_restore',*common,'-d','preservation_backup_restored','--no-owner','--exit-on-error',temp/'restore/database.dump')
        result=run(binpath/'psql',*common,'-d','preservation_backup_restored','-Atc','SELECT score FROM progress WHERE id=1').stdout.decode().strip()
        assert result=='123456',result
        print('PASS: real PostgreSQL custom-format dump, verified ZIP, restore to a separate database, and saved score match.')
    finally:
        run(binpath/'pg_ctl','-D',cluster,'-m','fast','-w','stop')

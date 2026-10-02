"""Pinned public resource metadata and account-independent installation."""
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def resources():
    manifest=json.loads((ROOT/'resource-supplement.json').read_text())
    if manifest.get('format_version')!=1:raise ValueError('Unsupported resource manifest')
    files=manifest['files']
    for path,entry in files.items():
        url=entry['url_path']
        valid=(path=='help.bin' and url=='/master-data/production/help.bin') or (
            url.startswith('/production/static-assets/Resources/Textures/') and path=='static-assets'+url)
        if not valid or not re.fullmatch(r'[A-Za-z0-9_./()-]+',path) or any(x in ('','.','..') for x in path.split('/')):
            raise ValueError('Invalid supplemental resource path')
        if not re.fullmatch(r'[a-f0-9]{64}',entry['sha256']) or type(entry['bytes']) is not int or entry['bytes']<=0:
            raise ValueError('Invalid supplemental resource checksum/size')
    return files

def checksum(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def destination(root,path):
    return Path(root)/'private'/('upstream/help.bin' if path=='help.bin' else path)

def install_resources(source,root,require_all=True):
    source=Path(source);root=Path(root)
    if not (root/'private/upstream').is_dir():raise ValueError('Prepare the installation first')
    selected=[]
    # Validate the whole supplied set before changing any installed file.
    for path,entry in resources().items():
        src=source/path
        if not src.is_file():
            if require_all:raise ValueError('Missing supplemental resource: '+path)
            continue
        if src.stat().st_size!=entry['bytes'] or checksum(src)!=entry['sha256']:
            raise ValueError('Invalid supplemental resource: '+path)
        selected.append((src,destination(root,path)))
    for src,dest in selected:
        if src.resolve()==dest.resolve():continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_name(dest.name+'.installing')
        try:
            shutil.copyfile(src,temp)
            temp.replace(dest)
        finally:temp.unlink(missing_ok=True)
    return len(selected)

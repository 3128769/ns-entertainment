"""Copy instance keys and legacy data and use SQLite's consistent backup API."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse, json, os, shutil, sqlite3
from nsapp.settings import BASE_DIR, DB_PATH


def main():
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);args=parser.parse_args()
    target=args.destination
    target.mkdir(parents=True,exist_ok=False);target.chmod(0o700)
    for name in ['.secret_key','.admin_password']:
        p=BASE_DIR/name
        if p.exists(): shutil.copy2(p,target/name);(target/name).chmod(0o600)
    (target/'app').mkdir()
    for name in ['accounts.json','proxies.json','settings.json']:
        p=BASE_DIR/'app'/name
        if p.exists(): shutil.copy2(p,target/'app'/name)
    if DB_PATH.exists():
        src=sqlite3.connect(f'file:{DB_PATH}?mode=ro',uri=True);dst=sqlite3.connect(target/'app'/'app.sqlite')
        src.backup(dst);assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok';dst.close();src.close()
    for p in target.rglob('*'):
        if p.is_file():p.chmod(0o600)
    print(json.dumps({'status':'ok','destination':str(target),'integrity':'ok'}))
if __name__=='__main__':main()

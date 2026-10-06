"""Restore instance files after all Web/Worker writers have stopped; preserve displaced files."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse, json, os, shutil, sqlite3
from datetime import datetime,timezone
from nsapp.settings import BASE_DIR


def main():
    parser=argparse.ArgumentParser();parser.add_argument('backup',type=Path);parser.add_argument('--uid',type=int,default=10001);args=parser.parse_args()
    source=args.backup.resolve();db=source/'app'/'app.sqlite'
    check=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
    if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('BACKUP_INTEGRITY_FAILED')
    check.close()
    if not (source/'.secret_key').is_file() and not os.getenv('NS_SECRET_KEY'):
        raise RuntimeError('BACKUP_KEY_MISSING')
    for directory in (BASE_DIR,BASE_DIR/'app'):
        directory.mkdir(parents=True,exist_ok=True);directory.chmod(0o700)
        if os.geteuid()==0:os.chown(directory,args.uid,args.uid)
    displaced=BASE_DIR/'backups'/('restore-displaced-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    displaced.mkdir(parents=True);displaced.chmod(0o700)
    names=['.secret_key','.admin_password','app/app.sqlite','app/app.sqlite-wal','app/app.sqlite-shm','app/accounts.json','app/proxies.json','app/settings.json']
    for name in names:
        current=BASE_DIR/name;prior=displaced/name
        if current.exists():prior.parent.mkdir(parents=True,exist_ok=True);shutil.move(current,prior)
        saved=source/name
        if saved.exists():
            current.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(saved,current);current.chmod(0o600)
            if os.geteuid()==0:os.chown(current,args.uid,args.uid)
    print(json.dumps({'status':'ok','displaced':str(displaced),'integrity':'ok'}))

if __name__=='__main__':main()

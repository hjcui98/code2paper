"""L01 runner using the original read-only development sandbox, no fallback."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from scripts import dsh_dev as dev


def canonical_backend_root(profile):
    # Runtime candidates share the established physical-model owner database.
    original='0.2.0-rc.1+loop-origin.1'
    if profile.get('backend_admission_candidate',original)!=original:
        raise RuntimeError('l01_backend_alias_forbidden')
    return REPO/'.dsh-dev/candidates'/original/'live-backend-admission'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['prepare','offline','live'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--authorization',type=Path)
    parser.add_argument('--offline-stream-failure',action='store_true')
    parser.add_argument('--offline-terminal-rejection',action='store_true')
    parser.add_argument('--offline-provider-error',action='store_true')
    args=parser.parse_args()
    if args.offline_stream_failure and args.mode!='offline':
        parser.error('stream failure fixture is isolated offline only')
    if args.offline_terminal_rejection and (args.mode!='offline' or args.offline_stream_failure):
        parser.error('terminal rejection fixture is exclusive isolated offline only')
    if args.offline_provider_error and (args.mode!='offline' or args.offline_stream_failure or args.offline_terminal_rejection):
        parser.error('provider error fixture is exclusive isolated offline only')
    out=args.output.absolute()
    if out.resolve()!=out or not out.is_relative_to(Path('/tmp')) or out==Path('/tmp'):
        parser.error('canonical fresh output under /tmp required')
    if args.mode!='live': out.mkdir(exist_ok=False)
    elif not out.is_dir() or not args.receipt or not args.authorization:
        parser.error('prepared packet, current receipt and authorization required')
    profile=json.loads((REPO/'tests/live/profiles/qwen38_dsh_l01.json').read_text())
    backend_root=canonical_backend_root(profile)
    candidate=profile.get('candidate','0.2.0-rc.1+loop-origin.1')
    dev.select_candidate(candidate)
    manifest=json.loads((dev.DEV_ROOT/'manifest.json').read_text())
    env=dev.child_env(manifest['node'])
    ns=os.stat('/proc/self/ns/net')
    env['C2P_L01_PARENT_NETNS']=json.dumps({'device':ns.st_dev,'inode':ns.st_ino})
    payload=[manifest['node'],str(REPO/'integrations/dsh/dev/l01.mjs'),args.mode,str(out)]
    if args.offline_stream_failure:payload.extend(['','','stream-finalization'])
    if args.offline_terminal_rejection:payload.extend(['','','terminal-rejection'])
    if args.offline_provider_error:payload.extend(['','','provider-error'])
    ro=[]
    if args.mode=='live':
        # The original complete certificate's dependency closure remains RO.
        # No isolated offline permit is converted to model authority.
        from code2paper.integrations.dsh.offline_inputs import coverage_readonly_inputs
        _, closure=coverage_readonly_inputs(args.receipt.resolve(),candidate=candidate,engine_root=REPO)
        ro.extend(closure)
        ro.append(args.authorization.resolve())
        ro.extend([dev.DSH_HOME/'profiles',dev.PYWORKER])
        payload.extend([str(args.receipt.resolve()),str(args.authorization.resolve())])
    argv=dev.sandbox_command(manifest,payload,cwd=REPO,offline=args.mode!='live',
        output_root=out,readonly_inputs=ro,
        shared_backend_root=backend_root if args.mode=='live' else None)
    record={'mode':args.mode,'argv':argv,'cwd':str(REPO),'output':str(out),
        'scope':'original sandbox; original production task/fee/ingest owners','inference_authorized':args.mode=='live'}
    (out/'launch-record.json').write_text(json.dumps(record,indent=2)+'\n')
    with (out/('driver-'+args.mode+'.log')).open('w') as log:
        result=subprocess.run(argv,cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=360)
    print(json.dumps({'exit_code':result.returncode,'output':str(out),'log':str(out/('driver-'+args.mode+'.log'))}))
    return result.returncode

if __name__=='__main__': raise SystemExit(main())

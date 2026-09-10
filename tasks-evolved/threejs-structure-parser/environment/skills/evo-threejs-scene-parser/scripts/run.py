"""Python wrapper to run the Node parser."""
import subprocess, json, os, sys

def run_threejs_parser(scene_path: str, output_dir: str):
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parser.mjs')
    # node needs to find the 'three' module. Run from /root where node_modules exists.
    cwd = '/root'
    cmd = ['node', script, scene_path, output_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print('STDERR:', result.stderr, file=sys.stderr)
        print('STDOUT:', result.stdout, file=sys.stderr)
        raise RuntimeError(f'Parser failed: {result.stderr}')
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except Exception:
        print('STDOUT:', result.stdout)
        raise

if __name__ == '__main__':
    scene = sys.argv[1] if len(sys.argv) > 1 else '/root/data/object.js'
    out = sys.argv[2] if len(sys.argv) > 2 else '/root/output'
    res = run_threejs_parser(scene, out)
    print(json.dumps(res, indent=2))

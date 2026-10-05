"""gate の規則（K819）: gate=true は「基点（HEAD の写し）が出来事として読む文」だけ。基点の semantic_reader.document_view に「unsupported が空で modality が assert の節」があるか（門が触る節）を、
基点の木を PYTHONPATH にした子プロセスで測る。門が触るのは基点で読めている節だけ（設計 H801）なので、基点で読めない文には MODALITY_NOT_READ は付かない。"""
import json, subprocess, sys

def base_readable(base, python, documents):
    code = ("import sys,json\nfrom verantyx import semantic_reader as s, __file__ as _f\n"
            "assert _f.startswith(sys.argv[1]), _f\n"
            "print(json.dumps([any((not c.unsupported) and c.modality == 'assert' for c in s.document_view({'d': d}).clauses) for d in json.loads(sys.stdin.read())]))")
    out = subprocess.run([python, '-c', code, base], input=json.dumps(documents), capture_output=True, text=True,
                         env={'PYTHONPATH': base, 'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin'}, cwd=base)
    if out.returncode: raise SystemExit(out.stderr)
    return dict(zip(documents, json.loads(out.stdout.strip().splitlines()[-1])))


def base_answers(base, python, pairs, tmpdir):
    """基点の木の ask --mode round5 --document が、(文, 問い) に ANSWER を返すか。converse の gate の第 2 の条件（ask の理由に MODALITY_NOT_READ が出るのは、
    基点が答えていた形だけ。基点が別の理由で棄権する形は、理由が基点のまま）。"""
    code = ("import sys,json,io,contextlib,tempfile\nfrom pathlib import Path\nfrom verantyx import cli, __file__ as _f\nassert _f.startswith(sys.argv[1]), _f\n"
            "out=[]\nfor d,q in json.loads(sys.stdin.read()):\n    t=Path(tempfile.mkdtemp(dir=sys.argv[2])); (t/'d.txt').write_text(d+'\\n')\n    b=io.StringIO()\n"
            "    with contextlib.redirect_stdout(b): cli.main(['--store',str(t/'st.json'),'ask','--mode','round5','--document',str(t/'d.txt'),'--',q])\n"
            "    out.append(json.loads(b.getvalue()).get('verdict')=='ANSWER')\nprint(json.dumps(out))")
    r = subprocess.run([python, '-c', code, base, str(tmpdir)], input=json.dumps(pairs), capture_output=True, text=True,
                       env={'PYTHONPATH': base, 'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin'}, cwd=base)
    if r.returncode: raise SystemExit(r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])

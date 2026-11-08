"""Additional native portable acceptance; owned processes/files only, no ACL edits."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import time
from benchmarks.windows_release_smoke import App


def processes():
    class ENTRY(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('uses',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),
                  ('name',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(ENTRY)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(ENTRY)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows=[]
    try:
        row=ENTRY();row.size=ctypes.sizeof(row)
        ok=kernel.Process32FirstW(snapshot,ctypes.byref(row))
        while ok:
            rows.append({'pid':row.pid,'parent':row.parent,'name':row.name})
            ok=kernel.Process32NextW(snapshot,ctypes.byref(row))
    finally:
        kernel.CloseHandle(snapshot)
    return rows


def terminate_owned_child(app,pid):
    assert any(p['pid']==pid and p['parent']==app.proc.pid for p in processes())
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x0001,False,pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.TerminateProcess(handle,91):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def run(exe,output):
    exe=Path(exe).resolve();output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    unrelated=output/'別 cwd';unrelated.mkdir(exist_ok=True)
    temp=output/'別 TEMP';temp.mkdir(exist_ok=True)
    report={'no_arguments':True,'elevated':bool(ctypes.windll.shell32.IsUserAnAdmin()),'rows':[]}
    # Misleading old per-user roots are left unused, even with a different cwd.
    app=App(exe,local=output/'not-used-profile',temp=temp,cwd=unrelated)
    try:
        app.settings('normal');app.start();app.cell(7,7);time.sleep(2.3)
        saved,path=app.save()
        assert path.parent==exe.parent and len(saved['move_history'])==2,saved
        assert not list(unrelated.glob('gomoku_save_*.json'))
        assert not (output/'not-used-profile'/'Gomoku2').exists()
        app.capture(output/'different-cwd-save.png')
        app.stop(via_quit=False)
        report['rows'].append({'case':'different_cwd_and_temp','save_beside_exe':True,
                               'saved_moves':saved['move_history'],'exit_code':app.proc.returncode})
    finally:
        app.kill_owned()
    # A file obstructing only the owned worker root produces a visible error;
    # no fallback or process startup should occur.
    workers=exe.parent/'workers'
    assert not workers.exists() or not list(workers.iterdir())
    if workers.exists():
        workers.rmdir()  # exact owned empty runtime root, never a recursive delete.
    workers.write_text('intentional test obstruction',encoding='utf-8')
    app=App(exe,cwd=unrelated)
    try:
        app.settings('easy');app.start();app.cell(7,7);time.sleep(.7)
        assert not [p for p in processes() if p['parent']==app.proc.pid]
        saved,path=app.save()
        assert saved['move_history']==[[7,7]],saved
        app.capture(output/'worker-failure.png')
        app.stop()
        report['rows'].append({'case':'worker_root_obstructed','no_child':True,
                               'no_false_ai_move':True,'gui_save_still_works':True,'exit_code':app.proc.returncode})
    finally:
        app.kill_owned()
        assert workers.is_file() and workers.read_text()=='intentional test obstruction'
        workers.unlink()  # exact owned marker created immediately above.
    # Abnormal worker exit: terminate only a proven direct child of this app.
    app=App(exe)
    try:
        app.settings('very_hard');app.start();time.sleep(.4)
        app.click(400,340,pause=.01)
        found=app.wait(lambda:[p for p in processes() if p['parent']==app.proc.pid],5,'owned AI child')
        for child in found:
            terminate_owned_child(app,child['pid'])
        time.sleep(1.1)
        app.capture(output/'abnormal-worker.png')
        saved,path=app.save()
        assert saved['move_history']==[[7,7]],saved
        app.stop()
        app.wait(lambda:not [p for p in processes() if p['parent']==app.proc.pid],2,'no child residue')
        report['rows'].append({'case':'abnormal_worker_exit','child_count':len(found),
                               'no_false_ai_move':True,'exit_code':app.proc.returncode})
    finally:
        app.kill_owned()
    assert not (exe.parent/'_internal/pygame/freesansbold.ttf').exists()
    assert (exe.parent/'_internal/fonts/UiSans.ttf').is_file()
    assert not list((exe.parent/'workers').glob('renju-ai-*'))
    report['pass']=True
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('exe');parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.exe,args.output)

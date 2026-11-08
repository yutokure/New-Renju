"""Drive the actual packaged Windows SDL GUI using native window messages.

Uses only its own PID/window, explicit worker root and disposable save cwd.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time
from PIL import ImageGrab


def main(exe,root):
    exe=Path(exe).resolve()
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user.EnumWindows.argtypes=[ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM),wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    env=os.environ.copy()
    for name in ('SDL_VIDEODRIVER','SDL_AUDIODRIVER'):
        env.pop(name,None)
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    proc=subprocess.Popen([str(exe),'--worker-directory',str(root)],cwd=root,env=env,
                          stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    hwnd=None
    def windows():
        matches=[]
        @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        def callback(handle,_):
            pid=wintypes.DWORD()
            user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if pid.value==proc.pid and user.IsWindowVisible(handle):
                matches.append(handle)
            return True
        user.EnumWindows(callback,0)
        return matches
    def click(x,y):
        packed=(y<<16)|x
        user.PostMessageW(hwnd,0x200,0,packed)
        user.PostMessageW(hwnd,0x201,1,packed)
        user.PostMessageW(hwnd,0x202,0,packed)
        time.sleep(.25)
    def key(code):
        user.PostMessageW(hwnd,0x100,code,0)
        user.PostMessageW(hwnd,0x101,code,0)
        time.sleep(.25)
    def capture(name):
        rect=wintypes.RECT()
        user.GetWindowRect(hwnd,ctypes.byref(rect))
        user.SetForegroundWindow(hwnd)
        time.sleep(.1)
        ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom)).save(name)
    result={'explicit_worker_root':True,'pid':proc.pid}
    try:
        end=time.perf_counter()+8
        while not hwnd and time.perf_counter()<end:
            handles=windows()
            hwnd=handles[0] if handles else None
            if hwnd is None:
                time.sleep(.05)
        assert hwnd,'Packaged GUI did not create a visible window'
        time.sleep(.5)
        click(400,405)  # Settings
        click(585,350)  # Normal -> Hard
        click(585,350)  # Hard -> Very Hard
        capture('benchmarks/results/frozen-gui-settings.png')
        click(400,520)  # Back
        click(400,265)  # New game
        time.sleep(3)
        click(400,310)  # Human black center
        time.sleep(7.5)  # VH default5s plus imports, animation and telop transition.
        capture('benchmarks/results/frozen-gui-game.png')
        click(500,60)   # Save after worker completion
        saves=sorted(root.glob('gomoku_save_*.json'),key=lambda p:p.stat().st_mtime)
        assert saves,'Native Save click did not produce save evidence'
        save=json.loads(saves[-1].read_text())
        result['saved_settings']=save['settings']
        result['saved_move_history']=save['move_history']
        assert save['settings']['ai_difficulty']=='very_hard',result
        assert len(save['move_history'])>=2 and save['move_history'][0]==[7,7],result
        # Cancel/return to menu through the real game event path, then close.
        key(27)
        capture('benchmarks/results/frozen-gui-menu.png')
        user.PostMessageW(hwnd,0x10,0,0)
        proc.wait(timeout=5)
        result.update(exit_code=proc.returncode,clean_exit=proc.returncode==0,
                      worker_directories_after_exit=len(list(root.glob('renju-ai-*'))))
        assert result['clean_exit'] and result['worker_directories_after_exit']==0,result
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
    Path('benchmarks/results/frozen-gui-explicit-root.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('exe')
    p.add_argument('--request-root',required=True)
    args=p.parse_args()
    main(args.exe,args.request_root)

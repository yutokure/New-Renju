"""Serial native Windows GUI acceptance against the actual onedir executable.

No automation/test branch inside the product: this sends real window messages,
reads actual saved records and snapshots only owned worker/temp paths.
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


class App:
    def __init__(self,exe,local=None,temp=None,cwd=None):
        self.exe=Path(exe).resolve()
        self.local=Path(local) if local is not None else Path(os.environ['LOCALAPPDATA'])
        self.root=self.local/'Gomoku2'
        self.env=os.environ.copy()
        for key in ('SDL_VIDEODRIVER','SDL_AUDIODRIVER'):
            self.env.pop(key,None)
        if local is not None:
            self.env['LOCALAPPDATA']=str(local)
        if temp is not None:
            self.env['TEMP']=self.env['TMP']=str(temp)
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        self.user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        self.user.IsWindowVisible.argtypes=[wintypes.HWND]
        self.user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        self.user.SetForegroundWindow.argtypes=[wintypes.HWND]
        self.user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
        self.user.SetActiveWindow.argtypes=[wintypes.HWND]
        self.user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        self.proc=subprocess.Popen([str(self.exe)],cwd=cwd or self.exe.parent,env=self.env,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.hwnd=None
        self.wait(lambda:self.find_window(),8,'visible main window')
        time.sleep(.25)
    @staticmethod
    def wait(check,seconds,label):
        deadline=time.perf_counter()+seconds
        while time.perf_counter()<deadline:
            value=check()
            if value:
                return value
            time.sleep(.04)
        raise AssertionError('Timeout: '+label)
    def find_window(self):
        matches=[]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        @callback_type
        def callback(handle,_):
            pid=wintypes.DWORD()
            self.user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if pid.value==self.proc.pid and self.user.IsWindowVisible(handle):
                matches.append(handle)
            return True
        self.user.EnumWindows(callback,0)
        if matches:
            self.hwnd=matches[0]
        return self.hwnd
    def click(self,x,y,pause=.15):
        assert self.proc.poll() is None,'GUI exited unexpectedly'
        self.user.ShowWindow(self.hwnd,9)
        self.user.SetForegroundWindow(self.hwnd)
        packed=(y<<16)|x
        self.user.PostMessageW(self.hwnd,0x200,0,packed)
        self.user.PostMessageW(self.hwnd,0x201,1,packed)
        self.user.PostMessageW(self.hwnd,0x202,0,packed)
        time.sleep(pause)
    def key(self,key,pause=.15):
        self.user.PostMessageW(self.hwnd,0x100,key,0)
        self.user.PostMessageW(self.hwnd,0x101,key,0)
        time.sleep(pause)
    def capture(self,path):
        rect=wintypes.RECT()
        self.user.GetWindowRect(self.hwnd,ctypes.byref(rect))
        self.user.ShowWindow(self.hwnd,9)
        self.user.SetForegroundWindow(self.hwnd)
        time.sleep(.25)
        # Record native visible desktop evidence; verify each image manually.
        ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom)).save(path)
    def saves(self):
        directory=self.root/'Saves'
        return set(directory.glob('gomoku_save_*.json')) if directory.is_dir() else set()
    def save(self):
        before=self.saves()
        self.click(500,60)
        files=self.wait(lambda:self.saves()-before,2,'new atomic save')
        file=max(files,key=lambda p:p.stat().st_mtime_ns)
        return json.loads(file.read_text(encoding='utf-8')),file
    def settings(self,difficulty='normal',mode=1,target=5):
        self.click(400,405)
        for _ in range(mode-1 if mode>=1 else 1):
            self.click(610 if mode>=1 else 280,290)
        levels=['easy','normal','hard','very_hard']
        for _ in range((levels.index(difficulty)-1)%4):
            if mode != 0:
                self.click(610,350)
        for _ in range((target-5)%5):
            self.click(610,230)
        self.click(400,520)
    def start(self):
        self.click(400,265,.3)
    def cell(self,row,col):
        self.click(225+col*25,165+row*25,.4)
    def stop(self,via_quit=False):
        if self.proc.poll() is None:
            if via_quit:
                self.click(720,60)
                self.click(400,475)
            else:
                self.user.PostMessageW(self.hwnd,0x10,0,0)
            self.proc.wait(timeout=6)
        assert self.proc.returncode==0, self.proc.returncode
        workers=self.root/'workers'
        leftovers=list(workers.glob('renju-ai-*')) if workers.is_dir() else []
        assert not leftovers,leftovers
        saves=self.root/'Saves'
        assert not list(saves.glob('.gomoku-save-*.tmp')) if saves.is_dir() else True
    def kill_owned(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=3)


def run(exe,output,local=None,temp=None):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    report={'exe':str(Path(exe).resolve()),'no_arguments':True,'os':os.name,
            'elevated':bool(ctypes.windll.shell32.IsUserAnAdmin()),'rows':[]}
    for difficulty in ('easy','normal','hard','very_hard'):
        app=App(exe,local,temp)
        try:
            app.capture(output/(difficulty+'-menu.png'))
            # About uses central identity.
            if difficulty=='normal':
                app.click(570,555)
                app.capture(output/'about.png')
                app.click(400,564)
            app.settings(difficulty)
            app.start()
            app.cell(7,7)
            # Avoid S during active search: S intentionally cancels workers.
            time.sleep(2.5 if difficulty!='very_hard' else 6.5)
            saved,file=app.save()
            assert saved['settings']['ai_difficulty']==difficulty,saved
            assert saved['move_history'][0]==[7,7] and len(saved['move_history'])==2,saved
            assert saved['move_history'][1] in ([6,7],[6,8]),saved
            app.capture(output/(difficulty+'-reply.png'))
            # Prev, failed save in history, Next, then save current again.
            app.click(320,555)
            before=app.saves()
            app.click(500,60)
            assert app.saves()==before,'history save was accepted'
            app.capture(output/(difficulty+'-history.png'))
            app.click(480,555)
            again,_=app.save()
            assert again['move_history']==saved['move_history']
            app.click(720,60)
            app.click(400,335)
            app.click(400,150,.5)
            reloaded,_=app.save()
            assert reloaded['settings']==saved['settings'] and reloaded['move_history']==saved['move_history']
            app.capture(output/(difficulty+'-reloaded.png'))
            app.stop(via_quit=True)
            report['rows'].append({'difficulty':difficulty,'mode':'Human vs AI','saved_settings':saved['settings'],
                'history':saved['move_history'],'save_load_history':True,'exit_code':app.proc.returncode,
                'worker_cleanup':True,'save_path':str(file)})
        finally:
            app.kill_owned()
    # Human/Human connect3 terminal and rematch through real GUI.
    app=App(exe,local,temp)
    try:
        app.settings('normal',mode=0,target=3)
        app.start()
        # Custom target3 unchanged geometry at same board15.
        for row,col in ((7,7),(6,7),(7,6),(6,8),(7,5)):
            app.cell(row,col)
        saved,_=app.save()
        assert saved['settings']['game_mode']==[0,0] and saved['settings']['win_length']==3
        assert len(saved['move_history'])==5,saved
        app.capture(output/'human-human-terminal.png')
        app.click(300,400,.3)
        reset,_=app.save()
        assert reset['move_history']==[]
        app.stop()
        report['rows'].append({'mode':'Human vs Human','terminal_history':saved['move_history'],
            'rematch_empty':True,'exit_code':app.proc.returncode,'worker_cleanup':True})
    finally:
        app.kill_owned()
    for mode,name in ((2,'AI vs Human'),(3,'AI vs AI')):
        app=App(exe,local,temp)
        try:
            app.settings('easy',mode=mode)
            app.start()
            time.sleep(1.7)
            if mode==2:
                saved,_=app.save()
                assert saved['move_history']==[[7,7]],saved
                # Save cancels AI Telop into fade-out; update must finish that
                # transition before a human point is accepted, as in normal UI.
                time.sleep(.5)
                app.cell(6,7)
                time.sleep(2.0)
            else:
                time.sleep(1.5)
            saved,_=app.save()
            assert saved['settings']['game_mode']==([1,0] if mode==2 else [1,1]),saved
            assert len(saved['move_history'])>=3 if mode==2 else len(saved['move_history'])>=2,saved
            app.capture(output/('mode-'+str(mode)+'.png'))
            app.stop()
            report['rows'].append({'mode':name,'history':saved['move_history'],'exit_code':app.proc.returncode,
                                   'worker_cleanup':True})
        finally:
            app.kill_owned()
    report['pass']=True
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('exe')
    p.add_argument('--output',required=True)
    p.add_argument('--local-app-data')
    p.add_argument('--temp')
    a=p.parse_args()
    run(a.exe,a.output,a.local_app_data,a.temp)

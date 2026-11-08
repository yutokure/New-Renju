"""Capture an owned native HWND without focus or third-party desktop content."""
import ctypes
from ctypes import wintypes
from PIL import Image


def capture(hwnd,path):
    user=ctypes.WinDLL('user32',use_last_error=True)
    gdi=ctypes.WinDLL('gdi32',use_last_error=True)
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.GetWindowDC.argtypes=[wintypes.HWND];user.GetWindowDC.restype=wintypes.HDC
    user.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
    user.PrintWindow.argtypes=[wintypes.HWND,wintypes.HDC,wintypes.UINT]
    gdi.CreateCompatibleDC.argtypes=[wintypes.HDC];gdi.CreateCompatibleDC.restype=wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int]
    gdi.CreateCompatibleBitmap.restype=wintypes.HBITMAP
    gdi.SelectObject.argtypes=[wintypes.HDC,wintypes.HANDLE];gdi.SelectObject.restype=wintypes.HANDLE
    gdi.DeleteObject.argtypes=[wintypes.HANDLE];gdi.DeleteDC.argtypes=[wintypes.HDC]
    class HEADER(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),
            ('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),
            ('image_size',wintypes.DWORD),('x',wintypes.LONG),('y',wintypes.LONG),
            ('used',wintypes.DWORD),('important',wintypes.DWORD)]
    gdi.GetDIBits.argtypes=[wintypes.HDC,wintypes.HBITMAP,wintypes.UINT,wintypes.UINT,
                          ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
    rect=wintypes.RECT();assert user.GetWindowRect(hwnd,ctypes.byref(rect))
    width,height=rect.right-rect.left,rect.bottom-rect.top
    source=user.GetWindowDC(hwnd);memory=gdi.CreateCompatibleDC(source)
    bitmap=gdi.CreateCompatibleBitmap(source,width,height)
    previous=gdi.SelectObject(memory,bitmap)
    try:
        assert user.PrintWindow(hwnd,memory,2),'PrintWindow failed'
        gdi.SelectObject(memory,previous)
        header=HEADER(ctypes.sizeof(HEADER),width,-height,1,32,0,width*height*4,0,0,0,0)
        data=ctypes.create_string_buffer(width*height*4)
        assert gdi.GetDIBits(memory,bitmap,0,height,data,ctypes.byref(header),0)==height
        Image.frombuffer('RGB',(width,height),data.raw,'raw','BGRX',0,1).save(path)
    finally:
        gdi.SelectObject(memory,previous)
        gdi.DeleteObject(bitmap);gdi.DeleteDC(memory);user.ReleaseDC(hwnd,source)

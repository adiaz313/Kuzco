"""Read-only default-input observation; refresh only Kuzco's closed audio runtime.

No device setters, Bluetooth operations or PortAudio enumeration during capture.
"""
import ctypes
from functools import lru_cache
import sys
import time
from speech_input import VoiceInputError


class Address(ctypes.Structure):
    _fields_=[('selector',ctypes.c_uint32),('scope',ctypes.c_uint32),('element',ctypes.c_uint32)]


@lru_cache(maxsize=1)
def coreaudio():
    lib=ctypes.CDLL('/System/Library/Frameworks/CoreAudio.framework/CoreAudio')
    lib.AudioObjectGetPropertyData.argtypes=[ctypes.c_uint32,ctypes.POINTER(Address),ctypes.c_uint32,
        ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32),ctypes.c_void_p]
    lib.AudioObjectGetPropertyData.restype=ctypes.c_int32
    return lib


def default_input():
    if sys.platform!='darwin':return None
    try:
        address=Address(int.from_bytes(b'dIn ','big'),int.from_bytes(b'glob','big'),0)
        value=ctypes.c_uint32();size=ctypes.c_uint32(ctypes.sizeof(value))
        status=coreaudio().AudioObjectGetPropertyData(1,ctypes.byref(address),0,None,ctypes.byref(size),ctypes.byref(value))
        return value.value if status==0 else None
    except (OSError,AttributeError):return None


class InputChanged(VoiceInputError):pass


class InputWatch:
    def __init__(self,query=None,clock=None):
        self.query=query or default_input;self.clock=clock or time.monotonic
        self.selected=self.query();self.checked=self.clock()

    def check(self):
        now=self.clock()
        if now-self.checked<1:return
        self.checked=now
        current=self.query()
        if current is not None and self.selected is not None and current!=self.selected:
            raise InputChanged('macOS default input changed; reopening selected microphone')
        if self.selected is None:self.selected=current


def refresh(sd):
    """Call only after the RawInputStream context has closed (one owner).

    The pinned sounddevice wrapper exposes no public refresh API. These paired
    lifecycle helpers wrap Pa_Terminate/Pa_Initialize and update its exit counter.
    """
    if not hasattr(sd,'_terminate') or not hasattr(sd,'_initialize'):
        raise VoiceInputError('Audio runtime cannot refresh devices; restart Kuzco')
    if getattr(sd,'_initialized',1)>0:sd._terminate()
    sd._initialize()

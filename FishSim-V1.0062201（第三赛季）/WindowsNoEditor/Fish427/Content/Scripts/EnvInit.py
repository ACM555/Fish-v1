import unreal_engine as ue
from threading import Thread
import cue as mycue
from unreal_engine import FVector, FRotator, FTransform
import gc
import time
print(f"EnvInit")
class EnvInit:
    def begin_play(self):
        self.uobject.get_owner().bind_event('OnEnd',self.on_end_play) 
        print('EnvInit begin_play')
    def on_end_play(self): 
        gc.collect()
        print("EnvInit ue destroyed EnvInit")
        
import unreal_engine as ue

from unreal_engine import FLinearColor

import inspect

import sys
import os
pa = os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))#pa = os.path.abspath(os.path.join('..', '..','Content','Scripts'))
sys.path.append(pa)

import Main as m





class TestFishPy:

    def begin_play(self):
        #m.pbs.initttt()
        #m.oncb('ddddddddd')
        m.pbs.publisher.subscribe(self.oncb4)
        m.pbs.getInforpublisher.subscribe(self.getFishInfo)
        m.pbs.fishPy = self
        #m.aaa('aaa')
#publisher.aaa()
        #m.pbs.aaa()
        #publisher.subscribe(m.oncb)
        print('begin_play')
        
        self.uobject.get_owner().bind_event('OnTick',self.on_tick)
         

    def on_tick(self):

        print('calltol')

        
        print('calltol22')

        #self.uobject.get_owner().PointLight.SetLightColor(FLinearColor(test(),1,0,1))

        m.aaa()
        m.ontick()

        #m.pbs.publisher.publish("lalala", priority=2)

        print('done')
    
    def oncb4(self,data,priority=1):
        print(f"aaaaaa: {data} (aaaaa{priority})")

    def getFishInfo(self,data,priority=1):
        print(f"aaaaaa: {data} (aaaaa{priority})")
        return self.uobject.get_owner().call_function('getfishinfor')


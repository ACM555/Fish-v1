import unreal_engine as ue

from unreal_engine import FLinearColor

import inspect

import sys
import os
pa = os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))#pa = os.path.abspath(os.path.join('..', '..','Content','Scripts'))
sys.path.append(pa)

import Main as m



def oncb4(data,priority=1):
    print(f"aaaaaa: {data} (aaaaa{priority})")


class ChangeLight:

    def begin_play(self):
        #m.pbs.initttt()
        m.oncb('ddddddddd')
        m.pbs.publisher.subscribe(oncb4)
        #m.aaa('aaa')
#publisher.aaa()
        #m.pbs.aaa()
        #publisher.subscribe(m.oncb)
        print('begin_play')
        
        self.uobject.get_owner().bind_event('OnBeginPlay',self.turn_on_light)

    def turn_on_light(self):

        print('calltol')

        self.uobject.get_owner().PointLight.GetLightColor()
        print('calltol22')

        #self.uobject.get_owner().PointLight.SetLightColor(FLinearColor(test(),1,0,1))

        m.aaa()

        #m.pbs.publisher.publish("lalala", priority=2)

        print('done')


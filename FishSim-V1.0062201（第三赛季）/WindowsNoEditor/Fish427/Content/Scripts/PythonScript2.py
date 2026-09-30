import unreal_engine as ue

from unreal_engine import FLinearColor

class ChangeLight:

    def begin_play(self):
        
        self.uobject.get_owner().bind_event('OnBeginPlay',self.turn_on_light)

    def turn_on_light(self):

        self.uobject.get_owner().PointLight.SetLightColor(FlinearColor(0,1,0,1))

        print('done')
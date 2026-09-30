import unreal_engine as ue
from threading import Thread
import cue as mycue
from unreal_engine import FVector, FRotator, FTransform
import gc


class TestDds:
    def on_lcb(self,fish_ctrl_info):
        a = fish_ctrl_info
        
        self.leftAngel = a.wing_target_angel_left
        self.rightAngel = a.wing_target_angel_right
        self.leftForce = a.wing_force_left
        self.rightForce = a.wing_force_right
        self.tailAngel = a.tail_target_angel
        
        #self.uobject.get_owner().call('FishCtrl a.wing_target_angel_left a.wing_target_angel_right a.wing_force_left a.wing_force_right a.tail_target_angel')
        print(f"ueonlcb{a}")
        #self.uobject.get_owner().call_function('getfishinfor')
    
    def run_server(self):
        server = SimpleXMLRPCServer((rpc_server, rpc_port))
        server.register_function(self.get_name, "get_name")
        print("runserver...")
        server.serve_forever()
    def run_t(self):
        self.uobject.get_owner().call('CustomEvent_0')        
        print("run_t...")
        
    def begin_play(self):
        print('begin_play')
        self.uobject.get_owner().bind_event('On_StartPlay',self.on_start_play)
                
        
    def on_tick(self):
        actor = self.uobject.get_owner()
        actor.leftAngelTemp = self.leftAngel
        actor.rightAngelTemp = self.rightAngel
        actor.leftForceTemp = self.leftForce
        actor.rightForceTemp = self.rightForce
        actor.tailAngelTemp = self.tailAngel
        pos = actor.FishBody.get_world_location()#actor.get_actor_location(actor.FishBody)#actor.FishBody.get_property('bAbsoluteLocation')
        rot = actor.FishBody.get_world_rotation()#actor.get_actor_rotation(actor.FishBody)#actor.FishBody.get_property('bAbsoluteRotation')
        fishInfo = mycue.FishInfo(pos = mycue.Mvector(pos.x,pos.y,pos.z),rot = mycue.Mvector(rot.roll,rot.pitch,rot.yaw))
        print(f"ontick fishinfo:{fishInfo}")
        self.pbspulisher111.pbspublish(fishInfo)
        #properties_list = actor.FishBody.properties()
        #print(f"ontick fishinfo:{properties_list}")
                        

        print(f"ontick setleftangeltemp:{self.leftAngel}")
        print(f"ontick setleftangeltemp:{self.rightAngel}")
        print(f"ontick setleftangeltemp:{self.leftForce}")
        print(f"ontick setleftangeltemp:{self.rightForce}")
        print(f"ontick setleftangeltemp:{self.tailAngel}")
        
        print(">> Wrote vehicle")
    def on_start_play(self): 
        actor = self.uobject.get_owner()
        
        self.pbspulisher111 = mycue.pbspublisher('info' + actor.topicUid,mycue.FishInfo)
        self.uobject.get_owner().bind_event('OnTick',self.on_tick)
        self.leftAngel = 0
        self.rightAngel = 0
        self.leftForce = 0
        self.rightForce = 0
        self.tailAngel = 0
        
        self.uobject.get_owner().bind_event('On_EndPlay',self.on_end_play)
        self.pbssubscriber111 = mycue.pbssubscriber('ctrl' + actor.topicUid ,mycue.FishCtrlInfo,self.on_lcb)
        #self.publishVec = mycue.Vehicle(name="Dallara lalala",pos = mycue.Mvector(3,4,3),rot = mycue.Mvector(3,7,3))
        #self.uobject.get_owner().call('UpForce')

    def on_end_play(self): 
        del self.pbssubscriber111
        gc.collect()
        print("destroyedddd")
    
    
        
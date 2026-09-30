import unreal_engine as ue
from threading import Thread
import cue as mycue
from unreal_engine import FVector, FRotator, FTransform
import gc


class FishProject2:
    def set_fish_ctrl_info_list(self,fish_ctrl_info_list,selfIndex,dataIndex):
            self.leftAngel[selfIndex] = fish_ctrl_info_list.fishCtrlInfo[dataIndex].wing_target_angel_left
            self.rightAngel[selfIndex] = fish_ctrl_info_list.fishCtrlInfo[dataIndex].wing_target_angel_right
            self.leftForce[selfIndex] = fish_ctrl_info_list.fishCtrlInfo[dataIndex].wing_force_left
            self.rightForce[selfIndex] = fish_ctrl_info_list.fishCtrlInfo[dataIndex].wing_force_right
            self.tailAngel[selfIndex] = fish_ctrl_info_list.fishCtrlInfo[dataIndex].tail_target_angel

    def on_lcb0(self,fish_ctrl_info_list):
        print(f"FishProject2 ueonlcb1{fish_ctrl_info_list}")
        if hasattr(fish_ctrl_info_list, "fishCtrlInfo") and len(fish_ctrl_info_list.fishCtrlInfo) == 2: 
            self.set_fish_ctrl_info_list(fish_ctrl_info_list,0,0)
            self.set_fish_ctrl_info_list(fish_ctrl_info_list,1,1)   
        
    def on_lcb1(self,fish_ctrl_info_list):
        print(f"FishProject2 ueonlcb2{fish_ctrl_info_list}")
        if hasattr(fish_ctrl_info_list, "fishCtrlInfo") and len(fish_ctrl_info_list.fishCtrlInfo) == 2: 
            self.set_fish_ctrl_info_list(fish_ctrl_info_list,2,0)
            self.set_fish_ctrl_info_list(fish_ctrl_info_list,3,1)   
           
    def begin_play(self):
        print('begin_play FishProject2')
        self.uobject.get_owner().bind_event('On_StartPlay',self.on_start_play)
                
        
    def on_tick(self):
        actor = self.uobject.get_owner()
        #actor.tailAngelTemp = self.tailAngel
        pos0 = actor.fishCompArray[0].FishBody.get_world_location()
        rot0 = actor.fishCompArray[0].FishBody.get_world_rotation()
        forw0 = actor.fishCompArray[0].FishBody.get_forward_vector()
        pos1 = actor.fishCompArray[1].FishBody.get_world_location()
        rot1 = actor.fishCompArray[1].FishBody.get_world_rotation()
        forw1 = actor.fishCompArray[1].FishBody.get_forward_vector()
        pos2 = actor.fishCompArray[2].FishBody.get_world_location()
        rot2 = actor.fishCompArray[2].FishBody.get_world_rotation()
        forw2 = actor.fishCompArray[2].FishBody.get_forward_vector()
        pos3 = actor.fishCompArray[3].FishBody.get_world_location()
        rot3 = actor.fishCompArray[3].FishBody.get_world_rotation()
        forw3 = actor.fishCompArray[3].FishBody.get_forward_vector()
        posBall = actor.Ball.get_world_location()
        fishInfoList0 = [mycue.FishInfo(pos = mycue.Mvector(pos0.x,pos0.y,pos0.z),rot = mycue.Mvector(rot0.roll,rot0.pitch,rot0.yaw),forward = mycue.Mvector(forw0.x,forw0.y,forw0.z)),
                         mycue.FishInfo(pos = mycue.Mvector(pos1.x,pos1.y,pos1.z),rot = mycue.Mvector(rot1.roll,rot1.pitch,rot1.yaw),forward = mycue.Mvector(forw1.x,forw1.y,forw1.z)),
                         mycue.FishInfo(pos = mycue.Mvector(pos2.x,pos2.y,pos2.z),rot = mycue.Mvector(rot2.roll,rot2.pitch,rot2.yaw),forward = mycue.Mvector(forw2.x,forw2.y,forw2.z)),
                         mycue.FishInfo(pos = mycue.Mvector(pos3.x,pos3.y,pos3.z),rot = mycue.Mvector(rot3.roll,rot3.pitch,rot3.yaw),forward = mycue.Mvector(forw3.x,forw3.y,forw3.z))]
        fishInfoList1 = [mycue.FishInfo(pos = mycue.Mvector(pos2.x,pos2.y,pos2.z),rot = mycue.Mvector(rot2.roll,rot2.pitch,rot2.yaw),forward = mycue.Mvector(forw2.x,forw2.y,forw2.z)),
                         mycue.FishInfo(pos = mycue.Mvector(pos3.x,pos3.y,pos3.z),rot = mycue.Mvector(rot3.roll,rot3.pitch,rot3.yaw),forward = mycue.Mvector(forw3.x,forw3.y,forw3.z)),
                         mycue.FishInfo(pos = mycue.Mvector(pos0.x,pos0.y,pos0.z),rot = mycue.Mvector(rot0.roll,rot0.pitch,rot0.yaw),forward = mycue.Mvector(forw0.x,forw0.y,forw0.z)),
                         mycue.FishInfo(pos = mycue.Mvector(pos1.x,pos1.y,pos1.z),rot = mycue.Mvector(rot1.roll,rot1.pitch,rot1.yaw),forward = mycue.Mvector(forw1.x,forw1.y,forw1.z))]
        sceneInfo0 = mycue.SceneInfo(fishInfo = fishInfoList0,ballInfo = mycue.BallInfo(pos = mycue.Mvector(posBall.x,posBall.y,posBall.z)),teamID = 0)
        sceneInfo1 = mycue.SceneInfo(fishInfo = fishInfoList1,ballInfo = mycue.BallInfo(pos = mycue.Mvector(posBall.x,posBall.y,posBall.z)),teamID = 1)
        print(f"ontick fishinfo:{sceneInfo1}")
        self.pbspulisher0.pbspublish(sceneInfo0)
        self.pbspulisher1.pbspublish(sceneInfo1)
        
        for i in range(4):
            actor.call_function('PySetFishCtrlAtIndex', i, self.leftAngel[i],self.rightAngel[i],self.leftForce[i],self.rightForce[i],self.tailAngel[i]) 
        print(">> Wrote FishProject2")

    def on_start_play(self): 
        print('n_start_play FishProject2')
        actor = self.uobject.get_owner()
        self.pbspulisher0 = mycue.pbspublisher('info' + actor.topicUid0,mycue.SceneInfo)
        self.pbspulisher1 = mycue.pbspublisher('info' + actor.topicUid1,mycue.SceneInfo)
        self.uobject.get_owner().bind_event('OnTick',self.on_tick)
        self.leftAngel = [0,0,0,0]
        self.rightAngel = [0,0,0,0]
        self.leftForce = [0,0,0,0]
        self.rightForce = [0,0,0,0]
        self.tailAngel = [0,0,0,0]
        
        self.uobject.get_owner().bind_event('On_EndPlay',self.on_end_play)
        self.pbssubscriber0 = mycue.pbssubscriber('ctrl' + actor.topicUid0 ,mycue.FishCtrlInfoList,self.on_lcb0)
        self.pbssubscriber1 = mycue.pbssubscriber('ctrl' + actor.topicUid1 ,mycue.FishCtrlInfoList,self.on_lcb1)
                
        

    def on_end_play(self): 
        del self.pbssubscriber0
        del self.pbssubscriber1
        gc.collect()
        print("destroyedddd")
    
    
        
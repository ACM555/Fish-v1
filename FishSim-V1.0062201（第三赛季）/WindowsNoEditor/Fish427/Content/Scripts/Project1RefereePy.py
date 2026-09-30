import unreal_engine as ue
from threading import Thread
import cue as mycue
from unreal_engine import FVector, FRotator, FTransform
import gc
import time



class Project1Referee:
    def on_cb(self,requestData):
        if hasattr(requestData, "topic_uid"): 
            cb_data = requestData.topic_uid
            teamName = requestData.team_name
            print(f"Project1RefereePy ueonlcb{cb_data} time{self.timec}")

            if len(cb_data) > 0 :
                self.refereeTopicUid = cb_data
                self.teamName = teamName
                self.hasGetTopicUid = True
                
        b = hasattr(requestData, "topic_uid")
        print(f"Project1RefereePy uehasattr:{b}")
             
    def begin_play(self):
        print('Project1RefereePy begin_play')
        self.timec = time.time()
        self.refereeTopicUid = ''
        self.teamName =''
        self.hasGetTopicUid = False
        self.get_topicuid_subscriber = mycue.pbs_referee_subscriber(mycue.RequestData,self.on_cb)
        self.uobject.get_owner().bind_event('OnTick',self.on_tick)  
        self.uobject.get_owner().bind_event('OnEnd',self.on_end_play) 
        
    def on_tick(self):
        print(f"Project1Refeontick{self.refereeTopicUid}")
        if len(self.refereeTopicUid) > 0 :
            actor = self.uobject.get_owner()
            actor.refereeTopicUid = self.refereeTopicUid
            actor.teamName0 = self.teamName
            actor.hasGetTopicUid = self.hasGetTopicUid
    
    def on_end_play(self): 
        self.get_topicuid_subscriber.close()
        del self.get_topicuid_subscriber
        gc.collect()
        print("Project1RefereePy ue destroyed Project1RefereePy")

    
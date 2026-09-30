import unreal_engine as ue
from threading import Thread
import cue as mycue
from unreal_engine import FVector, FRotator, FTransform
import gc
import time


class Project2Referee:
    def on_cb(self,requestData):
        if hasattr(requestData, "topic_uid"): 
            cb_data = requestData.topic_uid
            teamName = requestData.team_name
            print(f"Project2Referee ueonlcb{cb_data} teamname:{teamName} time{self.timec} is not in:{cb_data not in  self.refereeTopicUid}")

            if len(cb_data) > 0 and cb_data not in  self.refereeTopicUid:
                self.refereeTopicUid.append(cb_data)
                self.teamName.append(teamName)
                #self.hasGetTopicUid = True
        
                            
        b = hasattr(requestData, "topic_uid")
        print(f"Project2Referee uehasattr:{b}")
             
    def begin_play(self):
        print('Project2Referee begin_play')
        self.timec = time.time()
        self.refereeTopicUid = []
        self.teamName = []
        self.hasGetTopicUid = False
        self.get_topicuid_subscriber = mycue.pbs_referee_subscriber(mycue.RequestData,self.on_cb)
        self.uobject.get_owner().bind_event('OnTick',self.on_tick)  
        self.uobject.get_owner().bind_event('OnEnd',self.on_end_play) 
        
    def on_tick_old(self):
        print(f"Project2Referee ontick{self.refereeTopicUid}")
        actor = self.uobject.get_owner()
        if len(self.refereeTopicUid) == 2 and actor.couldStart:
            print(f"Project2Referee ueontick len = 2 {self.refereeTopicUid}")
            actor.refereeTopicUid0 = self.refereeTopicUid[0]
            actor.refereeTopicUid1 = self.refereeTopicUid[1]
            actor.teamName0 = self.teamName[0]
            actor.teamName1 = self.teamName[1]
            actor.hasGetTopicUid = True

    def on_tick(self):
        print(f"Project2Referee ontick{self.refereeTopicUid}")
        actor = self.uobject.get_owner()
        if len(self.refereeTopicUid) == 1 and actor.couldStart:
            print(f"Project2Referee ueontick len = 2 {self.refereeTopicUid}")
            actor.refereeTopicUid0 = self.refereeTopicUid[0]
            #actor.refereeTopicUid1 = self.refereeTopicUid[1]
            actor.teamName0 = self.teamName[0]
            #actor.teamName1 = self.teamName[1]
            actor.hasGetTopicUid = True
    
    def on_end_play(self): 
        self.get_topicuid_subscriber.close()
        del self.get_topicuid_subscriber
        gc.collect()
        print("Project2Referee ue destroyed Project1RefereePy")

    
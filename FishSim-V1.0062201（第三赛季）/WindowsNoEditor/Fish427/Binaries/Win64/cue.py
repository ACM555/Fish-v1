import time
import random
import uuid

from cyclonedds.core import Listener, Qos, Policy
from cyclonedds.domain import DomainParticipant
from cyclonedds.pub import Publisher, DataWriter
from cyclonedds.sub import Subscriber, DataReader,ReadCondition, SampleState
from cyclonedds.topic import Topic
from cyclonedds.util import duration
from cyclonedds.builtin import BuiltinDataReader, BuiltinTopic

from FishProjectMsg import *

import threading
import gc

cue_id = ''


    
class publisher:
    def __init__(self,msgClass):

        self.qos = Qos(
        Policy.Reliability.Reliable(duration(microseconds=60)),
        Policy.Deadline(duration(microseconds=10)),
        Policy.Durability.TransientLocal,
        Policy.History.KeepLast(1)
        )
        self.topic_name = 'ctrl' + cue_id
        self.msg_class = msgClass
        self.domain_participant = DomainParticipant()
        self.topic = Topic(self.domain_participant, self.topic_name, self.msg_class, qos=self.qos)
        self.publisher = Publisher(self.domain_participant)
        self.writer = DataWriter(self.publisher, self.topic)
    def publish(self,msg_class):
        self.writer.write(msg_class)
        print(">>CUE Wrote")

class subscriber:
    def __init__(self,msgClass,listenerfunc):
        class MyListener(Listener):
            def __init__(self):
                super().__init__()
                
            def on_liveliness_changed(self, reader, status):
                print(">> Liveliness event")
            def on_data_available(self, reader):
                sample = reader.take()
                info = sample[0].sample_info
                data = sample[0]
                listenerfunc(data)
            def on_subscription_matched(self, reader,status):
                if status.current_count_change > 0:
                    print(f"新发布者匹配！当前匹配数: {status.current_count} last_publication_handle:{status.last_publication_handle} ")
                else:
                    print(f"发布者断开！剩余匹配数: {status.current_count}")
                
        self.qos = Qos(
        Policy.Reliability.Reliable(duration(microseconds=60)),
        Policy.Deadline(duration(microseconds=10)),
        Policy.Durability.TransientLocal,
        Policy.History.KeepLast(1)
        )
        self.topic_name = 'info' + cue_id
        self.msg_class = msgClass
        self.domain_participant = DomainParticipant()
        self.topic = Topic(self.domain_participant, self.topic_name, self.msg_class, qos=self.qos)
        self.subscriber = Subscriber(self.domain_participant)
        self.listener = MyListener()
        self.reader = DataReader(self.domain_participant, self.topic, listener=self.listener)
    def close(self):
        #self.reader.close()
        del self.reader
        #self.domain_participant.close()
        del self.domain_participant
        gc.collect()
    def runinit(self):
        while True:
            time.sleep(random.random() * 0.9 + 0.1)

class pbspublisher:
    def __init__(self,topicname,msgClass):

        self.qos = Qos(
        Policy.Reliability.Reliable(duration(microseconds=60)),
        Policy.Deadline(duration(microseconds=10)),
        Policy.Durability.TransientLocal,
        Policy.History.KeepLast(1)
        )
        self.topic_name = topicname
        self.msg_class = msgClass
        self.domain_participant = DomainParticipant()
        self.topic = Topic(self.domain_participant, self.topic_name, self.msg_class, qos=self.qos)
        self.publisher = Publisher(self.domain_participant)
        self.writer = DataWriter(self.publisher, self.topic)
    def pbspublish(self,msg_class):
        self.writer.write(msg_class)
        print(f">>CUE Wrote {msg_class}")
    


class pbssubscriber:
    def __init__(self,topicname,msgClass,listenerfunc):
        class MyListener(Listener):
            def __init__(self):
                super().__init__()
                
            def on_liveliness_changed(self, reader, status):
                print(">> Liveliness event")
            def on_data_available(self, reader):
                sample = reader.take()
                
                info = sample[0].sample_info
                data = sample[0]
                listenerfunc(data)
            def on_subscription_matched(self, reader,status):
                if status.current_count_change > 0:
                    print(f"新发布者匹配！当前匹配数: {status.current_count} last_publication_handle:{status.last_publication_handle} ")
                else:
                    print(f"发布者断开！剩余匹配数: {status.current_count}")
                
        self.qos = Qos(
        Policy.Reliability.Reliable(duration(microseconds=60)),
        Policy.Deadline(duration(microseconds=10)),
        Policy.Durability.TransientLocal,
        Policy.History.KeepLast(1)
        )
        self.topic_name = topicname
        self.msg_class = msgClass
        self.domain_participant = DomainParticipant()
        self.topic = Topic(self.domain_participant, self.topic_name, self.msg_class, qos=self.qos)
        self.subscriber = Subscriber(self.domain_participant)
        self.listener = MyListener()
        self.reader = DataReader(self.domain_participant, self.topic, listener=self.listener)
    def close(self):
        del self.reader
        del self.domain_participant
        gc.collect()
    def runinit(self):
        while True:
            time.sleep(random.random() * 0.9 + 0.1)
    
class pbs_referee_subscriber:
    def __init__(self,msgClass,listenerfunc):
        class MyListener(Listener):
            def __init__(self):
                super().__init__()
            def on_data_available(self, reader):
                sample = reader.take()
                data = sample[0]
                listenerfunc(data)
            def on_subscription_matched(self, reader,status):
                if status.current_count_change > 0:
                    print(f"新发布者匹配！当前匹配数: {status.current_count} last_publication_handle:{status.last_publication_handle}")
                else:
                    print(f"发布者断开！剩余匹配数: {status.current_count}")
        
                
        self.qos = Qos(
        Policy.Reliability.Reliable(duration(microseconds=60)),
        Policy.Deadline(duration(microseconds=10)),
        Policy.Durability.TransientLocal,
        Policy.History.KeepLast(1)
        )
        self.topic_name = 'get_uid'
        self.msg_class = RequestData
        self.domain_participant = DomainParticipant()
        self.topic = Topic(self.domain_participant, self.topic_name, self.msg_class, qos=self.qos)
        self.subscriber = Subscriber(self.domain_participant)
        self.listener = MyListener()
        self.reader = DataReader(self.domain_participant, self.topic, listener=self.listener)
    def close(self):
        del self.reader
        self.reader = None
        del self.subscriber
        self.subscriber = None
        del self.domain_participant
        self.domain_participant = None
        
def init(team_name = '未命名'):
    global cue_id
    cue_id = str(int(time.time() * 1e9))
    #cue_id ='111'
    print(f"cueid:{cue_id},team_name:{team_name}")
    requestData = RequestData()
    requestData.topic_uid = cue_id
    requestData.team_name = team_name
    cue_id_publisher = pbspublisher('get_uid',RequestData)
    cue_id_publisher.pbspublish(requestData)
    
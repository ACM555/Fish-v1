import cue as mycue
import time
import random

def calculate_fishCtrlInfo():
    ctrlInfo = mycue.FishCtrlInfo()
    return ctrlInfo
    
def lcb(scene_info):
    ctrlInfoList = mycue.FishCtrlInfoList(fishCtrlInfo = [mycue.FishCtrlInfo(),mycue.FishCtrlInfo()])
    ctrlInfo0 = calculate_fishCtrlInfo()
    ctrlInfo1 = calculate_fishCtrlInfo()
    ctrlInfoList.fishCtrlInfo = [ctrlInfo0,ctrlInfo1]
    pbspulisher.publish(ctrlInfoList)

mycue.init('F05012589')
sub = mycue.subscriber(mycue.SceneInfo,lcb)
pbspulisher = mycue.publisher(mycue.FishCtrlInfoList)

while True:
    time.sleep(1/60)


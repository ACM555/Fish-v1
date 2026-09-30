from enum import auto
from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

import cyclonedds.idl as idl
import cyclonedds.idl.annotations as annotate
import cyclonedds.idl.types as types
from cyclonedds.idl.types import sequence

@dataclass
class Mvector(idl.IdlStruct):
    x: types.float32 = 0
    y: types.float32 = 0
    z: types.float32 = 0
    
@dataclass
class FishInfo(idl.IdlStruct):
    pos: Mvector
    rot: Mvector
    forward: Mvector
    
@dataclass
class BallInfo(idl.IdlStruct):
    pos: Mvector
    
@dataclass
class FishCtrlInfo(idl.IdlStruct):
    wing_target_angel_left: types.float32 = 0
    wing_target_angel_right: types.float32 = 0
    wing_force_left: types.float32 = 0
    wing_force_right: types.float32 = 0
    tail_target_angel: types.float32 = 0

@dataclass
class FishCtrlInfoList(idl.IdlStruct):
    fishCtrlInfo:sequence[FishCtrlInfo]

@dataclass
class SceneInfo(idl.IdlStruct):
    fishInfo:sequence[FishInfo]
    ballInfo:BallInfo
    teamID:types.int32 = 0

@dataclass
class RequestData(idl.IdlStruct):
    topic_uid: str = ''
    team_name: str = '未命名'
    
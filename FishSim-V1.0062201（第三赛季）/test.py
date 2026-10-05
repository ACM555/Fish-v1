# -*- coding: utf-8 -*-
"""
第十九届先进机器人及仿真技术大赛
水中机器鱼仿真组（第三赛季）  科目一：障碍竞速
================================================================================
【裁判标准 PDF 要求】（第 3 页场地、第 5 页比赛内容）
  水池        3000 x 2000 x 1500 mm（水底中心为原点，x 前进方向，z 向上）
  出发点      (-1250, 0, 340)，以鱼身中心为 pivot
  终点        水池另一边线中间点 (1250, 0, 340)
  障碍物      200 x 200 x 1500 mm 方柱，共 3 个障碍
  路径        从起点出发 → 绕着障碍1 转 1 圈 → 穿过障碍2 → 绕着障碍3 转 2 圈 → 到达终点
  计时        平台记录用时，按用时升序排名；超过 60 s 记为失败

【本项目赛道实际坐标】（俯视图 俯视图.png 标注 + 裁判文件图2-1 实测）
  障碍1  (-750,    0)               单柱，绕 1 圈
  障碍2  (   0, +175) / (0, -175)   双柱"门"，中间缝隙 y ∈ (-75, +75)，从中穿过
  障碍3  ( 750,    0)               单柱，绕 2 圈

【必须遵守的参数限制】
  两侧胸鳍推进力   |wing_force_left/right| ≤ 50
  尾关节目标角度   |tail_target_angel| ≤ 80°
  （鱼身-鱼尾前部被动关节 ±10° 由平台自行模拟，无需也无法控制）

【实现思路】
  1. build_course() 用"直线 + 圆弧"拼出一条处处相切连续的赛道：
     绕柱圆半径 ORBIT_R = 230 mm（柱半宽 100 mm，即离柱面 130 mm），
     横向移位也用半径 230 mm 的 S 弯 —— 因为移位量正好等于绕柱半径，
     S 弯的第二段圆弧天然落在绕柱圆上，全路径只有一种曲率，弯道不需要额外减速。
  2. PurePursuit 按弧长做单调递增的前视跟踪（窗口只向前 200 mm），
     两圈绕柱靠"索引只增不减"实现；前视距离随目标速度自适应，过门时收紧到 85 mm。
  3. 速度规划：前方曲率同时受"侧向加速度 ≤1500 mm/s²"和"偏航角速度 ≤2.4 rad/s"
     两个上限约束 → 弯道自动降速、直道全速；再由 v→推力 换算
     （按实测约 14 mm/s 每单位推力），最后硬性限幅 ±50。
  4. 尾角 = **路径曲率前馈** + 航向 PID + 正弦摆尾：
     前馈按"当前速度 × 路径曲率"直接算出该转多少（ω = v·κ），尾巴立刻打到该有的角度，
     PID 只负责收拾剩余偏差；以前过弯全靠误差硬顶、稳态误差大、转不快，这是主要提速点。
     航向误差大时自动收油，另有超速收油保护。
  5. 胸鳍角度（wing_target_angel_left/right）用起来：
     -90° = 推力完全朝前（z 与 pitch 都不变），再用深度误差在 ±25° 内微调，
     把老版本"鳍角恒为 0 → 推力朝上 → 一直上浮抬头"的问题彻底修掉。
  6. 不需要状态机：路径本身已经按"绕1圈→穿门→绕2圈→终点"排好，
     只要沿着走就满足裁判的路线要求。
================================================================================
"""

import math
import time
from typing import List, Optional, Tuple

try:
    import cue as mycue
except Exception:          # 离线只跑路径/控制器自检时允许没有 cue 模块
    mycue = None


# =============================================================================
#                                 可调参数
# =============================================================================

TEAM_NAME = 'F05012589'          # 参赛队伍 ID（保持不变）

# ---- 赛道几何（单位 mm，水池坐标） ------------------------------------------
START = (-1250.0, 0.0)
FINISH = (1250.0, 0.0)
FINISH_STOP_X = 1265.0           # 冲过终点线后停推
ORBIT_R = 230.0                  # 绕单柱圆半径（柱半宽 100 → 离柱面 130，留足转向余量）
SAMPLE_STEP = 10.0               # 路径采样间距 mm

# ---- 速度规划（整体提速：全程基本满推，靠"航向误差收油"自适应过弯） --------
V_TOP = 900.0                    # 直道目标速度 mm/s（实际由推力上限决定）
A_LAT_MAX = 3200.0               # 允许侧向加速度 mm/s^2
YAW_RATE_MAX = 3.2               # 允许偏航角速度 rad/s（≈183°/s，弯道限速 v=w/kappa）
V_GATE = 600.0                   # 过门速度上限 mm/s（门缝 150 mm，路径在门区是直线，可快过）
GATE_X = (-380.0, 300.0)         # 过门限速区间（x）
MM_S_PER_FORCE = 14.0            # 推力→速度换算：每 1 单位推力约 14 mm/s
F_TOP = 48.0                     # 基础推力（限值 50，留 2 个单位余量）
F_MAX = 50.0                     # 裁判规定的推进力上限
FORCE_ERR_SLOW = 55.0            # 航向误差越大越收油（度）—— 过弯跟不住就自动减速
FORCE_ERR_MIN = 0.45             # 收油下限系数

# ---- 摆尾（摆频与动力成正比：这是除胸鳍推力外的主要提速手段） --------------
TAIL_AMP = 20.0                  # 摆尾幅度（度）
TAIL_FREQ = 2.20                 # 摆尾频率 Hz（摆频与动力成正比，这是第二个推进源）
TAIL_MAX = 80.0                  # 裁判规定的尾关节角度上限
CORR_LIMIT = 55.0                # 航向 PID 输出的尾角上限（给摆尾留余量）

# ---- 航向 PID + 曲率前馈 ----------------------------------------------------
YAW_KP = 2.20                    # 沿用原工程实测可用的参数
YAW_KI = 0.01
YAW_KD = 0.95
YAW_INTEGRAL_MAX = 50.0
YAW_GAIN_FF = 3.0                # 偏航角速度增益（deg/s per 1°尾角），用于曲率前馈
FF_LIMIT = 62.0                  # 前馈尾角上限（度）
FF_LEAD = 3                      # 前馈提前量（点数，约 30 mm）

# ---- 跟踪 -------------------------------------------------------------------
LOOKAHEAD_T = 0.24               # 前视时间常数：L = v * 0.24（小一点贴线更紧，过弯少切角）
LOOKAHEAD_MIN = 90.0
LOOKAHEAD_MAX = 170.0
GATE_LOOKAHEAD = 85.0            # 过门区间收紧前视，保证走直线
SEARCH_BACK = 5                  # 最近点回看窗口（点数，10 mm/点）
SEARCH_FWD = 20                  # 最近点前看窗口（点数）—— 防止跳段
CURV_LOOKAHEAD = 28              # 曲率预看点数（约 280 mm，速度高了要早点看到弯）

# ---- 胸鳍角度：决定推力朝哪个方向使 ----------------------------------------
#   侧视图实测含义：
#       0  = 推力朝上  （原框架从未赋值，默认就是 0 → 老版本鱼一直上浮、抬头）
#     -45  = 朝后上（倒退）
#     -90  = 完全朝前（z 不变、pitch 不变）← 水平推进
#    -100  = 朝前偏下（缓缓下潜）
WING_ANGLE_LEVEL = -90.0         # 水平推进角（把"往上顶"改成"往前推"）
DEPTH_TARGET = 340.0             # 目标深度（= 起点/终点高度 340）
DEPTH_ANGLE_KP = 0.10            # 深度误差 → 鳍角修正（度/mm）
DEPTH_ANGLE_LIMIT = 25.0         # 鳍角修正上限（度），保证推力主体仍然朝前
WING_ANGLE_MIN = -115.0          # 鳍角可用范围（再往下推力方向太斜，前进分量掉太多）
WING_ANGLE_MAX = -70.0

# ---- 姿态/推进保护 ----------------------------------------------------------
ROLL_GAIN = 0.0                  # 横滚差动增益（原工程取 0，实测更稳）
DEPTH_SOFT = 1100.0              # 高于此高度兜底收油（正常靠鳍角控深，不该用到）
DEPTH_SOFT_SCALE = 0.75
DEPTH_LOW = 120.0                # 低于此高度不加限制
OVERSPEED_TRIP = 1.20            # 实测速度超过目标 20% 就收油（防止弯道超速外切）
OVERSPEED_FLOOR = 0.50           # 最多收到 50%
SPEED_LP_TAU = 0.40              # 实测速度低通时间常数 s

# ---- 调试 -------------------------------------------------------------------
VERBOSE = True
LOG_EVERY = 30                   # 每 30 帧（约 0.5 s）打一条日志
CSV_EVERY = 6                    # 每 6 帧写一行 CSV（约 10 Hz）


# =============================================================================
#                              路径生成
# =============================================================================

Point = Tuple[float, float, float]      # (x, y, heading[rad])


def _wrap(a: float) -> float:
    """把角度标准化到 (-pi, pi]。"""
    return math.atan2(math.sin(a), math.cos(a))


def _line(p0, p1, step: float) -> List[Point]:
    """直线段采样（不含起点，含终点）。"""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return []
    heading = math.atan2(dy, dx)
    n = max(1, int(round(length / step)))
    return [(x0 + dx * i / n, y0 + dy * i / n, heading) for i in range(1, n + 1)]


def _arc(center, radius: float, a0_deg: float, a1_deg: float, step: float) -> List[Point]:
    """
    圆弧采样（不含起点，含终点）。
    a1 > a0 逆时针，a1 < a0 顺时针；切线方向由转向决定，与前后线段相切。
    """
    cx, cy = center
    a0 = math.radians(a0_deg)
    a1 = math.radians(a1_deg)
    total = a1 - a0
    if abs(total) < 1e-9:
        return []
    n = max(1, int(round(abs(total) * radius / step)))
    sign = math.pi / 2.0 if total > 0 else -math.pi / 2.0
    pts: List[Point] = []
    for i in range(1, n + 1):
        a = a0 + total * i / n
        pts.append((cx + radius * math.cos(a),
                    cy + radius * math.sin(a),
                    _wrap(a + sign)))
    return pts


def _lane_change(pts: List[Point], step: float, x0: float, y0: float, dy: float, r: float) -> float:
    """
    S 形变道：从 (x0, y0) 朝 +x 出发，横向平移 dy 后恢复朝 +x。
    两段圆弧半径都是 r，横向位移 dy = 2r(1-cosθ)，x 前进 dx = 2r·sinθ。
    返回前进的 x 距离 dx。dy>0 先左转后右转，dy<0 先右转后左转。
    """
    cos_t = 1.0 - abs(dy) / (2.0 * r)
    cos_t = max(-1.0, min(1.0, cos_t))
    theta = math.degrees(math.acos(cos_t))
    dx = 2.0 * r * math.sin(math.radians(theta))
    if dy > 0:                                   # 抬起
        pts.extend(_arc((x0, y0 + r), r, -90.0, -90.0 + theta, step))
        pts.extend(_arc((x0 + dx, y0 + dy - r), r, 90.0 + theta, 90.0, step))
    else:                                        # 压低
        pts.extend(_arc((x0, y0 - r), r, 90.0, 90.0 - theta, step))
        pts.extend(_arc((x0 + dx, y0 + dy + r), r, 270.0 - theta, 270.0, step))
    return dx


def build_course(step: float = SAMPLE_STEP) -> List[Point]:
    """
    生成整条赛道（处处相切连续，全部曲线半径 = ORBIT_R，离柱面 >= 130 mm）：

      起点 ─S弯抬到 y=+230 ─直线─ 障碍1 绕 1 圈(顺时针)
           ─S弯压回 y=0 ─直线穿过障碍2 门缝(y=0)
           ─S弯抬到 y=+230 ─ 障碍3 绕 2 圈(顺时针) ─S弯压回 y=0 ─直线─ 终点

    因为横向移位量 = 绕柱圆半径，S 弯的第二段圆弧正好落在绕柱圆上（半径相同、相切相接），
    所以全路径只有一种曲率 1/230，弯道不用额外减速。
    """
    pts: List[Point] = [(START[0], START[1], 0.0)]
    r_lane = ORBIT_R

    def line(p0, p1):
        pts.extend(_line(p0, p1, step))

    def arc(center, r, a0, a1):
        pts.extend(_arc(center, r, a0, a1, step))

    # --- ① 起步：S 弯抬到 y=+200 ---
    dx1 = _lane_change(pts, step, -1250.0, 0.0, ORBIT_R, r_lane)
    x_after_up1 = -1250.0 + dx1

    # --- ② 直线接障碍1 绕圈起点 (-750, +200) ---
    line((x_after_up1, ORBIT_R), (-750.0, ORBIT_R))

    # --- ③ 障碍1 (-750, 0)：顺时针绕 1 圈 ---
    arc((-750.0, 0.0), ORBIT_R, 90.0, 90.0 - 360.0)

    # --- ④ S 弯压回 y=0（起始圆弧与绕柱圆重合，等于多绕 60°） ---
    dx2 = _lane_change(pts, step, -750.0, ORBIT_R, -ORBIT_R, r_lane)

    # --- ⑤ 沿 y = 0 直线穿过障碍2 的 150 mm 门缝(x∈[-100,100]) ---
    line((-750.0 + dx2, 0.0), (750.0 - dx1, 0.0))

    # --- ⑥ S 弯抬到 y=+200，正好切到障碍3 绕圈起点 (750, +200) ---
    _lane_change(pts, step, 750.0 - dx1, 0.0, ORBIT_R, r_lane)

    # --- ⑦ 障碍3 (750, 0)：顺时针绕 2 圈 ---
    arc((750.0, 0.0), ORBIT_R, 90.0, 90.0 - 720.0)

    # --- ⑧ S 弯压回 y=0，冲终点 ---
    dx3 = _lane_change(pts, step, 750.0, ORBIT_R, -ORBIT_R, r_lane)
    line((750.0 + dx3, 0.0), (1250.0, 0.0))

    return pts


# =============================================================================
#                          前视路径跟踪（Pure Pursuit）
# =============================================================================

class PurePursuit:
    """
    把路径当作按弧长参数化的折线：
      · advance()  单调向前找最近点（小窗口搜索），两圈绕柱不会跳回第一圈；
      · curvature_ahead()  前方最大曲率，用于弯道限速；
      · target()   返回前方 lookahead 处的路径点作为瞄准点。
    """

    def __init__(self, points: List[Point]):
        self.pts = points
        self.n = len(points)
        self.s = [0.0] * self.n
        self.kappa = [0.0] * self.n          # 无符号曲率（用于限速）
        self.ks = [0.0] * self.n             # 带符号曲率（用于前馈：正=左转）
        for i in range(1, self.n):
            ds = math.hypot(points[i][0] - points[i - 1][0],
                            points[i][1] - points[i - 1][1])
            self.s[i] = self.s[i - 1] + ds
            dh = _wrap(points[i][2] - points[i - 1][2])
            if ds > 1e-6:
                self.kappa[i] = abs(dh) / ds
                self.ks[i] = dh / ds
        self.total = self.s[-1]
        self.idx = 0

    def advance(self, x: float, y: float) -> float:
        lo = max(0, self.idx - SEARCH_BACK)
        hi = min(self.n - 1, self.idx + SEARCH_FWD)
        best, best_d2 = self.idx, float('inf')
        for k in range(lo, hi + 1):
            dx = self.pts[k][0] - x
            dy = self.pts[k][1] - y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2, best = d2, k
        self.idx = best
        return math.sqrt(best_d2)

    def curvature_ahead(self, n_ahead: int = CURV_LOOKAHEAD) -> float:
        hi = min(self.n - 1, self.idx + n_ahead)
        k = 0.0
        for i in range(self.idx, hi + 1):
            if self.kappa[i] > k:
                k = self.kappa[i]
        return k

    def curvature_now(self) -> float:
        """当前点带符号曲率（正=左转），含少量提前量，用于尾角前馈。"""
        return self.ks[min(self.n - 1, self.idx + FF_LEAD)]

    def target(self, lookahead: float):
        """返回 (瞄准点, 是否到路径末端, 剩余弧长)。"""
        s_target = self.s[self.idx] + lookahead
        if s_target >= self.total:
            return self.pts[-1], True, self.total - self.s[self.idx]
        j = self.idx
        while j < self.n - 1 and self.s[j] < s_target:
            j += 1
        return self.pts[j], False, self.total - self.s[self.idx]

    @property
    def progress(self) -> float:
        return self.s[self.idx] / self.total if self.total > 0 else 1.0


# =============================================================================
#                              航向 PID
# =============================================================================

class PID:
    """角度误差（度）→ 尾关节偏角（度）。"""

    def __init__(self, kp, ki, kd, integral_max):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.integral_max = integral_max
        self.reset()

    def reset(self):
        self.err_prev = 0.0
        self.integral = 0.0

    def calculate(self, err: float, dt: float) -> float:
        self.integral = max(-self.integral_max, min(self.integral_max, self.integral + err * dt))
        d = (err - self.err_prev) / dt if dt > 1e-6 else 0.0
        self.err_prev = err
        return self.kp * err + self.ki * self.integral + self.kd * d


# =============================================================================
#                         赛道跟踪控制器
# =============================================================================

class CourseFollower:
    """纯跟踪 + 弯道限速 + PID 航向控制 + 摆尾推进，输出 FishCtrlInfo。"""

    def __init__(self, path: List[Point]):
        self.tracker = PurePursuit(path)
        self.pid = PID(YAW_KP, YAW_KI, YAW_KD, YAW_INTEGRAL_MAX)
        self.phase = 0.0
        self.frames = 0
        self.last_t = None
        self.finished = False
        self.last_err = 0.0
        self.last_force = 0.0
        self.last_wing = WING_ANGLE_LEVEL
        self.last_ff = 0.0
        self.dist_to_path = 0.0
        self.v_meas = 0.0            # 实测速度（低通），用于超速保护
        self._px = None
        self._py = None

        self.log_file = None
        self.csv_file = None
        self._open_logs()

    # ---------------- 日志 ----------------
    def _open_logs(self):
        try:
            self.log_file = open('log.txt', 'w', encoding='utf-8')
            self.log_file.write('# Fish-v1 障碍竞速 运行日志\n')
            self.log_file.write('# 路径总长 %.1f mm，采样点 %d 个\n'
                                % (self.tracker.total, self.tracker.n))
            self.log_file.flush()
        except Exception:
            self.log_file = None
        try:
            self.csv_file = open('fish_debug_log.csv', 'w', encoding='utf-8')
            self.csv_file.write('Time(s),Progress,PosX,PosY,PosZ,Yaw(deg),Tail(deg),'
                                'ThrustL,ThrustR,ErrToPath(mm),Speed(mm/s),WingAngle(deg)\n')
            self.csv_file.flush()
        except Exception:
            self.csv_file = None

    def _log(self, line: str):
        if self.log_file is not None:
            try:
                self.log_file.write(line + '\n')
                self.log_file.flush()
            except Exception:
                self.log_file = None

    def _csv(self, line: str):
        if self.csv_file is not None:
            try:
                self.csv_file.write(line + '\n')
            except Exception:
                self.csv_file = None

    def close(self):
        for f in (self.log_file, self.csv_file):
            try:
                if f is not None:
                    f.flush()
                    f.close()
            except Exception:
                pass
        self.log_file = self.csv_file = None

    # ---------------- 速度规划 ----------------
    def _speed_limit(self, x: float) -> float:
        """按前方曲率 + 过门区间给出目标速度（mm/s）。"""
        kappa = self.tracker.curvature_ahead()
        v = V_TOP
        if kappa > 1e-9:
            # 弯道同时受"侧向加速度"和"偏航角速度"两个上限约束，取小者
            v = min(v, math.sqrt(A_LAT_MAX / kappa), YAW_RATE_MAX / kappa)
        if GATE_X[0] <= x <= GATE_X[1]:
            v = min(v, V_GATE)
        return max(120.0, v)

    # ---------------- 单帧控制 ----------------
    def control(self, x: float, y: float, z: float, yaw: float, roll_deg: float,
                dt: float) -> Tuple[float, float, float, float, float]:
        """返回 (tail_angle, force_left, force_right, wing_angle, heading_error_deg)。"""
        # 0) 实测速度（低通），用于超速保护
        if self._px is not None and dt > 1e-6:
            v_inst = math.hypot(x - self._px, y - self._py) / dt
            self.v_meas += (v_inst - self.v_meas) * min(1.0, dt / SPEED_LP_TAU)
        self._px, self._py = x, y

        # 1) 跟踪进度
        self.dist_to_path = self.tracker.advance(x, y)

        # 2) 目标速度 → 前视距离
        v_des = self._speed_limit(x)
        look = max(LOOKAHEAD_MIN, min(LOOKAHEAD_MAX, v_des * LOOKAHEAD_T))
        if GATE_X[0] <= x <= GATE_X[1]:
            look = min(look, GATE_LOOKAHEAD)
        (tx, ty, _), at_end, remain = self.tracker.target(look)

        # 3) 航向误差
        err_deg = math.degrees(_wrap(math.atan2(ty - y, tx - x) - yaw))
        self.last_err = err_deg

        # 4) 尾角 = 曲率前馈 + 航向 PID 修正 + 正弦摆尾
        #    前馈按"当前速度 × 路径曲率"直接算出该转多少，PID 只管剩下的偏差，
        #    这样尾巴能立刻打到该有的角度，稳态误差小、过弯不用靠误差硬顶。
        v_ff = max(self.v_meas, 200.0)                     # mm/s（起步给下限，避免 0）
        omega_req = v_ff * self.tracker.curvature_now()    # rad/s（正 = 左转）
        tail_ff = math.degrees(omega_req) / YAW_GAIN_FF
        tail_ff = max(-FF_LIMIT, min(FF_LIMIT, tail_ff))

        corr = self.pid.calculate(err_deg, dt)
        corr = max(-CORR_LIMIT, min(CORR_LIMIT, corr))
        swing = TAIL_AMP * math.sin(self.phase)
        tail = max(-TAIL_MAX, min(TAIL_MAX, swing + tail_ff + corr))
        self.last_ff = tail_ff

        self.phase += 2.0 * math.pi * TAIL_FREQ * dt
        if self.phase > 2.0 * math.pi:
            self.phase -= 2.0 * math.pi

        # 5) 推进力：速度换算 + 大误差收油 + 超速收油 + 横滚差动 + 深度兜底，限幅 ±50
        base = v_des / MM_S_PER_FORCE
        base = min(base, F_TOP)
        base *= max(FORCE_ERR_MIN, 1.0 - abs(err_deg) / FORCE_ERR_SLOW)
        if self.v_meas > v_des * OVERSPEED_TRIP:          # 实测比目标快太多 → 收油
            base *= max(OVERSPEED_FLOOR, v_des / self.v_meas)
        if z > DEPTH_SOFT:
            base *= DEPTH_SOFT_SCALE
        elif z < DEPTH_LOW:
            base *= 1.0

        roll_correct = roll_deg * ROLL_GAIN
        fl = max(-F_MAX, min(F_MAX, base - roll_correct))
        fr = max(-F_MAX, min(F_MAX, base + roll_correct))
        self.last_force = base

        # 6) 胸鳍角度：-90° = 完全朝前（z 不变、pitch 不变），再用深度误差微调：
        #    偏高 → 角度更负（朝前偏下，下潜）；偏低 → 角度回抬（朝前偏上，上浮）
        z_err = DEPTH_TARGET - z
        wing = WING_ANGLE_LEVEL + max(-DEPTH_ANGLE_LIMIT,
                                      min(DEPTH_ANGLE_LIMIT, DEPTH_ANGLE_KP * z_err))
        wing = max(WING_ANGLE_MIN, min(WING_ANGLE_MAX, wing))
        self.last_wing = wing

        # 7) 冲过终点线后停推
        if at_end and x >= FINISH_STOP_X:
            self.finished = True
        if self.finished:
            return 0.0, 0.0, 0.0, WING_ANGLE_LEVEL, err_deg

        return tail, fl, fr, wing, err_deg


# =============================================================================
#                              主程序
# =============================================================================

_follower: Optional[CourseFollower] = None
_publisher = None


def lcb(fish_info):
    """平台环境数据回调：每帧计算一次控制量并发布。"""
    try:
        now = time.monotonic()
        if _follower.last_t is None:
            dt = 1.0 / 60.0
        else:
            dt = max(0.005, min(0.10, now - _follower.last_t))
        _follower.last_t = now
        _follower.frames += 1

        x = float(fish_info.pos.x)
        y = float(fish_info.pos.y)
        z = float(fish_info.pos.z)
        yaw = math.atan2(float(fish_info.forward.y), float(fish_info.forward.x))
        roll_deg = float(fish_info.rot.x)          # 平台旋转量单位为"度"

        tail, fl, fr, wing, err = _follower.control(x, y, z, yaw, roll_deg, dt)

        ctrl = mycue.FishCtrlInfo()
        ctrl.tail_target_angel = tail
        ctrl.wing_force_left = fl
        ctrl.wing_force_right = fr
        # 胸鳍角度：-90° 水平推进（原框架恒为 0 = 推力朝上，才会一直上浮、抬头）
        ctrl.wing_target_angel_left = wing
        ctrl.wing_target_angel_right = wing
        _publisher.publish(ctrl)

        # ---- 调试输出 ----
        if _follower.frames % LOG_EVERY == 0:
            line = ('%.2f,%.4f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f'
                    % (now, _follower.tracker.progress, x, y, z,
                       math.degrees(yaw), tail, fl, fr, _follower.dist_to_path,
                       _follower.v_meas, wing))
            _follower._log(line)
            if VERBOSE:
                print('t=%5.2fs 进度=%5.1f%%  pos=(%7.1f,%7.1f,%6.1f)  yaw=%6.1f°  '
                      '尾=%6.1f°  推力=(%4.1f,%4.1f)  鳍角=%6.1f°  v=%4.0fmm/s  '
                      '偏离=%5.1fmm  误差=%6.1f°'
                      % (now, _follower.tracker.progress * 100.0, x, y, z,
                         math.degrees(yaw), tail, fl, fr, wing, _follower.v_meas,
                         _follower.dist_to_path, err))
        if _follower.frames % CSV_EVERY == 0:
            _follower._csv('%.2f,%.4f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f'
                           % (now, _follower.tracker.progress, x, y, z,
                              math.degrees(yaw), tail, fl, fr, _follower.dist_to_path,
                              _follower.v_meas, wing))
    except Exception as exc:      # 单帧异常不能让 DDS 回调线程挂掉
        try:
            print('[lcb error] %r' % (exc,))
        except Exception:
            pass


def main():
    global _follower, _publisher
    if mycue is None:
        raise RuntimeError('未找到 cue 模块：请在仿真平台自带的 Python 环境中运行本脚本')

    path = build_course()
    _follower = CourseFollower(path)
    print('赛道采样点 %d 个，路径总长 %.1f mm' % (len(path), _follower.tracker.total))

    mycue.init(TEAM_NAME)
    _publisher = mycue.publisher(mycue.FishCtrlInfo)
    sub = mycue.subscriber(mycue.FishInfo, lcb)      # noqa: F841  (保持引用，勿被回收)

    print('等待平台环境数据 ... (Ctrl+C 退出)')
    try:
        while True:
            time.sleep(1.0 / 100.0)
    except KeyboardInterrupt:
        print('退出')
    finally:
        _follower.close()


if __name__ == '__main__':
    main()

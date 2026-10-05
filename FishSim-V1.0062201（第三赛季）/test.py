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
  5. 循迹 = 纯跟踪瞄准 − Stanley 横向修正项（K_CROSS=2）：
     纯跟踪跟得顺、允许少量切弯（路程短），横向修正项把切弯量压住，高速也不会一路切上柱子。
     弯道限速全部放开，全程基本满推；跟不住时由两道保护自动减速：
       · 瞄准误差收油（偏出目标方向越多越收）
       · 跑宽收油（离路径越远越收）
  6. 胸鳍角度（wing_target_angel_left/right）用起来：
     -90° = 推力完全朝前（z 与 pitch 都不变），再用深度误差在 ±25° 内微调，
     把老版本"鳍角恒为 0 → 推力朝上 → 一直上浮抬头"的问题彻底修掉。
  7. 不需要状态机：路径本身已经按"绕1圈→穿门→绕2圈→终点"排好，
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
ORBIT_R = 220.0                  # 绕单柱圆半径（柱半宽 100 + 鱼等效半宽 45 + 余量）
PHI_EXIT1 = 55.0                 # 绕障碍1 的出圈极角(度)：出口航向 = 该角 - 90
PHI_IN3 = 128.7                  # 绕障碍3 的入圈极角(度)：入口航向 = 该角 - 90
RHO1 = 500.0                     # 出圈后拉平到 y=0 的左转弧半径（大半径=对转向能力要求低）
SAMPLE_STEP = 10.0               # 路径采样间距 mm

# ---- 速度规划（真鱼实测：尾舵打满约 76°/s，v=490 时最小转弯半径约 370mm） ----
V_TOP = 520.0                    # 直道目标速度 mm/s
A_LAT_MAX = 1600.0               # 允许侧向加速度 mm/s^2
YAW_RATE_MAX = 1.75              # 允许偏航角速度 rad/s ≈100°/s（弯道限速 v=w·R，主约束）
                                 # 绕柱段因此限到 1.75×220 ≈ 385 mm/s；放到 1.95 会冲出绕柱圈
V_GATE = 430.0                   # 过门速度上限 mm/s
GATE_X = (-380.0, 300.0)         # 过门限速区间（x）
MM_S_PER_FORCE = 14.0            # 推力→速度换算：每 1 单位推力约 14 mm/s
F_TOP = 48.0                     # 基础推力（限值 50）
F_MAX = 50.0                     # 裁判规定的推进力上限
FORCE_ERR_SLOW = 95.0            # 航向误差收油（度）：绕柱段稳态就有 ~20° 滞后误差，
FORCE_ERR_MIN = 0.78             #   刹车太狠会把鱼自己按住（实测绕柱速度被压到 300 而非 365）
DEV_SOFT = 60.0                  # 偏离路径超过这个距离开始收油（mm）
DEV_HARD = 200.0                 # 偏离到这个距离收到下限
DEV_MIN = 0.50                   # 偏离收油下限系数

# ---- 摆尾（摆频与动力成正比：这是除胸鳍推力外的主要提速手段） --------------
TAIL_AMP = 20.0                  # 摆尾幅度（度）：绕柱段宜小不宜大（幅值大=速度快=转不过来）
# 摆频：实机观察"摆太频繁反而大幅掉速"（每次摆动的横向摆动都在吃阻力），
# 所以取低频：既保留一点摆尾推进，又把摆动次数压到最低。
# 原来 2.4Hz（16s 要摆 38 次）→ 现在 1.2Hz（16s 只摆 19 次）。
# 仍需摆动推进时可回调（1.2~1.8 之间），调到鱼明显"游不动"就是过低了。
TAIL_FREQ = 1.20                 # 摆尾频率 Hz
TAIL_MAX = 80.0                  # 裁判规定的尾关节角度上限
DC_LIM = 58.0                    # 尾角直流偏置上限：58 + 幅值 22 = 80，正好用满不越限

# ---- 蟹角(crab angle)补偿 ---------------------------------------------------
# 实测：鱼的机头朝向 yaw 与速度方向 psi_v 之间固定差 beta ≈ -11.5°（转圈时）。
# 不补偿的后果：稳态绕柱半径 = 目标半径 + ld·tan(beta)，实际会系统性内切 ~30mm，
# 在 R=220 时等效半径掉到 ~190，逼近"柱半对角 141.4 + 鱼等效半宽 45 = 186.4"的安全线。
# 只在绕柱大曲率段补偿（对齐弧不加，否则落点整体偏移）。
BETA_ARC = -0.20                 # rad，≈ -11.5°
BETA_KAPPA_MIN = 1.0 / 320.0     # 曲率大于此值才认为在绕柱

# ---- 卡死脱困 ---------------------------------------------------------------
STUCK_V = 70.0                   # 实测速度低于此值视为卡住 mm/s
STUCK_T = 0.7                    # 持续这么久就触发脱困 s
ESCAPE_T = 0.6                   # 脱困持续时长 s
ESCAPE_AMP = 30.0                # 脱困时的摆尾幅值
PILLAR_CENTERS = [(-750.0, 0.0), (750.0, 0.0), (0.0, 175.0), (0.0, -175.0)]

# ---- 航向 PID + 曲率前馈 ----------------------------------------------------
YAW_KP = 2.20                    # 沿用原工程实测可用的参数
YAW_KI = 0.01
YAW_KD = 0.95
YAW_INTEGRAL_MAX = 50.0
YAW_GAIN_FF = 2.8                # 偏航角速度增益（deg/s per 1°尾角），用于曲率前馈
FF_LIMIT = 50.0                  # 前馈+修正合成的直流偏置上限（度）
FF_LEAD = 3                      # 前馈提前量（点数，约 30 mm）

# ---- 跟踪 -------------------------------------------------------------------
LOOKAHEAD_T = 0.24               # 前视时间常数（仅用于取瞄准点/速度规划参考）
LOOKAHEAD_MIN = 90.0
LOOKAHEAD_MAX = 170.0
GATE_LOOKAHEAD = 85.0            # 过门区间收紧前视，保证走直线
K_CROSS = 2.0                    # Stanley 横向修正增益（1/s）：0=纯跟踪，2=贴线且不牺牲速度
CT_MIN_V = 250.0                 # Stanley 分母速度下限 mm/s（防止低速时增益爆炸）
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


def _dist_to_rect(px, py, cx, cy, half):
    """点到方柱表面的距离（柱内为 0）。"""
    dx = max(cx - half - px, 0.0, px - (cx + half))
    dy = max(cy - half - py, 0.0, py - (cy + half))
    return math.hypot(dx, dy)


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


def _tangent_phi(point, center, R):
    """从 point 向"以 center 为圆心、半径 R"的圆作切线，返回两个切点的极角（弧度）。"""
    dx, dy = point[0] - center[0], point[1] - center[1]
    d = math.hypot(dx, dy)
    beta = math.acos(max(-1.0, min(1.0, R / d)))
    a = math.atan2(dy, dx)
    return a - beta, a + beta


def build_course(step: float = SAMPLE_STEP) -> List[Point]:
    """
    生成整条赛道（处处相切连续）：

      起点 ─切线─ 绕障碍1 一圈多(顺时针) ─直线下切─ 大半径左转弧落到 y=0
           ─直线穿过障碍2 门缝─ 大半径左转弧切到障碍3 入口
           ─绕障碍3 两圈多(顺时针) ─切线─ 终点

    与"绕一圈再 S 形变道"的老写法相比，这里靠**绕柱的出/入极角**天然完成横向移位：
      出圈时航向已经是斜向下（-35°），只用一段半径 500mm 的缓弧就能拉平到 y=0；
      进门后再用一段半径 ~780mm 的缓弧切进障碍3 的入口点。
    对齐只花 ~74° 转向（老写法 S 弯要 480°），而且半径大、对转向能力要求低——
    实测这条鱼尾舵打满也只有 ~76°/s 偏航率（v=490 时最小转弯半径约 370mm），
    老写法半径 230 的 S 弯它根本转不过来。
    """
    pts: List[Point] = [(START[0], START[1], 0.0)]
    R = ORBIT_R
    C1 = (-750.0, 0.0)
    C3 = (750.0, 0.0)

    # ---- ① 起点沿切线进绕柱1 ----
    pa, pb = _tangent_phi(START, C1, R)
    phi_in1 = pa if math.sin(pa) > math.sin(pb) else pb
    T1_in = (C1[0] + R * math.cos(phi_in1), C1[1] + R * math.sin(phi_in1))
    pts.extend(_line(START, T1_in, step))

    # ---- ② 障碍1：顺时针绕 1 圈 + 多转到出圈极角 ----
    phi_ex1 = math.radians(PHI_EXIT1)
    T1_out = (C1[0] + R * math.cos(phi_ex1), C1[1] + R * math.sin(phi_ex1))
    pts.extend(_arc(C1, R, math.degrees(phi_in1), math.degrees(phi_ex1) - 360.0, step))

    # ---- ③ 沿出圈航向直行 → 大半径左转弧拉平到 y=0 ----
    th1 = phi_ex1 - math.pi / 2.0                       # 顺时针出圈时的航向
    rho1 = RHO1
    t1 = (rho1 * (1.0 - math.cos(th1)) - T1_out[1]) / math.sin(th1)
    PS1 = (T1_out[0] + t1 * math.cos(th1), T1_out[1] + t1 * math.sin(th1))
    xE = PS1[0] - rho1 * math.sin(th1)
    pts.extend(_line(T1_out, PS1, step))
    a_b1 = math.degrees(math.atan2(PS1[1] - rho1, PS1[0] - xE))
    pts.extend(_arc((xE, rho1), rho1, a_b1, -90.0, step))     # 结束于 (xE, 0)，航向 0

    # ---- ④ 障碍3 入口点与进门后的对齐弧 ----
    phi_in3 = math.radians(PHI_IN3)
    E2 = (C3[0] + R * math.cos(phi_in3), C3[1] + R * math.sin(phi_in3))
    th2 = phi_in3 - math.pi / 2.0                       # 顺时针入圈时的航向
    rho2 = E2[1] / (1.0 - math.cos(th2))
    xS2 = E2[0] - rho2 * math.sin(th2)

    # ---- ⑤ 沿 y=0 直线穿过障碍2 的 150 mm 门缝 ----
    pts.extend(_line((xE, 0.0), (xS2, 0.0), step))

    # ---- ⑥ 大半径左转弧切到障碍3 入口点 E2 ----
    pts.extend(_arc((xS2, rho2), rho2, -90.0, -90.0 + math.degrees(th2), step))

    # ---- ⑦ 障碍3：顺时针绕 2 圈 + 多转到出圈极角 ----
    pa, pb = _tangent_phi(FINISH, C3, R)
    phi_out3 = pa if math.sin(pa) > math.sin(pb) else pb
    T3_out = (C3[0] + R * math.cos(phi_out3), C3[1] + R * math.sin(phi_out3))
    pts.extend(_arc(C3, R, math.degrees(phi_in3), math.degrees(phi_out3) - 720.0, step))

    # ---- ⑧ 沿切线冲到终点并留 170mm 余量（裁判绕完第二圈即计时结束） ----
    ux, uy = FINISH[0] - T3_out[0], FINISH[1] - T3_out[1]
    un = math.hypot(ux, uy)
    EXT = (FINISH[0] + ux / un * 170.0, FINISH[1] + uy / un * 170.0)
    pts.extend(_line(T3_out, EXT, step))

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

    def signed_cross_track(self, x: float, y: float):
        """返回 (横向偏差 e>0 表示鱼在路径左侧, 路径切线方向 ph)。"""
        px, py, ph = self.pts[self.idx]
        nx, ny = -math.sin(ph), math.cos(ph)          # 路径左法线
        return (x - px) * nx + (y - py) * ny, ph

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
        self.last_dc = 0.0
        self.last_ct = 0.0
        self.dist_to_path = 0.0
        self.v_meas = 0.0            # 实测速度（低通），用于超速保护
        self._px = None
        self._py = None
        self.t_acc = 0.0             # 内部计时（脱困用）
        self.stuck_t = 0.0
        self.esc_until = -1.0
        self.esc_dir = 0.0
        self.esc_flip = 1.0

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

        # 3) 航向误差 = 纯跟踪瞄准误差 − Stanley 横向修正项 + 蟹角补偿
        #    纯跟踪跟得顺、允许少量切弯（路程更短）；横向修正项负责把切弯量压住，
        #    避免高速时一路切到柱子上。K_CROSS=0 即退化为纯跟踪。
        aim_err_deg = math.degrees(_wrap(math.atan2(ty - y, tx - x) - yaw))
        e_ct, ph = self.tracker.signed_cross_track(x, y)
        v_eff = max(self.v_meas, CT_MIN_V)
        ct_term = math.degrees(math.atan2(K_CROSS * e_ct, v_eff))
        # 绕柱大曲率段补蟹角：让机头朝路径方向再偏 beta，速度方向才真正贴住圆
        k_now = self.tracker.curvature_now()
        crab = math.degrees(BETA_ARC) if abs(k_now) > BETA_KAPPA_MIN else 0.0
        err_deg = aim_err_deg - ct_term + crab
        self.last_err = err_deg
        self.last_ct = e_ct
        head_err_deg = aim_err_deg          # 收油只看"偏离目标方向"的量

        # 3b) 卡死检测与脱困：撞柱后如果速度掉到几十，光靠控制器会一直顶在柱子上
        self.t_acc += dt
        if not self.finished and self.v_meas < STUCK_V:
            self.stuck_t += dt
        else:
            self.stuck_t = 0.0
        if self.stuck_t > STUCK_T and self.t_acc > self.esc_until:
            near, nd = None, 1e9
            for (cx, cy) in PILLAR_CENTERS:
                dd = _dist_to_rect(x, y, cx, cy, 100.0)
                if dd < nd:
                    nd, near = dd, (cx, cy)
            if near is not None:
                base = math.atan2(y - near[1], x - near[0])
                self.esc_dir = _wrap(base + self.esc_flip * 1.2)
                self.esc_flip = -self.esc_flip
                self.esc_until = self.t_acc + ESCAPE_T
                self.stuck_t = 0.0

        # 4) 尾角 = 曲率前馈 + 航向 PID 修正，再叠加正弦摆尾
        #    （脱困期间改为朝"背离最近柱子"的方向满舵冲出去）
        if self.t_acc < self.esc_until:
            e_esc = _wrap(self.esc_dir - yaw)
            dc = max(-DC_LIM, min(DC_LIM, math.degrees(YAW_KP * e_esc) / 1.9))
            amp_use = ESCAPE_AMP
            tail_ff = 0.0
        else:
            v_ff = max(self.v_meas, 200.0)                 # mm/s（起步给下限，避免 0）
            omega_req = v_ff * self.tracker.curvature_now()  # rad/s（正 = 左转）
            tail_ff = math.degrees(omega_req) / YAW_GAIN_FF
            tail_ff = max(-FF_LIMIT, min(FF_LIMIT, tail_ff))
            corr = self.pid.calculate(err_deg, dt)
            # 直流偏置负责转向，正弦摆尾负责推进；两者之和不超过 ±80
            dc = max(-DC_LIM, min(DC_LIM, tail_ff + corr))
            amp_use = TAIL_AMP
        swing = amp_use * math.sin(self.phase)
        tail = max(-TAIL_MAX, min(TAIL_MAX, dc + swing))
        self.last_dc = dc
        self.last_ff = tail_ff

        self.phase += 2.0 * math.pi * TAIL_FREQ * dt
        if self.phase > 2.0 * math.pi:
            self.phase -= 2.0 * math.pi

        # 5) 推进力：速度换算 + 大误差收油 + 超速收油 + 横滚差动 + 深度兜底，限幅 ±50
        base = v_des / MM_S_PER_FORCE
        base = min(base, F_TOP)
        base *= max(FORCE_ERR_MIN, 1.0 - abs(head_err_deg) / FORCE_ERR_SLOW)
        # 跑宽了自动刹车：既允许直道全力跑，又能在切弯外抛前把速度收回来
        base *= max(DEV_MIN, 1.0 - max(0.0, self.dist_to_path - DEV_SOFT) / (DEV_HARD - DEV_SOFT))
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

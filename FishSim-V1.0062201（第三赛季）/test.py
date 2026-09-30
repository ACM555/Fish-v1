import math
from typing import Tuple, List, Optional
import time
import cue as mycue


# ========================== 角度处理工具函数（path_generate.py） ==========================

def theta(T):
    """
    将任意角度标准化到 [0, 2π) 区间。
    :param T: 原始角度（弧度）
    :return: 标准化后的角度
    """
    return T % (2 * math.pi)


def up_theta(T, B):
    """
    确保角度 T 不小于角度 B，返回一个比 B 大且与 T 相差 (T-B) 标准化值的角度。
    用于处理圆弧段角度缠绕问题。
    :param T: 目标角度
    :param B: 基准角度
    :return: 满足 ≥ B 且模 2π 后等于 T 的角度
    """
    return theta(B) + theta(T - B)


# ========================== 路径点类（path_generate.py） ==========================

class Points:
    """
    表示 Dubins 路径中的一个节点（圆心或路径转折点）。
    属性：
        x, y    : 圆心坐标（若 r>0）或路径点坐标（若 r=0）
        r       : 圆弧半径，0 表示直线段或路径点
        circles : 圆弧段额外绕行的圈数（可为负表示反向绕圈）
        ARR     : 到达该段圆弧时的角度
        DEP     : 离开该段圆弧时的角度
    """

    def __init__(self, x, y, r, circles):
        self.x = x
        self.y = y
        self.r = r
        self.circles = circles
        self.ARR = None
        self.DEP = None


# ========================== Dubins 路径计算类（path_generate.py） ==========================

class Dubins:
    """
    根据给定的节点列表和路径类型字符串，计算 Dubins 路径的到达/离开角度，
    并可采样路径上的离散点用于仿真或可视化。
    """

    def __init__(self, points_list, path):
        """
        :param points_list: 列表，每个元素为 (x, y, r, circles)
        :param path: 字符串，每个字符表示对应节点间路径类型
                     'R' 表示顺时针圆弧，'L' 表示逆时针圆弧
        """
        # 创建 Points 对象列表
        self.points = [Points(point[0], point[1], point[2], point[3]) for point in points_list]
        self.path = path
        self.RAT = True  # 路径有效性标志，True 表示可计算有效路径

        # 首节点只有离开方向，末节点只有到达方向，这里设为零
        self.points[0].ARR = 0
        self.points[-1].DEP = 0

        # 计算所有节点的到达和离开角度
        self.set_arr_dep()
        # 初始化采样点列表
        self.sampled_points = []

    # ------------------------- 核心几何计算 -------------------------
    def calculate_arr_dep(self, i):
        """
        计算第 i 个节点与第 i+1 个节点之间的路径所确定的离开角和到达角。
        根据路径类型（同向或异向）使用不同几何公式。
        :param i: 节点索引（0 ≤ i < len(points)-1）
        :return: (C1, C2) 分别对应节点 i 的离开角和节点 i+1 的到达角（如果路径有效）
                 若路径无效，则返回 (None, None) 并置 self.RAT = False
        """
        C_1, C_2 = None, None
        if self.RAT:
            # 两圆心之间的距离
            L_O = math.sqrt((self.points[i + 1].x - self.points[i].x) ** 2 +
                            (self.points[i + 1].y - self.points[i].y) ** 2)
            # 两圆心连线的方向角
            D_O = theta(math.atan2(self.points[i + 1].y - self.points[i].y,
                                   self.points[i + 1].x - self.points[i].x))

            # 情况1：相邻两段圆弧转向相同（如 R→R 或 L→L）
            if self.path[i] == self.path[i + 1]:
                # 检查几何可行性：两圆不能完全内含（小圆+距离必须 ≥ 大圆半径）
                if L_O + min(self.points[i + 1].r, self.points[i].r) < max(self.points[i + 1].r, self.points[i].r):
                    self.RAT = False
                else:
                    # 计算圆心连线与内外公切线的夹角
                    D_like = math.asin((self.points[i + 1].r - self.points[i].r) / L_O)
                    # 离开/到达角公式：π/2 + 圆心连线角 ± 偏角（取决于转向）
                    C_1 = C_2 = math.pi / 2 + D_O + (D_like if self.path[i] == "R" else math.pi - D_like)

            # 情况2：相邻两段圆弧转向相反（如 R→L 或 L→R）
            elif self.path[i] != self.path[i + 1]:
                # 检查几何可行性：两圆不能相交（距离必须 ≥ 半径和）
                if L_O < self.points[i + 1].r + self.points[i].r:
                    self.RAT = False
                else:
                    # 计算圆心连线与内外公切线的夹角
                    D_unlike = math.asin((self.points[i + 1].r + self.points[i].r) / L_O)
                    # 离开角公式：π/2 + 圆心连线角 ± 偏角（符号与转向有关）
                    C_1 = math.pi / 2 + D_O + (-D_unlike if self.path[i] == "R" else -math.pi + D_unlike)
                    # 到达角公式：3π/2 + 圆心连线角 ± 偏角（符号与转向有关）
                    C_2 = 3 * math.pi / 2 + D_O + (-D_unlike if self.path[i] == "R" else -math.pi + D_unlike)
        return C_1, C_2

    def tidy_arr_dep(self, i):
        """
        整理第 i 个节点的到达角和离开角，确保它们满足圆弧段的方向要求。
        对于顺时针（R）圆弧，离开角应大于到达角（增加方向）；逆时针（L）则相反。
        利用 up_theta 函数保证角度大小关系正确，并处理多圈缠绕。
        :param i: 节点索引
        :return: (arr, dep) 整理后的到达角和离开角
        """
        if self.path[i] == "R":
            # 顺时针：dep 应大于 arr，且 dep - arr 的标准化值等于原始差
            return up_theta(theta(self.points[i].ARR), theta(self.points[i].DEP)), theta(self.points[i].DEP)
        else:
            # 逆时针：arr 应大于 dep（即从 arr 到 dep 是减小方向），但函数实现为 arr 较小，dep 较大
            # 这里实际返回 (arr, up_theta(dep, arr))，使得 arr ≤ dep，但在后续采样时会根据圈数处理方向
            return theta(self.points[i].ARR), up_theta(theta(self.points[i].DEP), theta(self.points[i].ARR))

    def set_arr_dep(self):
        """
        依次计算所有相邻节点间的离开/到达角，并最终整理每个节点的角度对。
        如果某段几何不可行，则 RAT 置 False 并终止。
        """
        # 第一步：根据相邻节点计算离开/到达角
        for i in range(len(self.points) - 1):
            self.points[i].DEP, self.points[i + 1].ARR = self.calculate_arr_dep(i)
            if not self.RAT:
                break
        # 第二步：如果路径有效，整理每个节点的角度对（确保大小关系正确）
        if self.RAT:
            for i in range(len(self.points)):
                self.points[i].ARR, self.points[i].DEP = self.tidy_arr_dep(i)

    # ------------------------- 路径采样 -------------------------
    def sample_path_points(self, step=10):
        """
        沿 Dubins 路径均匀采样点，每个采样点包含坐标、方向等信息。
        直线段按步长 step 采样，圆弧段按弧长步长 step 采样（考虑圈数）。
        :param step: 采样步长（距离单位）
        :return: 采样点列表，每个元素为 (x, y, 340, cos(direction), sin(direction), 0)
                 其中 340 为固定值（可能表示颜色或类型），方向向量用于表示朝向。
        """
        if not self.RAT:
            print("Path doesn't exist, cannot sample points.")
            return []

        self.sampled_points = []  # 清空之前的采样

        # 遍历所有节点（每个节点对应一段圆弧，最后一段圆弧后可能跟直线段）
        for i in range(len(self.points)):
            # ----- 圆弧段采样 -----
            if self.points[i].r > 0:
                # 基本角度变化（不考虑圈数）
                angle_diff = self.points[i].DEP - self.points[i].ARR
                # 总角度变化 = 基本差 + 2π * 圈数（符号由 angle_diff 决定，使方向一致）
                total_angle_diff = angle_diff + 2 * math.pi * self.points[i].circles * (1 if angle_diff >= 0 else -1)

                # 圆弧长度
                arc_length = abs(total_angle_diff) * self.points[i].r

                # 根据步长计算采样点数（至少1个点）
                num_samples = int(arc_length / step) + 1
                for j in range(num_samples):
                    t = j / max(1, num_samples - 1)  # 归一化参数 [0,1]
                    current_angle = self.points[i].ARR + t * total_angle_diff

                    # 计算圆弧上的点坐标
                    x = self.points[i].x + self.points[i].r * math.cos(current_angle)
                    y = self.points[i].y + self.points[i].r * math.sin(current_angle)

                    # 圆弧切线方向：顺时针（R）时切线 = 当前角度 - π/2，逆时针（L）时切线 = 当前角度 + π/2
                    if self.path[i] == 'R':
                        direction = current_angle - math.pi / 2
                    else:  # 'L'
                        direction = current_angle + math.pi / 2
                    direction = direction % (2 * math.pi)

                    # 记录采样点（x, y, 固定值340, 方向余弦, 方向正弦, 0）
                    self.sampled_points.append((x, y, 340, math.cos(direction), math.sin(direction), 0))

            # ----- 直线段采样（连接当前节点圆弧终点与下一节点圆弧起点）-----
            if i < len(self.points) - 1:
                # 当前节点圆弧终点（离开点）
                start_x = self.points[i].x + self.points[i].r * math.cos(self.points[i].DEP)
                start_y = self.points[i].y + self.points[i].r * math.sin(self.points[i].DEP)

                # 下一节点圆弧起点（到达点）
                end_x = self.points[i + 1].x + self.points[i + 1].r * math.cos(self.points[i + 1].ARR)
                end_y = self.points[i + 1].y + self.points[i + 1].r * math.sin(self.points[i + 1].ARR)

                # 直线段长度及方向
                line_length = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
                line_direction = math.atan2(end_y - start_y, end_x - start_x)

                # 按步长采样
                num_samples = int(line_length / step) + 1
                for j in range(num_samples):
                    t = j / max(1, num_samples - 1)
                    x = start_x + t * (end_x - start_x)
                    y = start_y + t * (end_y - start_y)
                    self.sampled_points.append((x, y, 340, math.cos(line_direction), math.sin(line_direction), 0))

        return self.sampled_points


# ========================== 路径生成示例（path_generate.py） ==========================

def generate_path():
    """
    定义一组节点和路径类型，创建 Dubins 对象并返回采样点。
    节点列表格式：每个元素为 (x, y, r, circles)
        - x, y : 圆心坐标（若 r>0）或路径点坐标（若 r=0）
        - r    : 圆弧半径
        - circles : 圆弧额外圈数（0 表示无绕圈）
    路径字符串：每个字符对应相邻节点间的圆弧转向，长度应比节点数少1。
    """
    points_list = [(-1250, 0, 0, 0),
                   (-1250, 200, 180, 0),
                   (-750, 50, 174, 0),
                   (-750, -50, 174, 0),
                   (-750, 50, 174, 0),
                   (-750, -50, 174, 0),
                   (-750, 50, 176, 0),
                   (50, 0, 175, 0),
                   (-50, 0, 175, 0),
                   (50,0, 175, 0),
                   (750, 100, 140, 0),
                   (1250, 0, 0, 0)]
    path = 'LLRRRRRRRRLR'

    dubin_path = Dubins(points_list, path)
    sampled = dubin_path.sample_path_points(step=10)
    return sampled


# ========================== PID控制器（find_point.py） ==========================
class PIDControllerFindPoint:
    """通用PID控制器，用于平滑航向控制"""

    def __init__(self, kp: float = 2.0, ki: float = 0.0, kd: float = 0.5, max_integral: float = 50.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_integral = max_integral

        self.error_prev = 0.0
        self.integral = 0.0
        self.output = 0.0

    def calculate(self, error: float, dt: float = 0.05) -> float:
        p = self.kp * error

        self.integral += error * dt
        self.integral = max(-self.max_integral, min(self.max_integral, self.integral))
        i = self.ki * self.integral

        d = self.kd * (error - self.error_prev) / dt if dt > 0 else 0.0

        self.output = p + i + d
        self.error_prev = error
        return self.output

    def reset(self):
        self.error_prev = 0.0
        self.integral = 0.0
        self.output = 0.0


# ========================== 路径控制器（find_point.py 尾鳍/推力/航向 完全不变） ==========================
class PathControllerFindPoint:
    """
    路径控制器 - 根据当前位置和目标点计算控制参数
    负责计算鱼尾角度和滚转角控制
    """

    def __init__(self,
                 forward_force: float = 40.0,
                 max_wing_force: float = 60.0,
                 tail_frequency: float = 1.8,
                 tail_amplitude: float = 18.0,
                 max_tail_angle: float = 70.0,
                 yaw_kp: float = 5.5,
                 yaw_ki: float = 0.4,
                 yaw_kd: float = 1,
                 roll_gain: float = 2.5):
        # 推力控制
        self.forward_force = forward_force
        self.max_wing_force = max_wing_force

        # 尾鳍摆动
        self.tail_frequency = tail_frequency
        self.tail_amplitude = tail_amplitude
        self.max_tail_angle = max_tail_angle

        # 滚转
        self.roll_gain = roll_gain

        # 相位
        self.swim_phase = 0.0

        # PID航向控制
        self.yaw_pid = PIDControllerFindPoint(kp=yaw_kp, ki=yaw_ki, kd=yaw_kd)
        self.prev_position: Tuple[float, float] = (0.0, 0.0)

    def _constrain(self, value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(value, max_val))

    def calculate_control(self,
                          current: Tuple[float, float],
                          current_yaw: float,
                          target_direction: float,
                          roll_angle: float,
                          dt: float = 0.05) -> Tuple[float, float, float]:
        # ===================== 角度标准化（全局统一） =====================
        def normalize_angle_rad(angle):
            return math.atan2(math.sin(angle), math.cos(angle))

        current_yaw = normalize_angle_rad(current_yaw)
        target_direction = normalize_angle_rad(target_direction)

        # 航向误差
        yaw_error = target_direction - current_yaw
        yaw_error = normalize_angle_rad(yaw_error)
        yaw_error_deg = math.degrees(yaw_error)

        # PID转向
        yaw_correction = self.yaw_pid.calculate(yaw_error_deg, dt)
        yaw_correction = self._constrain(yaw_correction, -self.max_tail_angle * 0.8, self.max_tail_angle * 0.8)

        # 尾鳍摆动（原逻辑完全不变）
        base_swing = self.tail_amplitude * math.sin(self.swim_phase)
        tail_angle = base_swing + yaw_correction
        tail_angle = self._constrain(tail_angle, -self.max_tail_angle, self.max_tail_angle)

        # 胸鳍推力
        roll_correct = roll_angle * self.roll_gain
        wing_left = self.forward_force - roll_correct
        wing_right = self.forward_force + roll_correct

        wing_left = self._constrain(wing_left, -self.max_wing_force, self.max_wing_force)
        wing_right = self._constrain(wing_right, -self.max_wing_force, self.max_wing_force)

        # 更新相位
        self.swim_phase += self.tail_frequency * dt * math.pi * 2
        if self.swim_phase > math.pi * 2:
            self.swim_phase -= math.pi * 2

        self.prev_position = current
        return tail_angle, wing_left, wing_right

# ========================== 极速优化 PathPointFinder ==========================
class PathPointFinderFindPoint:
    def __init__(self,
                 path_points: List[Tuple] = None,
                 lookahead_distance: float = 180.0,      # 高速巡航视野（合规）
                 lookahead_points: int = 120):            # 更长视野 = 更快过弯

        self.unreached_path_points: List[Tuple[float, float, float]] = self._convert_path_points(path_points)
        self.lookahead_distance = lookahead_distance
        self.lookahead_points = lookahead_points

    def _convert_path_points(self, raw_points: List[Tuple]) -> List[Tuple[float, float, float]]:
        if not raw_points:
            return []

        converted = []
        for point in raw_points:
            try:
                x, y, _, cos_dir, sin_dir, _ = point
                direction = math.atan2(sin_dir, cos_dir)
                direction = math.atan2(math.sin(direction), math.cos(direction))
                converted.append((float(x), float(y), direction))
            except (ValueError, TypeError):
                continue
        return converted

    def _get_distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        return math.hypot(x2 - x1, y2 - y1)

    def update_unreached_points(self, current_x: float, current_y: float) -> int:
        if not self.unreached_path_points:
            return 0

        max_search = min(self.lookahead_points, len(self.unreached_path_points))
        nearest_idx = 0
        min_dist = float('inf')

        for i in range(max_search):
            x, y, _ = self.unreached_path_points[i]
            dist = self._get_distance(current_x, current_y, x, y)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        remove_count = nearest_idx
        del self.unreached_path_points[:nearest_idx]
        return remove_count

    def find_target_point(self, current_x: float, current_y: float) -> Tuple[
        Optional[float], Optional[float], Optional[float]]:
        if not self.unreached_path_points:
            return None, None, None

        self.update_unreached_points(current_x, current_y)

        best_idx = -1
        max_dist_in_lookahead = -1.0

        for i, (x, y, _) in enumerate(self.unreached_path_points):
            dist = self._get_distance(current_x, current_y, x, y)

            # ===================== 【规则友好】智能视野 =====================
            if abs(x) < 200:
                # 障碍区域：贴圈高速绕圈（不违规、不扩大圈）
                adaptive_lookahead = 120
            else:
                # 直线/终点：全速巡航
                adaptive_lookahead = self.lookahead_distance

            if dist > adaptive_lookahead:
                break

            if dist > max_dist_in_lookahead:
                max_dist_in_lookahead = dist
                best_idx = i

        if best_idx >= 0:
            return self.unreached_path_points[best_idx]

        return self.unreached_path_points[0]


# ========================== PID控制器（control.py） ==========================
class PIDControllerControl:
    """通用PID控制器，用于平滑航向控制"""

    def __init__(self, kp: float = 2.0, ki: float = 0.0, kd: float = 0.5, max_integral: float = 50.0):
        self.kp = kp  # 比例系数
        self.ki = ki  # 积分系数
        self.kd = kd  # 微分系数
        self.max_integral = max_integral  # 积分限幅（防止积分饱和）

        self.error_prev = 0.0  # 上一时刻误差
        self.integral = 0.0  # 积分累积
        self.output = 0.0  # 输出值

    def calculate(self, error: float, dt: float = 0.05) -> float:
        """计算PID输出
        Args:
            error: 误差值
            dt: 控制周期，单位秒
        """
        # 比例项
        p = self.kp * error

        # 积分项（带限幅）
        self.integral += error * dt
        self.integral = max(-self.max_integral, min(self.max_integral, self.integral))
        i = self.ki * self.integral

        # 微分项
        d = self.kd * (error - self.error_prev) / dt if dt > 0 else 0.0

        # 总输出
        self.output = p + i + d
        self.error_prev = error

        return self.output

    def reset(self):
        """重置PID状态"""
        self.error_prev = 0.0
        self.integral = 0.0
        self.output = 0.0


# ========================== 路径点查找器（control.py 融合自find_point.py） ==========================
class PathPointFinderControl:
    """
    路径点查找器 - 管理路径点并查找下一个目标点
    适配control.py的精准操控逻辑，保留前瞻距离+角度标准化
    """

    def __init__(self,
                 path_points: List[Tuple] = None,
                 lookahead_distance: float = 100.0,  # 适配精准绕柱：适度增大前瞻距离
                 lookahead_points: int = 35):  # 适配精准操控：减少前瞻点数，提高响应

        self.unreached_path_points: List[Tuple[float, float, float]] = self._convert_path_points(path_points)
        self.lookahead_distance = lookahead_distance
        self.lookahead_points = lookahead_points

    def _normalize_angle_rad(self, angle: float) -> float:
        """角度标准化：统一到-π ~ π"""
        return math.atan2(math.sin(angle), math.cos(angle))

    def _convert_path_points(self, raw_points: List[Tuple]) -> List[Tuple[float, float, float]]:
        """转换原始路径点为(x,y,航向角)格式，统一角度标准化"""
        if not raw_points:
            return []

        converted = []
        for point in raw_points:
            try:
                x, y, _, cos_dir, sin_dir, _ = point
                direction = self._normalize_angle_rad(math.atan2(sin_dir, cos_dir))
                converted.append((float(x), float(y), direction))
            except (ValueError, TypeError):
                continue
        return converted

    def _get_distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """计算两点间距离"""
        return math.hypot(x2 - x1, y2 - y1)

    def update_unreached_points(self, current_x: float, current_y: float) -> int:
        """更新未到达路径点：删除已过的近点，适配精准绕柱"""
        if not self.unreached_path_points:
            return 0

        max_search = min(self.lookahead_points, len(self.unreached_path_points))
        nearest_idx = 0
        min_dist = float('inf')

        for i in range(max_search):
            x, y, _ = self.unreached_path_points[i]
            dist = self._get_distance(current_x, current_y, x, y)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        # 精准绕柱优化：仅删除距离<20的点，避免误删近柱点
        remove_count = nearest_idx if min_dist < 20.0 else 0
        if remove_count > 0:
            del self.unreached_path_points[:remove_count]
        return remove_count

    def find_target_point(self, current_x: float, current_y: float):
        # ... 前序 update 逻辑 ...
        for i, (x, y, _) in enumerate(self.unreached_path_points):
            dist = self._get_distance(current_x, current_y, x, y)

            # 【核心微调】针对障2出弯点进行视野收敛
            if x > -50 and x < 150:
                adaptive_lookahead = 45.0  # 极短前瞻，强制鱼贴合圆弧，不许提前看障3
            elif abs(x) < 200:
                adaptive_lookahead = 50.0  # 障2近场视野
            else:
                adaptive_lookahead = self.lookahead_distance if dist > 50 else self.lookahead_distance * 0.8

            if dist > adaptive_lookahead:
                break

            if dist > max_dist_in_lookahead:
                max_dist_in_lookahead = dist
                best_idx = i

        if best_idx >= 0:
            return self.unreached_path_points[best_idx]

        return self.unreached_path_points[0]


# ========================== 优化版路径控制器（control.py 融合+增强） ==========================
class PathControllerControl:
    """
    终极优化版路径控制器
    1. 保留control.py精准绕柱/过间隙核心逻辑
    2. 融合find_point.py角度标准化+前瞻路径查找
    3. 动态参数适配，兼顾顺滑跟踪与精准操控
    4. 抗干扰、无抖动、转向丝滑
    """

    def __init__(self,
                 # 游动基础参数（适配精准+顺滑）
                 forward_force: float = 33.0,  # 降低基础推力，平衡速度与操控
                 max_wing_force: float = 70.0,

                 # 鱼尾摆动参数（大幅增加摆动幅度和频率）
                 tail_frequency: float = 1.25,  # 降低频率，减少抖动
                 tail_amplitude: float = 18.5,  # 适度降低幅度，提高稳定性
                 max_tail_angle: float = 80.0,

                 # 航向PID控制器（融合最优参数）
                 yaw_kp: float = 2.2,  # 折中control(2.0)和find_point(2.5)
                 yaw_ki: float = 0.01,  # 降低积分，避免过度修正
                 yaw_kd: float = 0.95,  # 折中微分，兼顾响应与稳定

                 # 滚转平衡控制（减小增益，降低垂直方向扰动）
                 roll_gain: float = 0,  # 小幅降低滚转增益

                 # 精准绕柱参数
                 near_target_distance: float = 150.0,  # 近目标距离阈值
                 min_speed_factor: float = 0.6):  # 最低速度系数，避免停摆

        # 基础游动参数
        self.forward_force = forward_force
        self.max_wing_force = max_wing_force

        # 鱼尾摆动
        self.tail_frequency = tail_frequency
        self.tail_amplitude = tail_amplitude
        self.max_tail_angle = max_tail_angle

        # 滚转修正
        self.roll_gain = roll_gain

        # 精准绕柱参数
        self.near_target_distance = near_target_distance
        self.min_speed_factor = min_speed_factor

        # 相位（鱼尾摆动）
        self.swim_phase = 0.0

        # 航向PID控制器
        self.yaw_pid = PIDControllerControl(kp=yaw_kp, ki=yaw_ki, kd=yaw_kd)
        self.prev_position: Tuple[float, float] = (0.0, 0.0)

    def _normalize_angle_rad(self, angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    def _constrain(self, value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(value, max_val))

    def calculate_control(self,
                          current: Tuple[float, float],
                          current_yaw: float,
                          target_direction: float,
                          roll_angle: float,
                          dt: float = 0.05) -> Tuple[float, float, float]:
        """
        计算控制输出：鱼尾角度、左推力、右推力
        增强特性：
        1. 全局角度标准化，避免跨周期误差
        2. 动态速度适配，精准绕柱+顺滑跟踪
        3. 更鲁棒的数值约束
        """
        # -------------------------- 1. 全局角度标准化 --------------------------
        current_yaw = self._normalize_angle_rad(current_yaw)
        target_direction = self._normalize_angle_rad(target_direction)

        # -------------------------- 2. 计算航向误差（标准化） --------------------------
        yaw_error = target_direction - current_yaw
        yaw_error = self._normalize_angle_rad(yaw_error)
        yaw_error_deg = math.degrees(yaw_error)

        # -------------------------- 3. PID航向控制（平滑转向） --------------------------
        yaw_correction = self.yaw_pid.calculate(yaw_error_deg, dt)
        # 转向量约束：适度放宽到0.8倍最大角度
        yaw_correction = self._constrain(yaw_correction, -self.max_tail_angle * 0.8, self.max_tail_angle * 0.8)
        # -------------------------- 4. 鱼尾摆动 + 转向合成 --------------------------
        # 基础自然摆动（正弦波）
        base_swing = self.tail_amplitude * math.sin(self.swim_phase)
        # 摆动 + PID转向 合成
        tail_angle = base_swing + yaw_correction
        # 最终机械限位
        tail_angle = self._constrain(tail_angle, -self.max_tail_angle, self.max_tail_angle)

        # -------------------------- 5. 胸鳍推力控制（前进+平衡） --------------------------
        # 滚转平衡修正（角度标准化后更稳定）
        roll_angle = self._normalize_angle_rad(roll_angle)
        roll_correct = roll_angle * self.roll_gain
        wing_left = self.forward_force - roll_correct
        wing_right = self.forward_force + roll_correct

        # 推力限幅
        wing_left = self._constrain(wing_left, -self.max_wing_force, self.max_wing_force)
        wing_right = self._constrain(wing_right, -self.max_wing_force, self.max_wing_force)

        # -------------------------- 6. 精准绕柱/过间隙增强处理 --------------------------
        # 计算当前位置到目标点的距离（标准化方向计算）
        target_x = current[0] + math.cos(target_direction) * 100.0
        target_y = current[1] + math.sin(target_direction) * 100.0
        distance_to_target = math.hypot(target_x - current[0], target_y - current[1])

        # 动态速度适配：近目标时降速，且最低速度系数可配置
        if distance_to_target < self.near_target_distance:
            speed_factor = max(self.min_speed_factor, distance_to_target / self.near_target_distance)
            wing_left *= speed_factor
            wing_right *= speed_factor

        # 更新相位
        self.swim_phase += self.tail_frequency * dt * math.pi * 2
        if self.swim_phase > math.pi * 2:
            self.swim_phase -= math.pi * 2

        self.prev_position = current
        return tail_angle, wing_left, wing_right

    def reset(self):
        self.swim_phase = 0.0
        self.yaw_pid.reset()
# ========================== main.py 主程序逻辑 ==========================

# 打开日志文件
log_file = open('log.txt', 'w')

# 采样路径点
points = generate_path()
print(points)

# 创建路径点查找器
path_finder = PathPointFinderFindPoint(path_points=points)
# 创建路径控制器
controller = PathControllerControl()


class PositionTracker:
    """
    位置跟踪器 - 整合路径查找器和控制器
    """

    def __init__(self, path_finder, controller):
        self.path_finder = path_finder
        self.controller = controller

    def calculate_control(self, current_x: float, current_y: float,
                          current_yaw: float, roll_angle: float) -> Tuple[float, float, float]:
        """
        计算控制输出

        Args:
            current_x: 当前位置x坐标
            current_y: 当前位置y坐标
            current_yaw: 当前航向（弧度）

        Returns:
            (tail_angle, wing_force_left, wing_force_right)
        """
        # 查找下一个目标点
        target_x, target_y, _ = self.path_finder.find_target_point(
            current_x, current_y
        )
        target_direction = math.atan2(target_y - current_y, target_x - current_x)
        print(f"实时打印下一个目标点信息：{target_x}, {target_y}, {target_direction})")

        # 如果没有目标点（路径完成），返回停止指令
        if target_x is None or target_y is None or target_direction is None:
            return 0.0, 0.0, 0.0

        # 计算控制参数
        tail_angle, wing_force_left, wing_force_right = self.controller.calculate_control(
            current=(current_x, current_y),
            current_yaw=current_yaw,
            target_direction=target_direction,
            roll_angle=roll_angle
        )

        return tail_angle, wing_force_left, wing_force_right


# 创建位置跟踪器
tracker = PositionTracker(path_finder, controller)


def lcb(fish_info):
    # 获取鱼当前位置和朝向
    current_x = fish_info.pos.x
    current_y = fish_info.pos.y
    current_z = fish_info.pos.z          # 新增：获取垂直坐标
    current_yaw = math.atan2(fish_info.forward.y, fish_info.forward.x)

    # 计算控制输出（原有逻辑）
    tail_angle, wing_force_left, wing_force_right = tracker.calculate_control(
        current_x=current_x,
        current_y=current_y,
        current_yaw=current_yaw,
        roll_angle=fish_info.rot.x
    )

    # ========== 新增：防撞上壁（极小改动）==========
    # 池子高度 1500，安全阈值 1000
    if current_z > 1000:
        # 推力降低到原来的 50%，并施加相反方向的力（让鱼下沉）
        wing_force_left  *= 0.5
        wing_force_right *= 0.5
        # 可选：给一个额外的向下力矩（通过左右推力差，需根据滚转方向调整）
        # 简单做法：让左推力稍小、右推力稍大（假设正滚转会抬头），这里不做复杂处理
    # 如果鱼太低（低于 200），也可以适当增加推力，但不是必须
    elif current_z < 200:
        wing_force_left  *= 1.2
        wing_force_right *= 1.2
    # ============================================

    # 设置控制参数
    ctrlInfo = mycue.FishCtrlInfo()
    ctrlInfo.tail_target_angel = tail_angle
    ctrlInfo.wing_force_left = wing_force_left
    ctrlInfo.wing_force_right = wing_force_right

    # 打印控制参数
    print(f"实时打印控制信息：{ctrlInfo}")

    # 发布控制信息
    pbspulisher.publish(ctrlInfo)


mycue.init('F05012589')
sub = mycue.subscriber(mycue.FishInfo, lcb)
pbspulisher = mycue.publisher(mycue.FishCtrlInfo)

while True:
    time.sleep(1 / 100)
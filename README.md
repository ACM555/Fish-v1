# Fish-v1

水下机器鱼仿真竞赛（第三赛季）项目的 Python 源码仓库。

本仓库**只保存 Python 源码**，不包含游戏本体、引擎、DLL 等大文件。

## 目录结构（与本地项目一致）

| 仓库路径 | 说明 |
| --- | --- |
| `FishSim-V1.0062201（第三赛季）/test.py` | 主控制程序（Dubins 路径 + PID 控制 + 主循环，开发版） |
| `FishSim-V1.0062201（第三赛季）/WindowsNoEditor/Scripts/project2/team1/main.py` | 比赛提交入口脚本 |
| `FishSim-V1.0062201（第三赛季）/WindowsNoEditor/Fish427/Content/Scripts/*.py` | 官方示例脚本 |
| `FishSim-V1.0062201（第三赛季）/WindowsNoEditor/Fish427/Binaries/Win64/cue.py` | 比赛平台 Python 接口 |

## 约定

每次更新任意 `.py` 文件后，都要把改动上传到本仓库（<https://github.com/ACM555/Fish-v1>）：

```bat
cmd /c "D:\Fish\push_python.cmd" "本次改了什么"
```

脚本会自动 `git add` 所有 `.py`、提交、推送到 `origin/main`；游戏本体、引擎、二进制、日志都被
`.gitignore` 排除，不会进入仓库。详见 [AGENTS.md](AGENTS.md)。

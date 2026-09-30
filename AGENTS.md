# 项目约定（对 AI 助手 / 协作者）

## 硬性规则：Python 文件一有更新就必须上传

远程仓库：<https://github.com/ACM555/Fish-v1>（public，只放 Python 源码）

**任何一次对项目内 `.py` 文件的改动（新增 / 修改 / 删除）完成后，必须立刻执行上传：**

```powershell
pwsh -File D:\Fish\push_python.ps1 -Message "一句话说明这次改了什么"
```

- 上传只包含 `.py` 源码与仓库说明文件，游戏本体 / 引擎 / 二进制 / 日志都不会上传。
- 一次改动 = 一次提交 + 一次推送，不要攒批。
- 推送失败（网络 / 鉴权）时必须重试并明确报告失败原因，不能默默跳过。

## 项目概况

- 工作目录：`D:\Fish`
- 游戏本体：`FishSim-V1.0062201（第三赛季）\WindowsNoEditor\`
- 我们自己的 Python 代码：
  - `FishSim-V1.0062201（第三赛季）\test.py`
  - `FishSim-V1.0062201（第三赛季）\WindowsNoEditor\Scripts\project2\team1\main.py`
- 平台 Python 接口：`...\WindowsNoEditor\Fish427\Binaries\Win64\cue.py`
- 引擎自带的 Python 标准库（`...\Win64\Lib\`、`Tools\`、`tcl\`、`Engine\`）**不是我们的代码，永不上传**。

## 环境注意

- 沙箱 `workspace-write` 模式下 `pwsh` 进程无法启动（退出码 0xC0000142），
  需要跑 git / 脚本时请用一次性的 `danger-full-access` 提权重试。
- `gh` CLI 已登录账号 ACM555，git 凭据助手已指向 `gh auth git-credential`。

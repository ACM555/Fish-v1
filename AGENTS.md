# 项目约定（对 AI 助手 / 协作者）

## 硬性规则：Python 文件一有更新就必须上传

远程仓库：<https://github.com/ACM555/Fish-v1>（public，只放 Python 源码）

**任何一次对项目内 `.py` 文件的改动（新增 / 修改 / 删除）完成后，必须立刻执行上传：**

```bat
cmd /c "D:\Fish\push_python.cmd" "一句话说明这次改了什么"
```

等价的 PowerShell 写法（本机执行策略是 RemoteSigned，必须带 Bypass）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\Fish\push_python.ps1 -Message "一句话说明这次改了什么"
```

- 上传只包含 `.py` 源码与仓库说明文件；游戏本体 / 引擎 / 二进制 / 日志由 `.gitignore` 排除，**不会被上传**。
- 一次改动 = 一次提交 + 一次推送，不要攒批；推送成功以 `git push` 退出码 0 为准。
- 推送失败（网络 / 鉴权）必须重试并明确报告失败原因，不能默默跳过。
- 上传后用 `git ls-tree -r --name-only origin/main` 或
  `gh api repos/ACM555/Fish-v1/commits/main --jq .sha` 复核远端确实收到了。

## 项目概况

- 工作目录：`D:\Fish`（本身就是 git 仓库，remote `origin` 指向上面的地址）
- 游戏本体：`FishSim-V1.0062201（第三赛季）\WindowsNoEditor\`
- 我们自己的 Python 代码：
  - `FishSim-V1.0062201（第三赛季）\test.py`
  - `FishSim-V1.0062201（第三赛季）\WindowsNoEditor\Scripts\project2\team1\main.py`
- 平台 Python 接口：`...\WindowsNoEditor\Fish427\Binaries\Win64\cue.py`
- 引擎自带的 Python 标准库（`...\Win64\Lib\`、`Tools\`、`tcl\`、`Engine\`）**不是我们的代码，永不上传**。

## 环境注意（重要）

1. 本机**没有 PowerShell 7（`pwsh` 不在 PATH）**，DSH 的 shell 实际是
   `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`（5.1）。写脚本请按 5.1 兼容，
   含中文的 `.ps1` 建议保存为 **UTF-8 with BOM**。
2. 执行策略为 `RemoteSigned`，未签名脚本会被拒绝 → 运行 `.ps1` 必须加 `-ExecutionPolicy Bypass`，
   或直接调用 `push_python.cmd`。
3. 沙箱 `workspace-write` 模式下 `powershell` 进程无法启动（退出码 `0xC0000142`），
   读文件用 read/grep/glob 工具即可；需要跑 git / 脚本时用一次性的 `danger-full-access` 提权重试。
4. `gh` CLI（`C:\Program Files\GitHub CLI\gh.exe`）已登录账号 **ACM555**，
   git 凭据助手已指向 `gh auth git-credential`，push 无需再输密码。

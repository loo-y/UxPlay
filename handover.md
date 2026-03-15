# Handover

## 1. 今天实际遇到的问题

- Windows 上原始 `uxplay.exe` 可以接收 iPhone 投屏，但直接以前台控制台方式启动时，窗口容易快速退出，导致 iPhone 上的 AirPlay 目标瞬间消失。
- 本地编译的 Windows 版本最初还遇到了 GStreamer 插件缺失和插件注册表异常，表现为 `Required gstreamer plugin ... not found`，以及部分 DLL/插件加载不稳定。
- 做“桌面应用宿主”时，第一版 `PowerShell + WinForms` 只是启动器，不是用户想要的真正桌面应用；而且最早尝试的 `-hwnd` 直嵌渲染虽然能建立音视频链路，但画面不能稳定显示在宿主窗口里。
- 切到 `PySide6` 后，又遇到两个具体问题：
  - Qt 宿主里点击“启动”时，`gst-inspect-1.0` 通过相对命令名找不到，导致启动前预热阶段直接失败，iPhone 看不到 `UxPlay-Windows`，界面日志也为空。
  - Qt 宿主最初对子窗口尺寸的计算使用了 Qt 逻辑像素，挂进去的 `Direct3D12 Renderer` 没有铺满右侧画布；这和 Windows DPI/缩放比有关。

这些问题影响的核心能力分别是：

- Windows 端稳定广播 AirPlay 服务
- 稳定接收并持续显示 iPhone 投屏
- 在桌面宿主应用中显示投屏，而不是只弹一个裸 `Direct3D12 Renderer`

## 2. 原因判断与结论

- Windows 启动不稳定的根因不是 iPhone 端操作，而是本机这套 Windows 构建和 GStreamer 运行时组合对启动方式敏感。稳定方案是：
  - 用仓库内 `.local\msys64` 提供的 GStreamer 运行时
  - 使用 `GST_REGISTRY_FORK=no`
  - 启动前先预热 GStreamer registry
  - 用独立桌面进程启动 `uxplay.exe`
- 第一版宿主应用中，“`-hwnd` 直接把 GStreamer sink 嵌进 Qt/WinForms`”虽然理论可行，但在这台机器上没有跑通稳定出画；音频能通，但画面不能稳定显示。
- 当前最可信并且已经验证成功的桌面宿主方案，不再依赖 `-hwnd` 直嵌，而是：
  - 正常让 `uxplay.exe` 自己创建可正常出画的 `Direct3D12 Renderer`
  - 再把这个原生渲染窗口重挂到 `PySide6` 右侧画布中
- Qt 宿主“启动无日志、iPhone 看不到目标”的根因已经确认并修复：
  - `gst-inspect-1.0` 查找方式错误
  - `subprocess.Popen` 的日志句柄管理不当
- 右侧画布未铺满的问题，当前判断是 Windows 高 DPI/缩放比导致的原生像素和 Qt 逻辑像素不一致。已按原生像素重新计算子窗口尺寸，用户反馈“这次对了”。

## 3. 这次已经落地的修复

- [lib/CMakeLists.txt](/C:/Users/luyi1/code/github/UxPlay/lib/CMakeLists.txt)
  - 去掉 Windows 构建对 Bonjour SDK 的硬依赖，改为运行时加载 `dnssd.dll`
  - 作用：降低本机 Windows 编译门槛，让已有 Bonjour 服务即可工作

- [lib/dnssd.c](/C:/Users/luyi1/code/github/UxPlay/lib/dnssd.c)
- [lib/windows_dns_sd.h](/C:/Users/luyi1/code/github/UxPlay/lib/windows_dns_sd.h)
  - 增加 Windows 运行时 DNS-SD 适配
  - 作用：支持在没有 Bonjour SDK 开发头文件的情况下仍可注册 AirPlay 服务

- [lib/http_handlers.h](/C:/Users/luyi1/code/github/UxPlay/lib/http_handlers.h)
  - 修正 `libplist` 较新版本兼容问题
  - 作用：让本地 Windows 构建能正常通过并运行

- [uxplay.cpp](/C:/Users/luyi1/code/github/UxPlay/uxplay.cpp)
- [renderers/video_renderer.h](/C:/Users/luyi1/code/github/UxPlay/renderers/video_renderer.h)
- [renderers/video_renderer.c](/C:/Users/luyi1/code/github/UxPlay/renderers/video_renderer.c)
  - 新增 `-top` 选项，并在 Windows 上为视频窗口应用置顶逻辑
  - 尝试过 `-hwnd` 内嵌窗口渲染支持；当前代码仍保留该参数，但最终桌面宿主方案没有继续依赖它
  - 作用：提供 Windows 窗口置顶能力，并为后续宿主化探索提供底层能力

- [scripts/run-uxplay-windows.cmd](/C:/Users/luyi1/code/github/UxPlay/scripts/run-uxplay-windows.cmd)
- [launch-uxplay-windows.cmd](/C:/Users/luyi1/code/github/UxPlay/launch-uxplay-windows.cmd)
- [launch-uxplay-windows-no-topmost.cmd](/C:/Users/luyi1/code/github/UxPlay/launch-uxplay-windows-no-topmost.cmd)
- [launch-uxplay-windows-gui.cmd](/C:/Users/luyi1/code/github/UxPlay/launch-uxplay-windows-gui.cmd)
- [scripts/keep-uxplay-topmost.ps1](/C:/Users/luyi1/code/github/UxPlay/scripts/keep-uxplay-topmost.ps1)
- [scripts/uxplay-launcher-gui.ps1](/C:/Users/luyi1/code/github/UxPlay/scripts/uxplay-launcher-gui.ps1)
  - 固化 Windows 一键启动、非置顶启动、简单 GUI 启动和置顶守护脚本
  - 作用：保留已经验证成功的传统启动链，方便日常快速使用
  - 结论：这是稳定可用链路，属于当前可用的长期备用方案

- [scripts/uxplay_desktop_qt.py](/C:/Users/luyi1/code/github/UxPlay/scripts/uxplay_desktop_qt.py)
- [scripts/launch-uxplay-desktop-app.ps1](/C:/Users/luyi1/code/github/UxPlay/scripts/launch-uxplay-desktop-app.ps1)
- [launch-uxplay-desktop-app.cmd](/C:/Users/luyi1/code/github/UxPlay/launch-uxplay-desktop-app.cmd)
  - 新增 `PySide6` 桌面宿主应用
  - 左侧提供中文设置区、状态区、日志区
  - 右侧提供投屏画布，并把 `uxplay.exe` 创建的 `Direct3D12 Renderer` 重挂进去
  - 使用文件日志 + `subprocess.Popen` 启动链，解决了 Qt 中无日志、无广播的问题
  - 已针对高 DPI/缩放比对子窗口尺寸做原生像素换算修复
  - 作用：提供真正的桌面应用宿主，而不是简单壳子
  - 结论：这是当前桌面应用方向的 MVP 方案

- [docs/windows-iphone-mirroring.md](/C:/Users/luyi1/code/github/UxPlay/docs/windows-iphone-mirroring.md)
- [docs/windows-successful-mirroring-state.md](/C:/Users/luyi1/code/github/UxPlay/docs/windows-successful-mirroring-state.md)
- [README.md](/C:/Users/luyi1/code/github/UxPlay/README.md)
  - 补充 Windows 使用路径、桌面宿主入口和当前结论
  - 作用：让后续接手者和用户知道当前哪条链路是真正可用的

## 4. 已验证结果

- 已在这台 Windows 机器上真实跑通 iPhone 投屏到 `uxplay.exe`
- 已验证传统一键入口可稳定工作：
  - 双击 `launch-uxplay-windows.cmd`
  - iPhone 可发现 `UxPlay-Windows`
  - 停止镜像后可再次连接
- 已验证置顶链路可工作
- 已验证桌面宿主链路可工作到以下程度：
  - `PySide6` 宿主界面可正常启动
  - 在宿主中点击“启动”后，日志可见
  - iPhone 可发现并连接
  - 日志中可见：
    - `connection request from iPhone 15`
    - `raop_rtp_mirror starting mirroring`
    - `Begin streaming to GStreamer video pipeline`
    - `渲染窗口已挂接到宿主画布。`
  - 用户确认投屏成功，且右侧画布铺满问题在 DPI 修复后“这次对了”
- 已验证基础静态检查：
  - `py_compile scripts/uxplay_desktop_qt.py`
  - Qt 最小窗口烟雾测试通过
  - `uxplay.exe -h` 可看到新增的 Windows 参数

## 5. 当前仍存在的问题 / 边界

- 这套桌面宿主仍然是开发态方案，不是最终给普通用户分发的成品。
- 宿主应用本质上仍然是：
  - `PySide6` 外层壳
  - `uxplay.exe` 子进程
  - 将其 `Direct3D12 Renderer` 窗口重挂到宿主画布中
  不是单进程内原生播放器架构。
- 目前没有做自动化端到端测试；验证依赖真实 iPhone 和这台 Windows 主机。
- 仓库里还保留了多条 Windows 入口：
  - 传统控制台启动
  - 简单 GUI 启动
  - Qt 桌面宿主
  对新接手的人来说选择较多，需要文档明确区分用途。
- 当前宿主 UI 已中文化并做过一轮样式打磨，但仍有继续打磨空间，例如更正式的工具栏、连接状态面板、全屏模式、日志抽屉等。

## 6. 最终想实现的产品目标

- 最终希望交付的是一个真正给 Windows 普通用户使用的桌面投屏应用，而不是要求用户理解：
  - `.local\msys64`
  - GStreamer 环境变量
  - 多种 `.cmd/.ps1` 启动入口
  - `uxplay.exe` 和宿主应用的关系
- 理想产品形态应当是：
  - 一个桌面应用窗口
  - 内部显示 iPhone 投屏内容
  - 提供顶部设置栏/工具栏
  - 可直接控制置顶、开始/停止、设备名称、全屏等
  - 最终可打包为更易分发的 Windows 应用

## 7. 后续 TODO

1. 继续精修 Qt 宿主的视频区域行为
   - 目标：确保不同 DPI、不同显示缩放比、不同窗口大小下，挂接进来的 `uxplay` 渲染窗口都能正确铺满画布
   - 意义：解决最后一类“宿主画布和实际视频区域不一致”的视觉问题

2. 梳理并收敛 Windows 启动入口
   - 目标：明确哪些入口是“传统稳定备用链路”，哪些是“桌面宿主链路”
   - 意义：降低后续维护和用户理解成本

3. 给 Qt 宿主补更明确的运行状态与错误提示
   - 目标：在 UI 中明确显示“未启动 / 广播中 / 已连接 / 已挂接 / 已退出”
   - 意义：用户不必只靠日志判断当前状态

4. 评估是否需要将 `uxplay.exe` 子进程控制进一步产品化
   - 目标：决定是继续使用“原生渲染窗口重挂”路线，还是未来切到更彻底的播放器架构
   - 意义：为后续做正式桌面产品和更稳定分发做架构准备

5. 准备最终分发方案
   - 目标：让 Windows 用户最终不需要手动配置 Python、PySide6、GStreamer 路径和脚本入口
   - 意义：从“开发态可用”推进到“普通用户可安装可使用”

# Changelog

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/) 约定，版本号参考 [SemVer](https://semver.org/lang/zh-CN/)。

## [0.3.0-beta] - 2026-10-11

### Quality
- 将快捷键「归一化」与「冲突检测」从 `app/hotkeys.py` 抽离为 **PySide6 无关**的 `app/hotkey_parser.py`，
  新增可在无 GUI 环境（含 CI / 沙箱）直接运行的纯逻辑单测 `tests/test_hotkey_parser.py`，消除对 GUI 依赖的测试耦合。
- 测试矩阵补充版本常量单测，与既有 40+ 个 GUI / 集成 / 回归测试并存，CI 在 PR 与 push 到 `main` 时一并运行。
- 新增 `tests/test_runtime.py`：覆盖打包（frozen）与源码两种形态下 `main_script` /
  `sys_executable` 的取值分支——开机自启逻辑依赖该路径，且此模块不依赖 PySide6 可离线验证。

### Docs
- `ARCHITECTURE.md`、`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md` 持续完善；
  release 工作流 `release-windows.yml` 为硬门禁（无 `continue-on-error`），保证发布产物可复现。

## [0.2.x] - 历史版本
- Windows OCR / 可选 PaddleOCR、多翻译后端、实时叠加、DPI 适配等能力迭代。

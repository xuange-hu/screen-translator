# Architecture & Refactoring Roadmap

> 本文记录 ScreenTranslator 的模块边界与已知结构债，并给出**已规划、尚未执行**的重构路线。
> 目的是让维护者与面试官一眼看清：哪些是大文件、为什么暂时不拆、以及拆法。

## 分层

```
main.py                入口：解析参数、装配 Application、启动 Qt 事件循环
app/                   UI 无关的"控制器"层（mixin 组合到 Application）
  application.py       Application 主体（组合各 mixin）
  *_mixin.py           按职责切分的控制器片段（capture / monitor / pipeline / hotkeys / settings / status / history）
ui/                    PySide6 视图层（窗口、对话框、覆盖层、托盘）
services/              领域服务（OCR 后端、翻译后端、截图、更新、诊断）
workers/               后台 worker（翻译线程）
utils/                纯函数工具（DPI、图像、文本、语言、布局）
```

设计上已经用 **mixin 组合**把 `Application` 按职责拆开（`capture_mixin` / `monitor_mixin` /
`pipeline_mixin` / `hotkeys_mixin` / `settings_mixin` / `status_mixin` / `history_mixin`），
避免把所有逻辑堆进一个类。

## 已知结构债（待重构）

| 文件 | 大小 | 问题 | 计划拆法 |
|---|---|---|---|
| `ui/settings_dialog.py` | ~64 KB | 设置对话框把所有标签页与校验逻辑塞进一个类 | 按"标签页"拆为 `ui/settings/*.py`，每页一个 `QWidget` 子类 |
| `app/application.py` | ~61 KB | 主体类仍偏大（尽管已 mixin 化） | 继续把"启动/更新/版本"流程抽到独立 service |
| `assets/` | ~3.8 MB | 多版启动图冗余（仅 `app_launch_v4.ico` 被构建引用） | 保留被引用的 ico，其余作为历史快照移出仓库或压缩 |

> 这些是大体量 GUI 代码，重构需配合 PySide6 渲染回归测试，**不在无 GUI 环境里盲拆**，
> 以免破坏发布构建。优先级低于功能与合规。

## 质量门禁

- `ci.yml`：`test`（Windows + PySide6 offscreen 跑 `pytest`）+ `lint`（ruff，增量规则集见 `pyproject.toml`）。
- 静默 `except` 已逐步改为带 `logger.debug` 的兜底，便于排障时追溯。
- 类型检查：`pyproject.toml` 提供 `mypy` 配置，本地 `python -m mypy app services utils workers` 渐进补齐注解。

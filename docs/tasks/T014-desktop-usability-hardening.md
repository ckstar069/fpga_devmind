# T014: Desktop Shell Usability Hardening

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

让桌面 GUI 达到开发者自用的第一个可用版本。不新增 Web GUI，不做 Electron，不接入 LLM，不运行 Vivado。

## Changes

### 1. PySide6 Optional Dependency

`pyproject.toml` 新增 `[project.optional-dependencies] desktop = ["PySide6>=6.7,<7"]`。

安装方式：
```bash
pip install -e ".[desktop]"
```

`desktop_app.py` fallback 提示更新为包含 `.[desktop]` 安装命令。

### 2. Sample Artifacts Helper

新增 `src/fpga_devmind/desktop/sample_artifacts.py`：

- `find_recent_artifact_bundles(base_dirs=None) → list[ArtifactBundleInfo]`
- `ArtifactBundleInfo` dataclass: path, bundle_type, mtime
- 默认扫描 `/tmp/fpga_devmind` 和 `/private/tmp/fpga_devmind`
- 复用 `artifact_loader.detect_bundle_type()` 判断 bundle 类型
- 按 mtime 降序排列
- 只读扫描，不修改任何文件

`desktop_app.py` 新增 `--recent` 参数：
```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```
自动选择最近的 bundle。没找到 → 打印提示，exit 0。

### 3. GUI Load-State Clarity

`_gui.py` 改善：

- Diagnostics tab: bundle is None 时显示 "No bundle loaded."
- Concept Trace tab: bundle is None 时在 Nodes 子表显示 "No bundle loaded."
- Plan Preview placeholder: "Load an artifact bundle first."

### 4. Tests

- `tests/test_sample_artifacts.py`: 5 tests（P1b/P1a 发现、不存在的 base_dir、非 bundle 目录跳过、mtime 排序）
- `tests/test_desktop_app_fallback.py`: 1 test（fallback 消息含 `.[desktop]`）

### 5. Documentation

- 本任务卡
- `docs/desktop-gui-smoke-test.md`: 手工 GUI smoke 文档

## Files

```text
pyproject.toml                                      — 修改: [project.optional-dependencies]
src/fpga_devmind/desktop_app.py                     — 修改: --recent, fallback 提示
src/fpga_devmind/desktop/sample_artifacts.py        — 新增: find_recent_artifact_bundles
src/fpga_devmind/desktop/_gui.py                    — 修改: 空状态提示
tests/test_sample_artifacts.py                      — 新增: 5 tests
tests/test_desktop_app_fallback.py                  — 新增: 1 test
docs/tasks/T014-desktop-usability-hardening.md      — 新增: 本任务卡
docs/desktop-gui-smoke-test.md                      — 新增: 手工 smoke 文档
docs/implementation-status.md                       — 修改: T014 条目
docs/p1a-v0.1-quickstart.md                         — 修改: Desktop Shell 补充
```

## Boundaries

```text
- No Vivado / synthesis / implementation / bitstream
- No fpga_project_* mutation
- No LLM / external API / API key
- No Web GUI / Electron / browser URL
- No PASS / HOLD / finding / audit
- Output only to /tmp or /private/tmp
```

## Next Steps

- T017 (future): Desktop Agent Trace Viewer — render `agent_runtime_trace.json` in GUI
- T018 (future): Real LLM provider integration

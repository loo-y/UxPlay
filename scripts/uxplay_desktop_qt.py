from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime" / "windows-mirroring"
SETTINGS_PATH = RUNTIME_DIR / "desktop-app-settings.json"
UXPLAY_EXE = ROOT / "build-manual" / "uxplay.exe"
UCRT_BIN = ROOT / ".local" / "msys64" / "ucrt64" / "bin"
USR_BIN = ROOT / ".local" / "msys64" / "usr" / "bin"
GST_INSPECT_EXE = UCRT_BIN / "gst-inspect-1.0.exe"
DESKTOP_STDOUT_LOG = RUNTIME_DIR / "desktop-app-uxplay.stdout.log"
DESKTOP_STDERR_LOG = RUNTIME_DIR / "desktop-app-uxplay.stderr.log"


class WindowApi:
    user32 = ctypes.windll.user32

    GWL_STYLE = -16
    WS_CHILD = 0x40000000
    WS_POPUP = 0x80000000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_MINIMIZE = 0x20000000
    WS_MAXIMIZE = 0x01000000
    WS_SYSMENU = 0x00080000
    SW_SHOW = 5

    @staticmethod
    def iter_top_level_windows() -> list[int]:
        handles: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            if WindowApi.user32.IsWindowVisible(hwnd) and WindowApi.user32.GetWindow(hwnd, 4) == 0:
                handles.append(int(hwnd))
            return True

        WindowApi.user32.EnumWindows(enum_proc, 0)
        return handles

    @staticmethod
    def get_process_window(process_id: int) -> int:
        pid = ctypes.c_ulong()
        for hwnd in WindowApi.iter_top_level_windows():
            WindowApi.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == process_id:
                return hwnd
        return 0

    @staticmethod
    def attach_window(child_hwnd: int, parent_hwnd: int, rect: QRect) -> None:
        WindowApi.user32.SetParent(child_hwnd, parent_hwnd)
        style = WindowApi.user32.GetWindowLongPtrW(child_hwnd, WindowApi.GWL_STYLE)
        style |= WindowApi.WS_CHILD
        style &= ~WindowApi.WS_POPUP
        style &= ~WindowApi.WS_CAPTION
        style &= ~WindowApi.WS_THICKFRAME
        style &= ~WindowApi.WS_MINIMIZE
        style &= ~WindowApi.WS_MAXIMIZE
        style &= ~WindowApi.WS_SYSMENU
        WindowApi.user32.SetWindowLongPtrW(child_hwnd, WindowApi.GWL_STYLE, style)
        WindowApi.user32.ShowWindow(child_hwnd, WindowApi.SW_SHOW)
        WindowApi.move_window(child_hwnd, rect)

    @staticmethod
    def move_window(hwnd: int, rect: QRect) -> None:
        WindowApi.user32.MoveWindow(hwnd, rect.x(), rect.y(), rect.width(), rect.height(), True)


@dataclass
class HostSettings:
    server_name: str = "UxPlay-Windows"
    topmost: bool = True


def load_settings() -> HostSettings:
    if not SETTINGS_PATH.exists():
        return HostSettings()
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return HostSettings()
    return HostSettings(
        server_name=payload.get("server_name") or "UxPlay-Windows",
        topmost=bool(payload.get("topmost", True)),
    )


def save_settings(settings: HostSettings) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(
            {
                "server_name": settings.server_name,
                "topmost": settings.topmost,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


class VideoSurface(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("videoSurface")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.placeholder = QLabel("等待投屏画面接入")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("videoPlaceholder")
        self.badge = QLabel("实时投屏")
        self.badge.setObjectName("surfaceBadge")
        self.caption = QLabel("画面将尽量占满当前画布")
        self.caption.setObjectName("surfaceCaption")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.badge, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.caption, 1, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.placeholder, 0, 0, 2, 2, Qt.AlignmentFlag.AlignCenter)
        layout.setRowStretch(2, 1)
        layout.setColumnStretch(1, 1)

    def native_target_rect(self) -> QRect:
        ratio = self.devicePixelRatioF()
        if self.window().windowHandle() is not None:
            ratio = self.window().windowHandle().devicePixelRatio()
        width = max(1, int(round(self.width() * ratio)))
        height = max(1, int(round(self.height() * ratio)))
        return QRect(0, 0, width, height)


class UxPlayDesktopWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.process: subprocess.Popen[str] | None = None
        self.stdout_handle = None
        self.stderr_handle = None
        self.renderer_hwnd = 0
        self.log_cursor = 0

        self.attach_timer = QTimer(self)
        self.attach_timer.setInterval(700)
        self.attach_timer.timeout.connect(self._poll_renderer_window)

        self.log_timer = QTimer(self)
        self.log_timer.setInterval(500)
        self.log_timer.timeout.connect(self._poll_log_file)

        self.setWindowTitle("UxPlay 桌面投屏")
        self.resize(1320, 820)
        self.setMinimumSize(1040, 680)
        self._build_ui()
        self._apply_style()
        self._apply_settings()

    def _build_ui(self) -> None:
        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(14, 14, 14, 14)
        shell.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(312)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(18)

        title = QLabel("UxPlay 桌面投屏")
        title.setObjectName("titleLabel")
        subtitle = QLabel("把 iPhone 投屏放进独立桌面应用里，并直接在宿主窗口控制置顶、启动和停止。")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)

        status_row = QHBoxLayout()
        self.status_badge = QLabel("待机")
        self.status_badge.setObjectName("statusBadge")
        self.status_summary = QLabel("准备就绪，可以启动接收端。")
        self.status_summary.setObjectName("statusSummary")
        self.status_summary.setWordWrap(True)
        status_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(self.status_summary, 1)

        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 16, 16, 16)
        settings_layout.setSpacing(14)

        settings_title = QLabel("会话设置")
        settings_title.setObjectName("sectionTitle")
        settings_form = QFormLayout()
        settings_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        settings_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        settings_form.setHorizontalSpacing(12)
        settings_form.setVerticalSpacing(12)

        self.server_name_edit = QLineEdit()
        self.server_name_edit.setPlaceholderText("UxPlay-Windows")
        self.topmost_checkbox = QCheckBox("让宿主窗口保持置顶")

        settings_form.addRow("设备名称", self.server_name_edit)
        settings_form.addRow("", self.topmost_checkbox)
        settings_layout.addWidget(settings_title)
        settings_layout.addLayout(settings_form)

        actions_card = QFrame()
        actions_card.setObjectName("card")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(12)

        actions_title = QLabel("控制")
        actions_title.setObjectName("sectionTitle")

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.start_button = QPushButton("启动")
        self.start_button.setObjectName("primaryButton")
        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("secondaryButton")
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        hint = QLabel("右侧画布会承载 UxPlay 的渲染窗口，因此置顶和布局都由这个宿主应用控制。")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)

        actions_layout.addWidget(actions_title)
        actions_layout.addLayout(button_row)
        actions_layout.addWidget(hint)

        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.setSpacing(10)
        log_title = QLabel("运行日志")
        log_title.setObjectName("sectionTitle")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(400)
        self.log_view.setObjectName("logView")
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log_view)

        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addLayout(status_row)
        sidebar_layout.addWidget(settings_card)
        sidebar_layout.addWidget(actions_card)
        sidebar_layout.addWidget(log_card, 1)

        main_area = QFrame()
        main_area.setObjectName("mainArea")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)
        self.video_surface = VideoSurface()
        self.video_surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.video_surface, 1)

        shell.addWidget(sidebar)
        shell.addWidget(main_area, 1)
        self.setCentralWidget(root)

        topmost_action = QAction("置顶", self, checkable=True)
        topmost_action.setChecked(self.settings.topmost)
        topmost_action.toggled.connect(self._toggle_topmost)
        self.addAction(topmost_action)

        self.start_button.clicked.connect(self.start_receiver)
        self.stop_button.clicked.connect(self.stop_receiver)
        self.topmost_checkbox.toggled.connect(self._toggle_topmost)

    def _apply_style(self) -> None:
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#10151c"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#0d1117"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#edf2f7"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#edf2f7"))
        self.setPalette(palette)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #10151c; color: #edf2f7; font-family: 'Segoe UI'; }
            #sidebar, #mainArea { background: #161d27; border: 1px solid #243041; border-radius: 24px; }
            #titleLabel { font-size: 28px; font-weight: 700; letter-spacing: 0.4px; }
            #subtitleLabel { color: #9fb0c4; font-size: 13px; line-height: 1.4; }
            #statusBadge {
                background: #1d5f4b; color: #d9fff2; border-radius: 999px;
                padding: 6px 12px; font-weight: 700; min-width: 64px;
            }
            #statusSummary { color: #cad5e2; font-size: 13px; }
            #card {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a2330, stop:1 #141b24);
                border: 1px solid #253244; border-radius: 18px;
            }
            #sectionTitle { font-size: 15px; font-weight: 700; color: #f6f8fb; }
            #hintLabel { color: #95a6ba; font-size: 12px; }
            QLineEdit, QPlainTextEdit {
                background: #0f141b; border: 1px solid #2b3b4f; border-radius: 12px;
                padding: 10px 12px; selection-background-color: #e97b39;
            }
            QPushButton {
                min-height: 40px; border-radius: 12px; padding: 0 14px; font-weight: 700;
                border: 1px solid transparent;
            }
            #primaryButton { background: #e97b39; color: #10151c; }
            #primaryButton:hover { background: #f08a4c; }
            #secondaryButton { background: #1a2431; color: #edf2f7; border-color: #2f4157; }
            #secondaryButton:hover { background: #233142; }
            #videoSurface {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a0e13, stop:1 #141a23);
                border: 1px solid #304052; border-radius: 26px;
            }
            #videoPlaceholder { color: #7f8da0; font-size: 16px; font-weight: 600; }
            #surfaceBadge {
                background: rgba(233, 123, 57, 0.92);
                color: #10151c;
                border-radius: 999px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
                margin: 14px 0 0 14px;
            }
            #surfaceCaption {
                color: #d6e0ea;
                background: rgba(10, 14, 19, 0.64);
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 11px;
                margin: 48px 0 0 14px;
            }
            #logView { font-family: 'Cascadia Mono'; font-size: 11px; color: #d4dde7; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator {
                width: 18px; height: 18px; border-radius: 6px; border: 1px solid #40546c; background: #0f141b;
            }
            QCheckBox::indicator:checked { background: #e97b39; border-color: #e97b39; }
            """
        )

    def _apply_settings(self) -> None:
        self.server_name_edit.setText(self.settings.server_name)
        self.topmost_checkbox.setChecked(self.settings.topmost)
        self._toggle_topmost(self.settings.topmost)
        self._set_running_state(False)

    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text.rstrip())

    def _save_settings(self) -> None:
        server_name = self.server_name_edit.text().strip() or "UxPlay-Windows"
        self.settings = HostSettings(server_name=server_name, topmost=self.topmost_checkbox.isChecked())
        save_settings(self.settings)

    def _set_running_state(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.server_name_edit.setEnabled(not running)
        self.video_surface.placeholder.setVisible(not running)
        self.status_badge.setText("运行中" if running else "待机")
        self.status_badge.setStyleSheet(
            "background: #8b2f2f; color: #fff1ef; border-radius: 999px; padding: 6px 12px; font-weight: 700;"
            if running
            else "background: #1d5f4b; color: #d9fff2; border-radius: 999px; padding: 6px 12px; font-weight: 700;"
        )

    def _toggle_topmost(self, checked: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()
        self.settings.topmost = checked
        save_settings(self.settings)

    def _build_environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PATH"] = f"{UCRT_BIN};{USR_BIN};{env.get('PATH', '')}"
        env["GST_PLUGIN_SCANNER"] = str(ROOT / ".local" / "msys64" / "ucrt64" / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe")
        env["GST_PLUGIN_SYSTEM_PATH_1_0"] = str(ROOT / ".local" / "msys64" / "ucrt64" / "lib" / "gstreamer-1.0")
        env["GST_REGISTRY_FORK"] = "no"
        env["GST_REGISTRY"] = str(RUNTIME_DIR / "gstreamer-registry.bin")
        return env

    def _warm_registry(self, env: dict[str, str]) -> None:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        registry = RUNTIME_DIR / "gstreamer-registry.bin"
        if registry.exists():
            registry.unlink()
        subprocess.run(
            [str(GST_INSPECT_EXE), "app", "libav", "playback", "autodetect", "videoparsersbad"],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def _write_boot_log(self) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_log(f"[{timestamp}] 启动 UxPlay: {self.settings.server_name}")
        self._append_log(f"[{timestamp}] 输出日志: {DESKTOP_STDOUT_LOG.name}")
        self._append_log(f"[{timestamp}] 错误日志: {DESKTOP_STDERR_LOG.name}")

    def _poll_log_file(self) -> None:
        if not DESKTOP_STDOUT_LOG.exists():
            return
        try:
            with DESKTOP_STDOUT_LOG.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self.log_cursor)
                chunk = handle.read()
                self.log_cursor = handle.tell()
        except OSError:
            return

        if chunk:
            self._append_log(chunk)

    def start_receiver(self) -> None:
        self._save_settings()
        if not UXPLAY_EXE.exists():
            QMessageBox.critical(self, "UxPlay 桌面投屏", "未找到 build-manual\\uxplay.exe。")
            return

        self.stop_receiver()
        DESKTOP_STDOUT_LOG.write_text("", encoding="utf-8")
        DESKTOP_STDERR_LOG.write_text("", encoding="utf-8")
        self.log_cursor = 0
        self._write_boot_log()
        env = self._build_environment()

        try:
            self._warm_registry(env)
        except Exception as exc:
            self._append_log(f"预热 GStreamer 失败: {exc}")
            self.status_summary.setText("GStreamer 预热失败，请查看运行日志。")
            return

        args = [
            str(UXPLAY_EXE),
            "-n",
            self.settings.server_name,
            "-nh",
            "-vs",
            "d3d12videosink",
            "-as",
            "wasapisink",
        ]
        self.stdout_handle = DESKTOP_STDOUT_LOG.open("w", encoding="utf-8", errors="replace")
        self.stderr_handle = DESKTOP_STDERR_LOG.open("w", encoding="utf-8", errors="replace")
        try:
            self.process = subprocess.Popen(
                args,
                cwd=ROOT,
                env=env,
                stdout=self.stdout_handle,
                stderr=self.stderr_handle,
                text=True,
            )
        except Exception as exc:
            self._append_log(f"启动 uxplay.exe 失败: {exc}")
            self.status_summary.setText("启动 uxplay.exe 失败，请查看运行日志。")
            if self.stdout_handle:
                self.stdout_handle.close()
                self.stdout_handle = None
            if self.stderr_handle:
                self.stderr_handle.close()
                self.stderr_handle = None
            return

        self.renderer_hwnd = 0
        self.attach_timer.start()
        self.log_timer.start()
        self.status_summary.setText("接收端已启动，正在等待渲染窗口挂接到画布。")
        self._set_running_state(True)

    def stop_receiver(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=3)
        self.process = None
        if self.stdout_handle is not None:
            self.stdout_handle.close()
            self.stdout_handle = None
        if self.stderr_handle is not None:
            self.stderr_handle.close()
            self.stderr_handle = None
        self.attach_timer.stop()
        self.log_timer.stop()
        self.renderer_hwnd = 0
        self.status_summary.setText("准备就绪，可以重新启动接收端。")
        self._set_running_state(False)

    def _poll_renderer_window(self) -> None:
        if self.process is None:
            self.attach_timer.stop()
            return
        if self.process.poll() is not None:
            self.attach_timer.stop()
            self.log_timer.stop()
            self._handle_process_finished()
            return
        if self.renderer_hwnd:
            self._resize_embedded_renderer()
            return

        process_id = int(self.process.pid)
        if not process_id:
            return
        hwnd = WindowApi.get_process_window(process_id)
        if not hwnd:
            return

        self.renderer_hwnd = hwnd
        WindowApi.attach_window(
            child_hwnd=hwnd,
            parent_hwnd=int(self.video_surface.winId()),
            rect=self.video_surface.native_target_rect(),
        )
        self.video_surface.placeholder.hide()
        self.status_summary.setText("渲染窗口已挂接，可以在 iPhone 的屏幕镜像里连接。")
        self._append_log("渲染窗口已挂接到宿主画布。")

    def _resize_embedded_renderer(self) -> None:
        if self.renderer_hwnd:
            WindowApi.move_window(self.renderer_hwnd, self.video_surface.native_target_rect())

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._resize_embedded_renderer()

    def _handle_process_finished(self) -> None:
        self.attach_timer.stop()
        self.log_timer.stop()
        self.renderer_hwnd = 0
        self.status_summary.setText("UxPlay 已退出。")
        self._set_running_state(False)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_settings()
        self.stop_receiver()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("UxPlay 桌面投屏")
    app.setFont(QFont("Segoe UI", 10))
    window = UxPlayDesktopWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

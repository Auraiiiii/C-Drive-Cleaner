"""C 盘极速瘦身助手（图形界面，只读扫描版本）。

本程序复用 main.py 中的只读扫描逻辑，仅读取目录和文件元数据。
“一键清理”目前只显示开发中提示，不会删除、移动或修改任何文件。

运行前请先安装 customtkinter：
    python -m pip install customtkinter
"""

from __future__ import annotations

import queue
import threading
import tkinter.messagebox as messagebox
from pathlib import Path
from typing import Any

import customtkinter as ctk

from main import (
    ScanResult,
    display_path,
    format_size,
    get_scan_targets,
    scan_directory,
)


class CleanerApp:
    """构建并管理 C 盘清理助手的主窗口。"""

    # 暖白背景和深青绿色强调色延续《文件整理助手》的极简浅色基调。
    BACKGROUND_COLOR = "#F7F7F5"
    SURFACE_COLOR = "#FFFFFF"
    TEXT_COLOR = "#18181B"
    MUTED_COLOR = "#71717A"
    ACCENT_COLOR = "#0F766E"
    ACCENT_HOVER_COLOR = "#115E59"
    ACCENT_SOFT_COLOR = "#ECFDF5"
    LOG_BACKGROUND = "#1E1E1E"
    LOG_TEXT = "#B9F6CA"
    SUCCESS_COLOR = "#15803D"
    FONT_FAMILY = "Microsoft YaHei UI"

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.message_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.is_scanning = False
        self.has_scan_results = False

        self.root.title("C盘极速瘦身助手")
        self.root.geometry("940x780")
        self.root.minsize(720, 640)
        self.root.configure(fg_color=self.BACKGROUND_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_interface()

    def _build_interface(self) -> None:
        """创建极简单列布局。"""

        main_frame = ctk.CTkFrame(
            self.root,
            fg_color="transparent",
            corner_radius=0,
        )
        main_frame.pack(fill="both", expand=True, padx=48, pady=34)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(5, weight=1)

        header_frame = ctk.CTkFrame(
            main_frame,
            fg_color="transparent",
            corner_radius=0,
        )
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 22))

        title_label = ctk.CTkLabel(
            header_frame,
            text="C盘极速瘦身助手",
            font=ctk.CTkFont(
                family=self.FONT_FAMILY,
                size=30,
                weight="bold",
            ),
            text_color=self.TEXT_COLOR,
            anchor="w",
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="扫描临时文件与下载目录，快速了解 C 盘可释放空间。",
            font=ctk.CTkFont(family=self.FONT_FAMILY, size=13),
            text_color=self.MUTED_COLOR,
            anchor="w",
        )
        subtitle_label.pack(anchor="w", pady=(8, 0))

        target_label = ctk.CTkLabel(
            main_frame,
            text="扫描范围  ·  Windows 临时文件夹  /  用户临时文件夹  /  默认下载文件夹",
            font=ctk.CTkFont(family=self.FONT_FAMILY, size=11),
            text_color=self.MUTED_COLOR,
            anchor="w",
        )
        target_label.grid(row=1, column=0, sticky="w", pady=(0, 16))

        self.scan_button = ctk.CTkButton(
            main_frame,
            text="开始扫描",
            command=self._start_scan,
            height=68,
            corner_radius=18,
            border_width=0,
            fg_color=self.ACCENT_COLOR,
            hover_color=self.ACCENT_HOVER_COLOR,
            text_color="#FFFFFF",
            text_color_disabled="#D1FAE5",
            font=ctk.CTkFont(
                family=self.FONT_FAMILY,
                size=17,
                weight="bold",
            ),
            cursor="hand2",
        )
        self.scan_button.grid(row=2, column=0, sticky="ew")

        log_header = ctk.CTkFrame(
            main_frame,
            fg_color="transparent",
            corner_radius=0,
        )
        log_header.grid(row=3, column=0, sticky="ew", pady=(22, 10))
        log_header.grid_columnconfigure(0, weight=1)

        log_title = ctk.CTkLabel(
            log_header,
            text="扫描日志",
            font=ctk.CTkFont(
                family=self.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color=self.TEXT_COLOR,
            anchor="w",
        )
        log_title.grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(
            log_header,
            text="●  就绪",
            font=ctk.CTkFont(
                family=self.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=self.SUCCESS_COLOR,
            anchor="e",
        )
        self.status_label.grid(row=0, column=1, sticky="e")

        self.log_text = ctk.CTkTextbox(
            main_frame,
            wrap="word",
            corner_radius=18,
            border_width=0,
            border_spacing=18,
            fg_color=self.LOG_BACKGROUND,
            text_color=self.LOG_TEXT,
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569",
            font=ctk.CTkFont(family="Cascadia Mono", size=12),
            activate_scrollbars=True,
            state="disabled",
        )
        self.log_text.grid(row=5, column=0, sticky="nsew")

        self._append_log("准备就绪。点击“开始扫描”查看可释放空间。")
        self._append_log("安全提示：当前版本仅读取文件信息，不会删除任何文件。")

        footer_frame = ctk.CTkFrame(
            main_frame,
            fg_color="transparent",
            corner_radius=0,
        )
        footer_frame.grid(row=6, column=0, sticky="ew", pady=(16, 0))
        footer_frame.grid_columnconfigure(0, weight=1)

        self.total_label = ctk.CTkLabel(
            footer_frame,
            text="等待扫描",
            font=ctk.CTkFont(
                family=self.FONT_FAMILY,
                size=13,
                weight="bold",
            ),
            text_color=self.TEXT_COLOR,
            anchor="w",
        )
        self.total_label.grid(row=0, column=0, sticky="w")

        self.clean_button = ctk.CTkButton(
            footer_frame,
            text="一键清理",
            command=self._show_cleanup_notice,
            width=142,
            height=44,
            corner_radius=13,
            border_width=1,
            border_color="#D4D4D8",
            fg_color="transparent",
            hover_color=self.ACCENT_SOFT_COLOR,
            text_color=self.MUTED_COLOR,
            text_color_disabled="#A1A1AA",
            font=ctk.CTkFont(
                family=self.FONT_FAMILY,
                size=13,
                weight="bold",
            ),
            cursor="arrow",
            state="disabled",
        )
        self.clean_button.grid(row=0, column=1, sticky="e")

        self.scan_button.focus_set()

    def _start_scan(self) -> None:
        """清空旧结果，并在后台线程中启动一次只读扫描。"""

        if self.is_scanning:
            return

        self.is_scanning = True
        self.has_scan_results = False
        self._clear_log()
        self._append_log("开始扫描，请稍候……")
        self._append_log("本次扫描不会修改或删除任何文件。")

        self.scan_button.configure(
            text="正在扫描...",
            state="disabled",
            cursor="arrow",
        )
        self.clean_button.configure(
            state="disabled",
            cursor="arrow",
            border_color="#D4D4D8",
            text_color=self.MUTED_COLOR,
        )
        self.status_label.configure(
            text="●  正在扫描",
            text_color=self.ACCENT_COLOR,
        )
        self.total_label.configure(
            text="共发现 0 B 垃圾",
            text_color=self.TEXT_COLOR,
        )

        worker = threading.Thread(
            target=self._scan_in_background,
            name="c-drive-scan",
            daemon=True,
        )
        worker.start()
        self.root.after(80, self._process_messages)

    def _scan_in_background(self) -> None:
        """在后台执行扫描，通过队列把进度安全地发回界面线程。"""

        total_size = 0
        total_files = 0
        total_skipped = 0

        try:
            targets = get_scan_targets()
            target_count = len(targets)

            for index, (title, root) in enumerate(targets, start=1):
                self.message_queue.put(
                    ("log", f"\n[{index}/{target_count}] 正在扫描：{title}")
                )
                self.message_queue.put(("log", f"路径：{root}"))

                try:
                    result = scan_directory(title, root)
                except Exception as exc:
                    # 单个目录发生异常时继续扫描其他目录，保留部分结果。
                    result = ScanResult(
                        title=title,
                        path=root,
                        scan_error=f"{type(exc).__name__}: {exc}",
                    )

                total_size += result.total_size
                total_files += result.file_count
                total_skipped += result.skipped_count

                for message in self._format_result(result):
                    self.message_queue.put(("log", message))

                self.message_queue.put(
                    (
                        "progress",
                        {
                            "total_size": total_size,
                            "completed": index,
                            "target_count": target_count,
                        },
                    )
                )

            summary = {
                "total_size": total_size,
                "total_files": total_files,
                "total_skipped": total_skipped,
            }
            self.message_queue.put(("complete", summary))
        except Exception as exc:
            self.message_queue.put(
                ("error", f"扫描失败：{type(exc).__name__}: {exc}")
            )

    @staticmethod
    def _format_result(result: ScanResult) -> list[str]:
        """把单个目录的扫描结果转换成适合文本框显示的日志行。"""

        messages = [f"【{result.title}】"]
        if result.scan_error and result.file_count == 0:
            messages.append(f"状态：{result.scan_error}")
        else:
            messages.append(
                f"共占用 {format_size(result.total_size)}"
                f"（{result.file_count:,} 个文件）"
            )

        if result.scan_error and result.file_count > 0:
            messages.append(f"状态：{result.scan_error}")

        if result.largest_files:
            messages.append("最大文件：")
            for index, large_file in enumerate(result.largest_files, start=1):
                relative_path = display_path(large_file.path, result.path)
                messages.append(
                    f"  {index}. {relative_path}"
                    f"（{format_size(large_file.size)}）"
                )
        else:
            messages.append("没有找到超过 10 MB 的可读取文件")

        if result.skipped_count:
            messages.append(
                f"已跳过：{result.skipped_count:,} 个无法读取的条目"
            )

        return messages

    def _process_messages(self) -> None:
        """由 Tk 主线程消费后台消息并更新界面。"""

        try:
            while True:
                message_type, payload = self.message_queue.get_nowait()

                if message_type == "log":
                    self._append_log(str(payload))
                elif message_type == "progress":
                    self.total_label.configure(
                        text=f"共发现 {format_size(payload['total_size'])} 垃圾"
                    )
                elif message_type == "complete":
                    self._finish_scan(payload)
                elif message_type == "error":
                    self._handle_scan_error(str(payload))
        except queue.Empty:
            pass

        # 扫描仍在进行时继续轮询，确保目录完成结果实时出现。
        if self.is_scanning:
            self.root.after(80, self._process_messages)

    def _finish_scan(self, summary: dict[str, int]) -> None:
        """恢复控件状态，展示汇总并点亮清理按钮。"""

        self.is_scanning = False
        self.has_scan_results = True
        total_size = summary["total_size"]

        self._append_log("")
        self._append_log("扫描完成。")
        self._append_log(
            f"共发现 {format_size(total_size)} 垃圾"
            f"（{summary['total_files']:,} 个文件）"
        )
        if summary["total_skipped"]:
            self._append_log(
                f"另有 {summary['total_skipped']:,} 个条目因权限等原因被跳过。"
            )
        self._append_log("安全提示：当前版本不会执行任何清理操作。")

        self.total_label.configure(
            text=f"共发现 {format_size(total_size)} 垃圾",
            text_color=self.TEXT_COLOR,
        )
        self.scan_button.configure(
            text="重新扫描",
            state="normal",
            cursor="hand2",
        )
        self.clean_button.configure(
            state="normal",
            cursor="hand2",
            border_color=self.ACCENT_COLOR,
            text_color=self.ACCENT_COLOR,
        )
        self.status_label.configure(
            text="●  扫描完成",
            text_color=self.SUCCESS_COLOR,
        )

    def _handle_scan_error(self, error_message: str) -> None:
        """意外错误时恢复界面，并避免误开启清理按钮。"""

        self.is_scanning = False
        self._append_log("")
        self._append_log(error_message)
        self.total_label.configure(text="扫描未完成")
        self.scan_button.configure(
            text="重新扫描",
            state="normal",
            cursor="hand2",
        )
        self.clean_button.configure(state="disabled", cursor="arrow")
        self.status_label.configure(
            text="●  扫描失败",
            text_color="#B91C1C",
        )

    def _show_cleanup_notice(self) -> None:
        """安全占位：不执行任何文件操作。"""

        if not self.has_scan_results:
            return
        messagebox.showinfo(
            "功能开发中",
            "清理功能开发中，敬请期待",
            parent=self.root,
        )

    def _append_log(self, message: str) -> None:
        """向只读日志区追加一行文本并自动滚动到底部。"""

        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        """清空上一次扫描留下的日志。"""

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        """关闭窗口；后台守护线程会随进程一并结束。"""

        self.root.destroy()


def main() -> None:
    """设置 Theme 并启动图形界面。"""

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    CleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

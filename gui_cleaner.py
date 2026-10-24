"""C 盘极速瘦身助手（图形界面）。

本程序复用 main.py 中的只读扫描逻辑，并可通过 send2trash 将扫描到的
普通文件移入系统回收站。清理在后台线程中执行，不阻塞 Tk 界面线程。

运行前请先安装依赖：
    python -m pip install -r requirements.txt
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter.messagebox as messagebox
from pathlib import Path
from typing import Any

import customtkinter as ctk
from send2trash import send2trash

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
        self.is_cleaning = False
        self.has_scan_results = False
        self.files_to_clean: list[Path] = []
        self.total_cleanup_size = 0
        self._cleanup_path_keys: set[str] = set()

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
        self._append_log("安全提示：清理操作会把文件移入系统回收站。")

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
            command=self._start_cleanup,
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

        if self.is_scanning or self.is_cleaning:
            return

        self.is_scanning = True
        self.has_scan_results = False
        self._reset_cleanup_results()
        self._clear_log()
        self._append_log("开始扫描，请稍候……")
        self._append_log("扫描不会修改文件；确认清理后会将文件移入回收站。")

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
                    result = scan_directory(
                        title,
                        root,
                        on_file=self._collect_cleanup_file,
                    )
                except Exception as exc:
                    # 单个目录发生异常时继续扫描其他目录，保留部分结果。
                    result = ScanResult(
                        title=title,
                        path=root,
                        scan_error=f"{type(exc).__name__}: {exc}",
                    )

                total_skipped += result.skipped_count

                for message in self._format_result(result):
                    self.message_queue.put(("log", message))

                self.message_queue.put(
                    (
                        "progress",
                        {
                            "total_size": self.total_cleanup_size,
                            "completed": index,
                            "target_count": target_count,
                        },
                    )
                )

            summary = {
                "total_size": self.total_cleanup_size,
                "total_files": len(self.files_to_clean),
                "total_skipped": total_skipped,
            }
            self.message_queue.put(("complete", summary))
        except Exception as exc:
            self.message_queue.put(
                ("error", f"扫描失败：{type(exc).__name__}: {exc}")
            )

    def _collect_cleanup_file(self, file_path: Path, file_size: int) -> None:
        """在后台扫描线程中收集待清理文件，并排除重叠目录的重复项。"""

        path_key = os.path.normcase(os.path.abspath(os.fspath(file_path)))
        if path_key in self._cleanup_path_keys:
            return

        self._cleanup_path_keys.add(path_key)
        self.files_to_clean.append(file_path)
        self.total_cleanup_size += file_size

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
            # 每次只处理有限数量的消息，避免大量文件日志同时占用 UI 线程。
            for _ in range(100):
                try:
                    message_type, payload = self.message_queue.get_nowait()
                except queue.Empty:
                    break

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
                elif message_type == "cleanup_progress":
                    self.status_label.configure(
                        text=(
                            "●  正在清理"
                            f" {payload['completed']}/{payload['total']}"
                        ),
                        text_color=self.ACCENT_COLOR,
                    )
                elif message_type == "cleanup_complete":
                    self._finish_cleanup(payload)
        except Exception as exc:
            self._append_log(f"界面消息处理失败：{type(exc).__name__}: {exc}")

        # 扫描或清理仍在进行时继续轮询，确保后台进度实时出现。
        if self.is_scanning or self.is_cleaning:
            self.root.after(80, self._process_messages)

    def _finish_scan(self, summary: dict[str, int]) -> None:
        """恢复控件状态，展示汇总并点亮清理按钮。"""

        self.is_scanning = False
        self.has_scan_results = summary["total_files"] > 0
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
        self._append_log("安全提示：确认清理后，文件将被移入系统回收站。")

        self.total_label.configure(
            text=f"共发现 {format_size(total_size)} 垃圾",
            text_color=self.TEXT_COLOR,
        )
        self.scan_button.configure(
            text="重新扫描",
            state="normal",
            cursor="hand2",
        )
        if self.has_scan_results:
            self.clean_button.configure(
                state="normal",
                cursor="hand2",
                border_color=self.ACCENT_COLOR,
                text_color=self.ACCENT_COLOR,
            )
        else:
            self.clean_button.configure(
                state="disabled",
                cursor="arrow",
                border_color="#D4D4D8",
                text_color=self.MUTED_COLOR,
            )
        self.status_label.configure(
            text="●  扫描完成",
            text_color=self.SUCCESS_COLOR,
        )

    def _handle_scan_error(self, error_message: str) -> None:
        """意外错误时恢复界面，并避免误开启清理按钮。"""

        self.is_scanning = False
        self._reset_cleanup_results()
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

    def _start_cleanup(self) -> None:
        """确认后创建后台线程，将本次扫描发现的文件移入回收站。"""

        if (
            self.is_scanning
            or self.is_cleaning
            or not self.has_scan_results
        ):
            return

        files_to_clean = tuple(self.files_to_clean)
        if not files_to_clean:
            messagebox.showinfo(
                "没有可清理文件",
                "本次扫描没有发现可清理文件。",
                parent=self.root,
            )
            return

        total_size_gb = self.total_cleanup_size / (1024 ** 3)
        confirmed = messagebox.askyesno(
            "确认清理",
            (
                f"确定要将发现的 {len(files_to_clean)} 个垃圾文件"
                f"（共 {total_size_gb:.2f} GB）移入回收站吗？"
            ),
            icon="warning",
            parent=self.root,
        )
        if not confirmed:
            return

        self.is_cleaning = True
        self.has_scan_results = False
        self._clear_log()
        self._append_log(
            f"开始清理 {len(files_to_clean)} 个文件，正在移入系统回收站……"
        )

        self.scan_button.configure(
            text="正在清理...",
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
            text=f"●  正在清理 0/{len(files_to_clean)}",
            text_color=self.ACCENT_COLOR,
        )

        worker = threading.Thread(
            target=self._cleanup_in_background,
            args=(files_to_clean,),
            name="c-drive-cleanup",
            daemon=True,
        )
        worker.start()
        self.root.after(80, self._process_messages)

    def _cleanup_in_background(self, files_to_clean: tuple[Path, ...]) -> None:
        """遍历文件列表并移入回收站，逐项上报成功或失败结果。"""

        success_count = 0
        failed_count = 0
        total_count = len(files_to_clean)

        for index, file_path in enumerate(files_to_clean, start=1):
            try:
                send2trash(file_path)
            except Exception as e:
                failed_count += 1
                reason = self._describe_cleanup_error(e)
                self.message_queue.put(
                    (
                        "log",
                        f"[跳过] {file_path.name}：{reason}",
                    )
                )
            else:
                success_count += 1
                self.message_queue.put(
                    ("log", f"已清理: {file_path.name}")
                )

            self.message_queue.put(
                (
                    "cleanup_progress",
                    {
                        "completed": index,
                        "total": total_count,
                    },
                )
            )

        self.message_queue.put(
            (
                "cleanup_complete",
                {
                    "success_count": success_count,
                    "failed_count": failed_count,
                },
            )
        )

    @staticmethod
    def _describe_cleanup_error(error: Exception) -> str:
        """把常见文件系统异常转换成用户容易理解的中文原因。"""

        winerror = getattr(error, "winerror", None)
        error_text = str(error).casefold()
        details = f"{type(error).__name__}: {error}"

        if winerror in (32, 33) or any(
            keyword in error_text
            for keyword in (
                "being used by another process",
                "used by another process",
                "sharing violation",
                "另一个程序正在使用",
                "正在使用此文件",
            )
        ):
            return f"文件被占用（{details}）"

        if (
            isinstance(error, PermissionError)
            or winerror == 5
            or "permission denied" in error_text
            or "access is denied" in error_text
            or "拒绝访问" in error_text
        ):
            return f"权限不足（{details}）"

        return f"系统拒绝操作（{details}）"

    def _finish_cleanup(self, summary: dict[str, int]) -> None:
        """提示清理结果，并恢复为尚未扫描的初始界面状态。"""

        self.is_cleaning = False
        success_count = summary["success_count"]

        messagebox.showinfo(
            "清理完成",
            (
                "清理完成！\n\n"
                f"清理成功 {success_count} 个，"
                "部分系统缓存文件因被占用或权限不足跳过（属于正常现象）。"
            ),
            parent=self.root,
        )
        self._reset_after_cleanup()

    def _reset_cleanup_results(self) -> None:
        """清除待清理列表和累计大小。"""

        self.files_to_clean.clear()
        self._cleanup_path_keys.clear()
        self.total_cleanup_size = 0

    def _reset_after_cleanup(self) -> None:
        """清空日志和扫描结果，并禁用“一键清理”按钮。"""

        self.has_scan_results = False
        self._reset_cleanup_results()
        self._clear_log()
        self.total_label.configure(
            text="共发现 0 B 垃圾",
            text_color=self.TEXT_COLOR,
        )
        self.scan_button.configure(
            text="重新扫描",
            state="normal",
            cursor="hand2",
        )
        self.clean_button.configure(
            state="disabled",
            cursor="arrow",
            border_color="#D4D4D8",
            text_color=self.MUTED_COLOR,
        )
        self.status_label.configure(
            text="●  就绪",
            text_color=self.SUCCESS_COLOR,
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
    try:
        root.iconbitmap("app_icon.ico")
    except Exception:
        pass
    CleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

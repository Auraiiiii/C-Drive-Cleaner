"""Windows C 盘空间扫描器（只读版本）。

本程序只读取目录和文件的大小信息，不会创建、移动、修改或删除任何文件。
扫描结果只包含当前账号有权限读取的内容；无权限的目录或文件会被跳过。
"""

from __future__ import annotations

import heapq
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple


# 10 MB 按二进制单位计算，即 10 * 1024 * 1024 字节。
MIN_LARGE_FILE_SIZE = 10 * 1024 * 1024

# 每个目录最多展示 5 个大文件。
TOP_FILE_COUNT = 5


@dataclass(frozen=True)
class LargeFile:
    """保存一个大文件的绝对路径和字节数。"""

    path: Path
    size: int


@dataclass
class ScanResult:
    """保存一个目录的扫描结果。"""

    title: str
    path: Path
    total_size: int = 0
    file_count: int = 0
    skipped_count: int = 0
    largest_files: List[LargeFile] = field(default_factory=list)
    scan_error: Optional[str] = None


def format_size(size_in_bytes: int) -> str:
    """把字节数转换成便于阅读的 KB、MB、GB 等单位。"""

    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"

    size = float(size_in_bytes)
    units = ("KB", "MB", "GB", "TB", "PB")

    for unit in units:
        size /= 1024
        if size < 1024 or unit == units[-1]:
            # 小于 10 时保留两位小数；较大数值保留一位，报告更紧凑。
            if size < 10:
                return f"{size:.2f} {unit}"
            if size < 100:
                return f"{size:.1f} {unit}"
            return f"{size:.0f} {unit}"

    # 正常情况下循环中一定会返回；这里作为极端情况的保底处理。
    return f"{size_in_bytes} B"


def get_scan_targets() -> List[Tuple[str, Path]]:
    """返回需要扫描的三个目录。

    Windows 临时目录优先使用系统的 %SystemRoot% 环境变量，找不到时使用
    C:\\Windows\\Temp。用户临时目录优先使用 %TEMP%，同时提供 AppData\\Local\\Temp
    作为后备。下载目录按需求使用当前用户的 ~/Downloads。
    """

    windows_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    windows_temp = windows_root / "Temp"

    user_temp_value = os.environ.get("TEMP") or os.environ.get("TMP")
    if user_temp_value:
        user_temp = Path(user_temp_value)
    else:
        local_app_data = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home() / "AppData" / "Local"),
            )
        )
        user_temp = local_app_data / "Temp"

    downloads = Path.home() / "Downloads"

    return [
        ("Windows 临时文件夹", windows_temp),
        ("用户临时文件夹", user_temp),
        ("默认下载文件夹", downloads),
    ]


def scan_directory(
    title: str,
    root: Path,
    on_file: Optional[Callable[[Path, int], None]] = None,
) -> ScanResult:
    """只读扫描目录，并返回总大小、文件数和大文件列表。

    这里使用 os.walk 逐层遍历目录，并明确关闭对符号链接目录的跟随，避免
    链接造成重复统计或目录循环。任何无法访问的条目都只会增加跳过计数，
    不会让整个扫描任务中断。调用方可以通过 on_file 接收每个普通文件的
    路径和大小，用于后续需要逐文件处理的场景。
    """

    result = ScanResult(title=title, path=root)

    # Path.is_dir() 本身也可能因路径无效或权限问题抛出异常。
    try:
        if not root.is_dir():
            result.scan_error = "目录不存在，或当前账号无法访问"
            return result
    except (OSError, ValueError) as exc:
        result.scan_error = f"{type(exc).__name__}: {exc}"
        return result

    # 使用最小堆只保存最大的 5 个候选文件，避免为超大目录保存全部文件列表。
    # 元组中的第二项是路径字符串，用于在文件大小相同时保持稳定比较。
    largest_heap: List[Tuple[int, str]] = []

    def handle_walk_error(error: OSError) -> None:
        """接收 os.walk 无法进入某个子目录时产生的错误。"""

        # os.walk 的 onerror 回调应吞掉错误；仅记录跳过数量供报告展示。
        result.skipped_count += 1

    try:
        for current_directory, directory_names, file_names in os.walk(
            root,
            topdown=True,
            onerror=handle_walk_error,
            followlinks=False,
        ):
            # 显式过滤符号链接目录，进一步防止循环和重复统计。
            try:
                directory_names[:] = [
                    name
                    for name in directory_names
                    if not os.path.islink(
                        os.path.join(current_directory, name)
                    )
                ]
            except OSError:
                # 列表推导本身出错时，至少保留目录列表，后续遍历仍可继续。
                result.skipped_count += 1

            for file_name in file_names:
                file_path = Path(current_directory) / file_name

                try:
                    # follow_symlinks=False 只统计链接自身的大小，不重复统计
                    # 链接目标；同时不要求读取文件内容，只需要元数据。
                    file_info = os.stat(file_path, follow_symlinks=False)
                except (OSError, ValueError):
                    # 权限不足、文件刚刚被删除、路径无效等情况直接跳过。
                    result.skipped_count += 1
                    continue

                # 只统计普通文件。目录、设备文件、符号链接等不计入目录占用。
                if not stat.S_ISREG(file_info.st_mode):
                    continue

                file_size = file_info.st_size
                result.total_size += file_size
                result.file_count += 1

                if on_file is not None:
                    on_file(file_path, file_size)

                # “超过 10MB”按严格大于处理；恰好 10MB 的文件不会入选。
                if file_size <= MIN_LARGE_FILE_SIZE:
                    continue

                candidate = (file_size, str(file_path))
                if len(largest_heap) < TOP_FILE_COUNT:
                    heapq.heappush(largest_heap, candidate)
                elif candidate[0] > largest_heap[0][0]:
                    heapq.heapreplace(largest_heap, candidate)
    except (OSError, ValueError) as exc:
        # 兜底捕获遍历期间出现的目录级错误，保留已经统计到的部分结果。
        result.skipped_count += 1
        result.scan_error = f"扫描提前结束：{type(exc).__name__}: {exc}"

    # 最小堆只能保证堆顶最小；转为普通列表后按大小从大到小排列。
    result.largest_files = [
        LargeFile(path=Path(path_text), size=size)
        for size, path_text in sorted(
            largest_heap,
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )
    ]
    return result


def display_path(path: Path, root: Path) -> str:
    """优先显示相对路径，让报告中嵌套文件的来源更清楚。"""

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def print_report(results: List[ScanResult]) -> None:
    """在控制台打印最终扫描报告。"""

    total_size = sum(result.total_size for result in results)
    total_files = sum(result.file_count for result in results)
    total_skipped = sum(result.skipped_count for result in results)

    print("=" * 72)
    print("C 盘空间扫描报告（只读模式：不会删除任何文件）")
    print("=" * 72)
    print("说明：大小为文件逻辑大小；无法读取的目录和文件会被跳过。")
    print()

    for result in results:
        print(f"【{result.title}】")
        print(f"  路径：{result.path}")

        if result.scan_error and result.file_count == 0:
            print(f"  状态：{result.scan_error}")
        else:
            print(
                f"  共占用 {format_size(result.total_size)}"
                f"（{result.file_count:,} 个文件）"
            )

        if result.scan_error and result.file_count > 0:
            print(f"  状态：{result.scan_error}")

        if result.largest_files:
            print("  最大文件（超过 10 MB，最多显示 5 个）：")
            for index, large_file in enumerate(result.largest_files, start=1):
                relative_path = display_path(large_file.path, result.path)
                print(
                    f"    {index}. {relative_path}"
                    f"（{format_size(large_file.size)}）"
                )
        else:
            print("  最大文件：没有找到超过 10 MB 的可读取文件")

        if result.skipped_count:
            print(f"  已跳过：{result.skipped_count:,} 个无法读取的条目")

        print()

    print("-" * 72)
    print(
        f"【合计】三个目录的可读取文件共占用 {format_size(total_size)}"
        f"（{total_files:,} 个文件）"
    )
    if total_skipped:
        print(
            f"【提示】扫描期间共跳过 {total_skipped:,} 个无法读取的条目，"
            "因此实际占用可能略高于本报告 "
        )
    else:
        print("【提示】本次扫描没有遇到无法读取的条目")
    print("=" * 72)


def main() -> None:
    """创建扫描任务并逐个执行。"""

    results: List[ScanResult] = []

    for title, root in get_scan_targets():
        try:
            result = scan_directory(title, root)
        except Exception as exc:
            # 每个目录相互隔离：即使某个目录出现极端错误，其余目录仍会扫描。
            result = ScanResult(
                title=title,
                path=root,
                scan_error=f"{type(exc).__name__}: {exc}",
            )
        results.append(result)

    print_report(results)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 用户可以随时按 Ctrl+C 终止扫描；这里只做温和退出，不修改任何文件。
        print("\n扫描已取消。")
        sys.exit(130)

"""使用 Tkinter Canvas 绘制并导出“C盘极速瘦身助手”图标。

脚本不依赖 Pillow：
1. 在原生 Tk Canvas 上绘制 512x512 的图标；
2. 通过 Windows GDI 获取 Canvas 的真实像素；
3. 使用标准库生成 PNG 数据，并按 ICO 格式打包为多尺寸文件。

运行：
    python create_icon.py

输出：
    app_icon.ico（16、32、48、64、128、256 像素）
"""

from __future__ import annotations

import ctypes
import math
import struct
import sys
import time
import zlib
from ctypes import wintypes
from pathlib import Path
from typing import Iterable

import tkinter as tk


RENDER_SIZE = 512
ICON_SIZES = (16, 32, 48, 64, 128, 256)
OUTPUT_PATH = Path(__file__).resolve().with_name("app_icon.ico")

COLOR_BACKGROUND_TOP = "#06152D"
COLOR_BACKGROUND_BOTTOM = "#0A2948"
COLOR_DEEP_BLUE = "#071D35"
COLOR_PANEL_BLUE = "#0A3153"
COLOR_CYAN = "#22D3EE"
COLOR_PALE_CYAN = "#DDFBFF"
COLOR_GREEN = "#10B981"
COLOR_LIME = "#A3E635"
COLOR_PALE_GREEN = "#D9F99D"


def _mix_color(first: str, second: str, amount: float) -> str:
    """在两个十六进制颜色之间做线性插值。"""

    amount = max(0.0, min(1.0, amount))
    rgb_first = tuple(
        int(first[index : index + 2], 16) for index in (1, 3, 5)
    )
    rgb_second = tuple(
        int(second[index : index + 2], 16) for index in (1, 3, 5)
    )
    mixed = tuple(
        round(start + (end - start) * amount)
        for start, end in zip(rgb_first, rgb_second)
    )
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def _rounded_points(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
) -> list[float]:
    """生成适合 Canvas 平滑多边形的圆角矩形顶点。"""

    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    return [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]


def _draw_rounded_rectangle(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    **options: object,
) -> int:
    """用原生 Canvas 多边形绘制圆角矩形。"""

    return canvas.create_polygon(
        _rounded_points(x1, y1, x2, y2, radius),
        smooth=True,
        splinesteps=32,
        **options,
    )


def _draw_star(
    canvas: tk.Canvas,
    center_x: float,
    center_y: float,
    radius: float,
    fill: str,
    outline: str = "",
) -> None:
    """绘制带四个尖角的清洁星芒。"""

    inner = radius * 0.22
    points = (
        center_x,
        center_y - radius,
        center_x + inner,
        center_y - inner,
        center_x + radius,
        center_y,
        center_x + inner,
        center_y + inner,
        center_x,
        center_y + radius,
        center_x - inner,
        center_y + inner,
        center_x - radius,
        center_y,
        center_x - inner,
        center_y - inner,
    )
    canvas.create_polygon(
        points,
        fill=fill,
        outline=outline,
        width=2 if outline else 0,
        joinstyle="round",
    )


def _ellipse_arc_points(
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    start_degrees: float,
    extent_degrees: float,
    step_degrees: float = 6.0,
) -> list[float]:
    """沿椭圆采样弧线，返回 Canvas 折线所需的交错坐标。"""

    count = max(2, math.ceil(abs(extent_degrees) / step_degrees))
    points: list[float] = []
    for index in range(count + 1):
        angle = math.radians(
            start_degrees + extent_degrees * index / count
        )
        points.extend(
            (
                center_x + radius_x * math.cos(angle),
                center_y + radius_y * math.sin(angle),
            )
        )
    return points


def _draw_c_stroke(canvas: tk.Canvas) -> int:
    """用粗弧线绘制醒目的字母 C，避免依赖特定字体。"""

    points = _ellipse_arc_points(205, 245, 103, 103, 43, 274, 4)
    canvas.create_line(
        *points,
        fill="#073A50",
        width=68,
        smooth=True,
        capstyle="round",
        joinstyle="round",
    )
    canvas.create_line(
        *points,
        fill="#0891B2",
        width=53,
        smooth=True,
        capstyle="round",
        joinstyle="round",
    )
    canvas.create_line(
        *points,
        fill="#ECFEFF",
        width=31,
        smooth=True,
        capstyle="round",
        joinstyle="round",
    )
    return len(points)


def _draw_broom(canvas: tk.Canvas) -> None:
    """绘制斜向魔法扫帚，使用青色杆身与绿色刷毛。"""

    # 先画扫帚在空气中划过的轨迹，让它位于主体后方。
    canvas.create_arc(
        93,
        56,
        476,
        426,
        start=308,
        extent=72,
        style="arc",
        outline="#155E75",
        width=7,
        dash=(14, 11),
    )

    # 扫帚杆的深色轮廓、青色主体和亮色反光。
    handle_start = (397, 69)
    handle_end = (291, 304)
    canvas.create_line(
        *handle_start,
        *handle_end,
        fill="#020B17",
        width=29,
        capstyle="round",
    )
    canvas.create_line(
        *handle_start,
        *handle_end,
        fill=COLOR_CYAN,
        width=16,
        capstyle="round",
    )
    canvas.create_line(
        handle_start[0] - 2,
        handle_start[1] + 1,
        handle_end[0] - 2,
        handle_end[1] - 1,
        fill=COLOR_PALE_CYAN,
        width=4,
        capstyle="round",
    )

    # 金属箍连接杆身与扫帚头。
    canvas.create_polygon(
        260,
        287,
        294,
        278,
        323,
        319,
        289,
        340,
        fill="#052E2B",
        outline=COLOR_CYAN,
        width=6,
        joinstyle="round",
    )
    canvas.create_line(
        272,
        294,
        300,
        327,
        fill=COLOR_LIME,
        width=7,
        capstyle="round",
    )

    # 向下展开的绿色刷毛。
    canvas.create_polygon(
        258,
        302,
        329,
        324,
        370,
        369,
        359,
        423,
        308,
        452,
        244,
        430,
        214,
        381,
        fill="#086A52",
        outline=COLOR_GREEN,
        width=9,
        joinstyle="round",
    )
    canvas.create_polygon(
        269,
        319,
        319,
        334,
        352,
        370,
        342,
        410,
        305,
        431,
        257,
        413,
        234,
        378,
        fill="#0D7A5A",
        outline="",
    )

    bristle_colors = (
        COLOR_LIME,
        COLOR_CYAN,
        COLOR_PALE_GREEN,
        COLOR_GREEN,
        COLOR_CYAN,
        COLOR_LIME,
    )
    bristle_starts = (
        (279, 318),
        (292, 322),
        (305, 326),
        (318, 330),
        (279, 318),
        (305, 326),
    )
    bristle_ends = (
        (237, 404),
        (255, 424),
        (277, 434),
        (311, 430),
        (343, 404),
        (349, 374),
    )
    for start, end, color in zip(
        bristle_starts,
        bristle_ends,
        bristle_colors,
    ):
        canvas.create_line(
            *start,
            *end,
            fill=color,
            width=6,
            capstyle="round",
        )

    # 扫帚头底部和上沿的高光，增强 32px 下的辨识度。
    canvas.create_line(
        229,
        347,
        269,
        309,
        fill=COLOR_PALE_CYAN,
        width=5,
        capstyle="round",
    )
    canvas.create_line(
        239,
        423,
        309,
        442,
        fill=COLOR_PALE_GREEN,
        width=6,
        capstyle="round",
    )


def draw_icon(canvas: tk.Canvas) -> None:
    """在 Canvas 上绘制完整的科技风清理图标。"""

    size = RENDER_SIZE
    canvas.delete("all")
    canvas.configure(bg=COLOR_BACKGROUND_TOP)

    # 深蓝渐变由细横条拼成，避免依赖渐变图像或 Pillow。
    strip_count = 96
    strip_height = size / strip_count
    for index in range(strip_count):
        amount = index / max(1, strip_count - 1)
        color = _mix_color(
            COLOR_BACKGROUND_TOP,
            COLOR_BACKGROUND_BOTTOM,
            amount,
        )
        y1 = round(index * strip_height)
        y2 = round((index + 1) * strip_height + 1)
        canvas.create_rectangle(
            0,
            y1,
            size,
            y2,
            fill=color,
            outline=color,
        )

    # 极淡的网格给背景增加一点“磁盘数据”氛围。
    for offset in range(32, size, 48):
        canvas.create_line(
            offset,
            0,
            offset,
            size,
            fill="#0C3152",
            width=1,
        )
        canvas.create_line(
            0,
            offset,
            size,
            offset,
            fill="#0C3152",
            width=1,
        )

    # C 盘圆形主体外围的多层青色光晕。
    glow_layers = (
        (25, 69, 385, 429, "#09233E", 42),
        (38, 82, 372, 416, "#0A3355", 30),
        (51, 95, 359, 403, "#0B5874", 17),
    )
    for x1, y1, x2, y2, color, width in glow_layers:
        canvas.create_oval(
            x1,
            y1,
            x2,
            y2,
            outline=color,
            width=width,
        )

    # 主盘体、内圈和两道科技轨道。
    canvas.create_oval(
        62,
        106,
        348,
        392,
        fill=COLOR_DEEP_BLUE,
        outline=COLOR_CYAN,
        width=11,
    )
    canvas.create_oval(
        80,
        124,
        330,
        374,
        fill=COLOR_PANEL_BLUE,
        outline="#38BDF8",
        width=3,
    )
    canvas.create_oval(
        96,
        140,
        314,
        358,
        outline="#155E75",
        width=4,
    )
    canvas.create_arc(
        96,
        140,
        314,
        358,
        start=205,
        extent=118,
        style="arc",
        outline="#67E8F9",
        width=7,
    )
    canvas.create_arc(
        112,
        156,
        298,
        342,
        start=23,
        extent=92,
        style="arc",
        outline=COLOR_GREEN,
        width=5,
    )

    _draw_c_stroke(canvas)

    # 盘体底部的数据条与绿色状态灯。
    _draw_rounded_rectangle(
        canvas,
        143,
        326,
        274,
        344,
        9,
        fill="#031B2E",
        outline="#0E7490",
        width=2,
    )
    _draw_rounded_rectangle(
        canvas,
        151,
        332,
        229,
        338,
        3,
        fill=COLOR_CYAN,
        outline="",
    )
    canvas.create_oval(
        272,
        325,
        294,
        347,
        fill="#052E26",
        outline=COLOR_GREEN,
        width=4,
    )
    canvas.create_oval(
        278,
        331,
        288,
        341,
        fill=COLOR_PALE_GREEN,
        outline="",
    )

    _draw_broom(canvas)

    # 清洁星芒与沿轨迹散落的数据粒子。
    canvas.create_oval(
        386,
        57,
        458,
        129,
        fill="#083D38",
        outline="",
    )
    _draw_star(canvas, 421, 92, 35, COLOR_PALE_GREEN, COLOR_GREEN)
    _draw_star(canvas, 353, 56, 16, COLOR_PALE_CYAN)
    _draw_star(canvas, 459, 164, 13, COLOR_LIME)
    _draw_star(canvas, 374, 236, 9, COLOR_CYAN)

    for center_x, center_y, radius, color in (
        (433, 221, 5, COLOR_CYAN),
        (405, 265, 4, COLOR_PALE_GREEN),
        (447, 283, 3, COLOR_GREEN),
        (382, 308, 4, COLOR_CYAN),
        (344, 468, 4, COLOR_LIME),
        (224, 459, 3, COLOR_CYAN),
    ):
        canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            fill=color,
            outline="",
        )

    # 黑色外框让图标在浅色和深色桌面都能保持清楚。
    canvas.create_rectangle(
        1,
        1,
        size - 2,
        size - 2,
        outline="#020817",
        width=2,
    )


class _RECT(ctypes.Structure):
    _fields_ = (
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    )


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = (
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    )


class _LOGBRUSH(ctypes.Structure):
    _fields_ = (
        ("lbStyle", wintypes.UINT),
        ("lbColor", wintypes.DWORD),
        ("lbHatch", ctypes.c_size_t),
    )


def _smooth_closed_points(
    coordinates: list[float],
    iterations: int = 2,
) -> list[float]:
    """用 Chaikin 细分近似 Canvas 的 smooth 多边形。"""

    points = [
        (coordinates[index], coordinates[index + 1])
        for index in range(0, len(coordinates), 2)
    ]
    if points and points[0] == points[-1]:
        points.pop()

    deduplicated = []
    for point in points:
        if not deduplicated or point != deduplicated[-1]:
            deduplicated.append(point)
    points = deduplicated

    for _ in range(iterations):
        if len(points) < 3:
            break
        refined: list[tuple[float, float]] = []
        for index, current in enumerate(points):
            following = points[(index + 1) % len(points)]
            refined.append(
                (
                    current[0] * 0.75 + following[0] * 0.25,
                    current[1] * 0.75 + following[1] * 0.25,
                )
            )
            refined.append(
                (
                    current[0] * 0.25 + following[0] * 0.75,
                    current[1] * 0.25 + following[1] * 0.75,
                )
            )
        points = refined

    result: list[float] = []
    for x, y in points:
        result.extend((x, y))
    return result


class _GdiCanvas:
    """与 Canvas 绘图接口兼容的离屏 GDI 画布。

    它只用于屏幕捕获不可用的环境。所有图形仍由 draw_icon 中的同一组
    Canvas 指令生成，不引入图像库或磁盘中间文件。
    """

    def __init__(self, logical_size: int, scale: int = 3) -> None:
        if sys.platform != "win32":
            raise RuntimeError("离屏 GDI 画布仅支持 Windows。")

        self.logical_size = logical_size
        self.scale = scale
        self.width = logical_size * scale
        self.height = logical_size * scale
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

        hwnd_type = wintypes.HWND
        hdc_type = wintypes.HDC
        hbitmap_type = wintypes.HBITMAP
        hgdiobj_type = wintypes.HGDIOBJ

        self.user32.GetDC.argtypes = (hwnd_type,)
        self.user32.GetDC.restype = hdc_type
        self.user32.ReleaseDC.argtypes = (hwnd_type, hdc_type)
        self.user32.ReleaseDC.restype = ctypes.c_int

        self.gdi32.CreateCompatibleDC.argtypes = (hdc_type,)
        self.gdi32.CreateCompatibleDC.restype = hdc_type
        self.gdi32.CreateDIBSection.argtypes = (
            hdc_type,
            ctypes.POINTER(_BITMAPINFOHEADER),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        )
        self.gdi32.CreateDIBSection.restype = hbitmap_type
        self.gdi32.SelectObject.argtypes = (hdc_type, hgdiobj_type)
        self.gdi32.SelectObject.restype = hgdiobj_type
        self.gdi32.DeleteObject.argtypes = (hgdiobj_type,)
        self.gdi32.DeleteObject.restype = wintypes.BOOL
        self.gdi32.DeleteDC.argtypes = (hdc_type,)
        self.gdi32.DeleteDC.restype = wintypes.BOOL
        self.gdi32.GetStockObject.argtypes = (ctypes.c_int,)
        self.gdi32.GetStockObject.restype = hgdiobj_type
        self.gdi32.CreateSolidBrush.argtypes = (wintypes.DWORD,)
        self.gdi32.CreateSolidBrush.restype = hgdiobj_type
        self.gdi32.ExtCreatePen.argtypes = (
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_LOGBRUSH),
            wintypes.DWORD,
            ctypes.c_void_p,
        )
        self.gdi32.ExtCreatePen.restype = hgdiobj_type
        self.gdi32.SetPolyFillMode.argtypes = (hdc_type, ctypes.c_int)
        self.gdi32.SetPolyFillMode.restype = ctypes.c_int
        self.gdi32.Rectangle.argtypes = (
            hdc_type,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        )
        self.gdi32.Rectangle.restype = wintypes.BOOL
        self.gdi32.Ellipse.argtypes = self.gdi32.Rectangle.argtypes
        self.gdi32.Ellipse.restype = wintypes.BOOL
        self.gdi32.Polygon.argtypes = (
            hdc_type,
            ctypes.POINTER(wintypes.POINT),
            ctypes.c_int,
        )
        self.gdi32.Polygon.restype = wintypes.BOOL
        self.gdi32.Polyline.argtypes = self.gdi32.Polygon.argtypes
        self.gdi32.Polyline.restype = wintypes.BOOL
        self.gdi32.GdiFlush.argtypes = ()
        self.gdi32.GdiFlush.restype = wintypes.BOOL

        self.screen_dc = self.user32.GetDC(None)
        if not self.screen_dc:
            raise ctypes.WinError(ctypes.get_last_error())
        self.memory_dc = self.gdi32.CreateCompatibleDC(self.screen_dc)
        if not self.memory_dc:
            self.user32.ReleaseDC(None, self.screen_dc)
            raise ctypes.WinError(ctypes.get_last_error())

        header = _BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = self.width
        header.biHeight = -self.height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0
        bits_pointer = ctypes.c_void_p()
        self.bitmap = self.gdi32.CreateDIBSection(
            self.memory_dc,
            ctypes.byref(header),
            0,
            ctypes.byref(bits_pointer),
            None,
            0,
        )
        if not self.bitmap or not bits_pointer.value:
            self.gdi32.DeleteDC(self.memory_dc)
            self.user32.ReleaseDC(None, self.screen_dc)
            raise ctypes.WinError(ctypes.get_last_error())

        self.bits_pointer = bits_pointer
        self.previous_bitmap = self.gdi32.SelectObject(
            self.memory_dc,
            self.bitmap,
        )
        self.gdi32.SetPolyFillMode(self.memory_dc, 2)  # WINDING

    @staticmethod
    def _colorref(color: str) -> int:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        return red | (green << 8) | (blue << 16)

    def _scaled_point_array(
        self,
        coordinates: Iterable[float],
    ) -> ctypes.Array[wintypes.POINT]:
        values = list(coordinates)
        point_count = len(values) // 2
        points = (wintypes.POINT * point_count)()
        for index in range(point_count):
            points[index].x = round(values[index * 2] * self.scale)
            points[index].y = round(values[index * 2 + 1] * self.scale)
        return points

    @staticmethod
    def _flatten_coordinates(
        coordinates: tuple[float | Iterable[float], ...],
    ) -> list[float]:
        """兼容 Tk 将坐标列表作为单个参数传入的写法。"""

        if (
            len(coordinates) == 1
            and not isinstance(coordinates[0], (int, float))
        ):
            return [float(value) for value in coordinates[0]]
        return [float(value) for value in coordinates]

    def _draw_with_objects(
        self,
        fill: str | None,
        outline: str | None,
        width: float,
        drawing_function: object,
    ) -> None:
        """选择画刷和画笔后执行一个 GDI 绘制函数。"""

        brush = (
            self.gdi32.CreateSolidBrush(self._colorref(fill))
            if fill
            else self.gdi32.GetStockObject(5)  # NULL_BRUSH
        )
        if outline and width > 0:
            log_brush = _LOGBRUSH(
                0,  # BS_SOLID
                self._colorref(outline),
                0,
            )
            pen = self.gdi32.ExtCreatePen(
                0x00010000,  # PS_GEOMETRIC | PS_ENDCAP_ROUND | PS_JOIN_ROUND
                max(1, round(width * self.scale)),
                ctypes.byref(log_brush),
                0,
                None,
            )
        else:
            pen = self.gdi32.GetStockObject(8)  # NULL_PEN

        old_brush = self.gdi32.SelectObject(self.memory_dc, brush)
        old_pen = self.gdi32.SelectObject(self.memory_dc, pen)
        try:
            drawing_function()
        finally:
            self.gdi32.SelectObject(self.memory_dc, old_brush)
            self.gdi32.SelectObject(self.memory_dc, old_pen)
            # 只有自建对象需要删除，stock 对象由 GDI 管理。
            if fill:
                self.gdi32.DeleteObject(brush)
            if outline and width > 0:
                self.gdi32.DeleteObject(pen)

    def create_rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        **options: object,
    ) -> None:
        fill = options.get("fill")
        outline = options.get("outline")
        width = float(options.get("width", 1))
        self._draw_with_objects(
            str(fill) if fill else None,
            str(outline) if outline else None,
            width,
            lambda: self.gdi32.Rectangle(
                self.memory_dc,
                round(x1 * self.scale),
                round(y1 * self.scale),
                round(x2 * self.scale),
                round(y2 * self.scale),
            ),
        )

    def create_oval(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        **options: object,
    ) -> None:
        fill = options.get("fill")
        outline = options.get("outline")
        width = float(options.get("width", 1))
        self._draw_with_objects(
            str(fill) if fill else None,
            str(outline) if outline else None,
            width,
            lambda: self.gdi32.Ellipse(
                self.memory_dc,
                round(x1 * self.scale),
                round(y1 * self.scale),
                round(x2 * self.scale),
                round(y2 * self.scale),
            ),
        )

    def create_polygon(self, *coordinates: float, **options: object) -> None:
        values = self._flatten_coordinates(coordinates)
        if options.get("smooth"):
            values = _smooth_closed_points(values, iterations=2)
        fill = options.get("fill")
        outline = options.get("outline")
        width = float(options.get("width", 1))
        point_array = self._scaled_point_array(values)
        self._draw_with_objects(
            str(fill) if fill else None,
            str(outline) if outline else None,
            width,
            lambda: self.gdi32.Polygon(
                self.memory_dc,
                point_array,
                len(values) // 2,
            ),
        )

    def create_line(self, *coordinates: float, **options: object) -> None:
        values = self._flatten_coordinates(coordinates)
        if len(values) < 4:
            return
        fill = str(options.get("fill", "#000000"))
        width = float(options.get("width", 1))
        point_array = self._scaled_point_array(values)
        self._draw_with_objects(
            None,
            fill,
            width,
            lambda: self.gdi32.Polyline(
                self.memory_dc,
                point_array,
                len(values) // 2,
            ),
        )

    def create_arc(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        **options: object,
    ) -> None:
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        radius_x = (x2 - x1) / 2
        radius_y = (y2 - y1) / 2
        points = _ellipse_arc_points(
            center_x,
            center_y,
            radius_x,
            radius_y,
            float(options.get("start", 0)),
            float(options.get("extent", 90)),
            5,
        )

        if options.get("dash"):
            # 每 8 个采样点绘制 5 个，近似 Canvas 的短划线。
            for index in range(0, len(points) - 4, 16):
                chunk = points[index : min(index + 10, len(points))]
                self.create_line(
                    *chunk,
                    fill=options.get("outline", "#000000"),
                    width=options.get("width", 1),
                )
        else:
            self.create_line(
                *points,
                fill=options.get("outline", "#000000"),
                width=options.get("width", 1),
            )

    def delete(self, _item: str) -> None:
        """清除 DIB 画布。"""

        ctypes.memset(self.bits_pointer, 0, self.width * self.height * 4)

    def configure(self, **_options: object) -> None:
        """兼容 Canvas.configure；离屏画布无需额外设置。"""

    def to_rgba(self) -> bytes:
        """返回离屏 DIB 的 RGB 顺序为 RGBA 的像素。"""

        self.gdi32.GdiFlush()
        pixels = bytearray(
            ctypes.string_at(
                self.bits_pointer,
                self.width * self.height * 4,
            )
        )
        pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]
        return bytes(pixels)

    def close(self) -> None:
        """释放 GDI 和 DIB 资源。"""

        self.gdi32.SelectObject(self.memory_dc, self.previous_bitmap)
        self.gdi32.DeleteObject(self.bitmap)
        self.gdi32.DeleteDC(self.memory_dc)
        self.user32.ReleaseDC(None, self.screen_dc)


def _capture_canvas(
    canvas: tk.Canvas,
    width: int,
    height: int,
    copy_from_screen: bool = False,
) -> bytes:
    """通过 Windows GDI 获取 Canvas 像素，返回 RGBA 字节。"""

    if sys.platform != "win32":
        raise RuntimeError(
            "当前脚本依赖 Windows GDI 捕获 Tk Canvas，请在 Windows 上运行。"
        )

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    hwnd_type = wintypes.HWND
    hdc_type = wintypes.HDC
    hbitmap_type = wintypes.HBITMAP
    hgdiobj_type = wintypes.HGDIOBJ

    user32.GetDC.argtypes = (hwnd_type,)
    user32.GetDC.restype = hdc_type
    user32.ReleaseDC.argtypes = (hwnd_type, hdc_type)
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = (hwnd_type, hdc_type, wintypes.UINT)
    user32.PrintWindow.restype = wintypes.BOOL
    user32.GetAncestor.argtypes = (hwnd_type, wintypes.UINT)
    user32.GetAncestor.restype = hwnd_type
    user32.RedrawWindow.argtypes = (
        hwnd_type,
        ctypes.c_void_p,
        wintypes.HRGN,
        wintypes.UINT,
    )
    user32.RedrawWindow.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = (hdc_type,)
    gdi32.CreateCompatibleDC.restype = hdc_type
    gdi32.CreateCompatibleBitmap.argtypes = (
        hdc_type,
        ctypes.c_int,
        ctypes.c_int,
    )
    gdi32.CreateCompatibleBitmap.restype = hbitmap_type
    gdi32.SelectObject.argtypes = (hdc_type, hgdiobj_type)
    gdi32.SelectObject.restype = hgdiobj_type
    gdi32.GetDIBits.argtypes = (
        hdc_type,
        hbitmap_type,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(_BITMAPINFOHEADER),
        wintypes.UINT,
    )
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.BitBlt.argtypes = (
        hdc_type,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        hdc_type,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.DWORD,
    )
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.DeleteObject.argtypes = (hgdiobj_type,)
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = (hdc_type,)
    gdi32.DeleteDC.restype = wintypes.BOOL

    # 部分显示驱动不会给 Tk 的 Canvas 子窗口返回 WM_PRINT 内容；
    # 捕获顶层无边框窗口的客户区具有更好的兼容性。
    canvas_hwnd = canvas.winfo_id()
    hwnd = user32.GetAncestor(canvas_hwnd, 2) or canvas_hwnd  # GA_ROOT
    window_dc = user32.GetDC(hwnd)
    if not window_dc:
        raise ctypes.WinError(ctypes.get_last_error())

    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    if not memory_dc or not bitmap:
        if memory_dc:
            gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)
        raise ctypes.WinError(ctypes.get_last_error())

    previous_object = gdi32.SelectObject(memory_dc, bitmap)
    try:
        user32.RedrawWindow(
            hwnd,
            None,
            None,
            0x0001 | 0x0004 | 0x0100,  # INVALIDATE | UPDATENOW | ALLCHILDREN
        )
        canvas.update_idletasks()
        if copy_from_screen:
            # SRCCOPY | CAPTUREBLT：读取窗口当前在桌面上的真实像素。
            if not gdi32.BitBlt(
                memory_dc,
                0,
                0,
                width,
                height,
                window_dc,
                0,
                0,
                0x00CC0020 | 0x40000000,
            ):
                raise RuntimeError("Windows 无法从屏幕读取 Tk Canvas 画面。")
        else:
            # 3 = PW_CLIENTONLY | PW_RENDERFULLCONTENT
            if not user32.PrintWindow(hwnd, memory_dc, 3):
                raise RuntimeError("Windows 无法捕获 Tk Canvas 画面。")

        header = _BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height  # 负值表示自上而下存储。
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0  # BI_RGB

        buffer = (ctypes.c_ubyte * (width * height * 4))()
        scan_lines = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(header),
            0,
        )
        if scan_lines != height:
            raise RuntimeError(
                f"读取 Canvas 像素失败：预期 {height} 行，实际 {scan_lines} 行。"
            )

        # GetDIBits 返回 BGRA；转换为 PNG 使用的 RGBA。
        pixels = bytearray(buffer)
        pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]
        return bytes(pixels)
    finally:
        gdi32.SelectObject(memory_dc, previous_object)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def _looks_like_rendered_canvas(pixels: bytes) -> bool:
    """检查捕获结果是否为空黑或纯白画面。"""

    samples = []
    for x, y in ((4, 4), (RENDER_SIZE - 5, 4), (4, RENDER_SIZE - 5)):
        index = (y * RENDER_SIZE + x) * 4
        samples.append(pixels[index : index + 3])
    return all(
        not (max(pixel) < 3 or min(pixel) > 250) for pixel in samples
    )


def _rounded_rectangle_alpha(
    x: float,
    y: float,
    size: int,
    radius: float,
) -> int:
    """计算圆角方形边缘的柔顺透明度。"""

    half = size / 2
    qx = abs(x - half) - (half - radius)
    qy = abs(y - half) - (half - radius)
    distance = (
        min(max(qx, qy), 0.0)
        + math.hypot(max(qx, 0.0), max(qy, 0.0))
        - radius
    )
    coverage = max(0.0, min(1.0, 0.5 - distance))
    return round(coverage * 255)


def _resize_rgba(
    source: bytes,
    source_size: int,
    target_size: int,
) -> bytes:
    """使用面积平均缩放 RGBA 图像，并添加透明圆角遮罩。"""

    target = bytearray(target_size * target_size * 4)
    corner_radius = max(2.0, target_size * 0.18)

    for y in range(target_size):
        source_y1 = y * source_size // target_size
        source_y2 = (y + 1) * source_size // target_size
        for x in range(target_size):
            source_x1 = x * source_size // target_size
            source_x2 = (x + 1) * source_size // target_size
            red = green = blue = count = 0

            for source_y in range(source_y1, source_y2):
                row_offset = source_y * source_size * 4
                for source_x in range(source_x1, source_x2):
                    offset = row_offset + source_x * 4
                    red += source[offset]
                    green += source[offset + 1]
                    blue += source[offset + 2]
                    count += 1

            output_offset = (y * target_size + x) * 4
            target[output_offset] = round(red / count)
            target[output_offset + 1] = round(green / count)
            target[output_offset + 2] = round(blue / count)
            target[output_offset + 3] = _rounded_rectangle_alpha(
                x + 0.5,
                y + 0.5,
                target_size,
                corner_radius,
            )

    return bytes(target)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """生成单个 PNG 数据块。"""

    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _encode_png(size: int, rgba: bytes) -> bytes:
    """把 RGBA 像素编码为标准 PNG。"""

    row_size = size * 4
    scanlines = b"".join(
        b"\x00" + rgba[row * row_size : (row + 1) * row_size]
        for row in range(size)
    )
    header = struct.pack(
        ">IIBBBBB",
        size,
        size,
        8,  # 位深
        6,  # RGBA
        0,  # 压缩方法
        0,  # 过滤方法
        0,  # 非隔行
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _encode_ico(images: Iterable[tuple[int, bytes]]) -> bytes:
    """把多张 PNG 打包进 ICO 容器。"""

    image_list = list(images)
    header = struct.pack("<HHH", 0, 1, len(image_list))
    offset = 6 + 16 * len(image_list)
    entries: list[bytes] = []
    payloads: list[bytes] = []

    for size, png_data in image_list:
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(png_data),
                offset,
            )
        )
        payloads.append(png_data)
        offset += len(png_data)

    return header + b"".join(entries) + b"".join(payloads)


def _render_offscreen() -> tuple[int, bytes]:
    """通过离屏 GDI 画布渲染，供无可见桌面时回退使用。"""

    canvas = _GdiCanvas(RENDER_SIZE, scale=3)
    try:
        draw_icon(canvas)
        return canvas.width, canvas.to_rgba()
    finally:
        canvas.close()


def create_icon() -> Path:
    """绘制图标、导出多尺寸 ICO，并返回输出路径。"""

    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()

    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.configure(bg=COLOR_BACKGROUND_TOP)
    root.geometry(
        f"{RENDER_SIZE}x{RENDER_SIZE}-10000-10000"
    )

    canvas = tk.Canvas(
        root,
        width=RENDER_SIZE,
        height=RENDER_SIZE,
        highlightthickness=0,
        borderwidth=0,
        bg=COLOR_BACKGROUND_TOP,
    )
    canvas.pack()

    try:
        source_size = RENDER_SIZE
        source = b""
        draw_icon(canvas)

        # 无边框窗口放到屏幕外进行渲染；PrintWindow 仍会要求 Canvas
        # 把完整客户区绘制到内存 DC 中。
        try:
            root.deiconify()
            root.update_idletasks()
            root.update()
            time.sleep(0.08)
            source = _capture_canvas(canvas, RENDER_SIZE, RENDER_SIZE)

            if not _looks_like_rendered_canvas(source):
                # 个别显卡驱动不会给屏幕外窗口返回有效像素，此时短暂
                # 显示窗口再读取一次桌面像素。
                root.geometry(
                    f"{RENDER_SIZE}x{RENDER_SIZE}+80+80"
                )
                root.attributes("-topmost", True)
                root.update_idletasks()
                root.update()
                time.sleep(0.12)
                source = _capture_canvas(
                    canvas,
                    RENDER_SIZE,
                    RENDER_SIZE,
                    copy_from_screen=True,
                )
        except (OSError, RuntimeError):
            source = b""

        if not _looks_like_rendered_canvas(source):
            # CI、远程会话或锁屏状态下无法读取桌面帧。改用共享同一套
            # 绘图指令的离屏 GDI 画布，保证仍能生成最终 ICO。
            source_size, source = _render_offscreen()

        images = []
        for size in ICON_SIZES:
            rgba = _resize_rgba(source, source_size, size)
            images.append((size, _encode_png(size, rgba)))

        OUTPUT_PATH.write_bytes(_encode_ico(images))
        return OUTPUT_PATH
    finally:
        root.destroy()


def main() -> None:
    """命令行入口。"""

    if sys.platform != "win32":
        raise SystemExit("请在 Windows 上运行此脚本以生成 ICO 文件。")

    output_path = create_icon()
    size_text = "、".join(str(size) for size in ICON_SIZES)
    print(f"已生成图标：{output_path}")
    print(f"包含尺寸：{size_text} px")


if __name__ == "__main__":
    main()

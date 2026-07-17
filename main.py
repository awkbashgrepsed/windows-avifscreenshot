import ctypes
import ctypes.wintypes as wintypes
import os
import re
import threading
from datetime import datetime

import keyboard
import pystray
from PIL import Image


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


# ============================================================
# Windows constants
# ============================================================

BI_RGB = 0
DIB_RGB_COLORS = 0


# ============================================================
# Embedded tray icon
# ============================================================

def get_tray_icon():
    # Create a simple 16x16 yellow icon
    image = Image.new(
        "RGB",
        (16, 16),
        "yellow"
    )

    return image


# ============================================================
# Windows structures
# ============================================================

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
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
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


# ============================================================
# Helpers
# ============================================================

def sanitize_filename(filename):
    filename = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        filename
    )

    filename = filename.rstrip(" .")

    return filename or "Untitled"


def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)

    if length == 0:
        return "Untitled"

    buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1
    )

    return buffer.value


def get_pictures_folder():
    pictures_folder = os.path.join(
        os.path.expanduser("~"),
        "Pictures"
    )

    os.makedirs(
        pictures_folder,
        exist_ok=True
    )

    return pictures_folder


# ============================================================
# Screenshot
# ============================================================

def take_screenshot():

    # Get the currently focused window
    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        print("Could not find the focused window.")
        return

    # Get window title
    window_title = get_window_title(hwnd)
    window_title = sanitize_filename(window_title)

    # Get window dimensions
    rect = RECT()

    if not user32.GetWindowRect(
        hwnd,
        ctypes.byref(rect)
    ):
        print("Could not get window dimensions.")
        return

    width = rect.right - rect.left
    height = rect.bottom - rect.top

    # Get device context
    hwnd_dc = user32.GetWindowDC(hwnd)

    if not hwnd_dc:
        print("Could not get window device context.")
        return

    # Create compatible device context
    mfc_dc = gdi32.CreateCompatibleDC(
        hwnd_dc
    )

    # Create bitmap
    save_bitmap = gdi32.CreateCompatibleBitmap(
        hwnd_dc,
        width,
        height
    )

    # Select bitmap
    gdi32.SelectObject(
        mfc_dc,
        save_bitmap
    )

    # Render the window into the bitmap
    result = user32.PrintWindow(
        hwnd,
        mfc_dc,
        0
    )

    if result == 0:
        print("Could not capture window.")

        gdi32.DeleteObject(
            save_bitmap
        )

        gdi32.DeleteDC(
            mfc_dc
        )

        user32.ReleaseDC(
            hwnd,
            hwnd_dc
        )

        return

    # Prepare bitmap information
    bitmap_info = BITMAPINFO()

    bitmap_info.bmiHeader.biSize = ctypes.sizeof(
        BITMAPINFOHEADER
    )

    bitmap_info.bmiHeader.biWidth = width
    bitmap_info.bmiHeader.biHeight = -height
    bitmap_info.bmiHeader.biPlanes = 1
    bitmap_info.bmiHeader.biBitCount = 32
    bitmap_info.bmiHeader.biCompression = BI_RGB

    # Allocate image buffer
    buffer = ctypes.create_string_buffer(
        width * height * 4
    )

    # Copy bitmap data
    gdi32.GetDIBits(
        mfc_dc,
        save_bitmap,
        0,
        height,
        buffer,
        ctypes.byref(bitmap_info),
        DIB_RGB_COLORS
    )

    # Create PIL image
    screenshot = Image.frombuffer(
        "RGB",
        (width, height),
        buffer,
        "raw",
        "BGRX",
        0,
        1
    )

    # Get Pictures folder
    pictures_folder = get_pictures_folder()

    # Create filename
    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    filename = (
        f"{window_title}_"
        f"{timestamp}.avif"
    )

    filepath = os.path.join(
        pictures_folder,
        filename
    )

    # Save as AVIF
    screenshot.save(
        filepath,
        format="AVIF",
        quality=90
    )

    # Cleanup
    gdi32.DeleteObject(
        save_bitmap
    )

    gdi32.DeleteDC(
        mfc_dc
    )

    user32.ReleaseDC(
        hwnd,
        hwnd_dc
    )

    print(
        f"Screenshot saved:\n"
        f"{filepath}"
    )


# ============================================================
# Keyboard listener
# ============================================================

def start_keyboard_listener():

    keyboard.add_hotkey(
        "print screen",
        take_screenshot
    )

    print(
        "Screenshot service running."
    )

    print(
        "Press Print Screen to capture "
        "the focused window."
    )

    keyboard.wait()


# ============================================================
# System tray
# ============================================================

def create_systray_icon():

    image = get_tray_icon()

    def exit_app(icon, item):
        keyboard.unhook_all()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(
            "Exit",
            exit_app
        )
    )

    icon = pystray.Icon(
        "Screenshot Service",
        image,
        "Screenshot Service",
        menu
    )

    icon.run()


# ============================================================
# Main
# ============================================================

keyboard_thread = threading.Thread(
    target=start_keyboard_listener,
    daemon=True
)

keyboard_thread.start()

create_systray_icon()


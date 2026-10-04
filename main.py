"""Uygulamanın giriş noktası."""
import ctypes
import tkinter as tk

from gui import DownloaderApp


def main():
    # Yüksek çözünürlüklü ekranlarda yazılar bulanık olmasın (sadece Windows)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
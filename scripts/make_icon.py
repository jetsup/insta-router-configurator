"""Generate assets/images/logo.ico from the source PNG logo.

Windows needs a real .ico file for the taskbar/executable icon; Nuitka's
--windows-icon-from-ico requires one (a .png is not accepted).
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'images', 'logo.png')
DST = os.path.join(ROOT, 'assets', 'images', 'logo.ico')

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    img = Image.open(SRC).convert('RGBA')
    img.save(DST, format='ICO', sizes=SIZES)
    print(f'Generated {DST}')


if __name__ == '__main__':
    main()

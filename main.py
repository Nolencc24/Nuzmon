"""
SoulSilver tracker.

    python main.py                 # read DeSmuME's memory directly (recommended)
    python main.py --demo          # sample data, no emulator needed
    python main.py --diagnose      # print what the tracker finds inside DeSmuME
    python main.py --lua           # read ss_dump.txt written by tools/tracker.lua instead
    python main.py --lua --file C:/path/ss_dump.txt
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="show sample data instead of reading the emulator")
    ap.add_argument("--diagnose", action="store_true", help="print what the tracker finds in DeSmuME, then exit")
    ap.add_argument("--pid", type=int, help="DeSmuME process ID, if auto-detection picks the wrong one")
    ap.add_argument("--lua", action="store_true", help="read the file written by tools/tracker.lua instead of memory")
    ap.add_argument("--file", default=os.path.join(HERE, "ss_dump.txt"), help="dump file for --lua mode")
    args = ap.parse_args()

    if args.diagnose:
        from tracker.game.memreader import diagnose
        diagnose(args.pid)
        return

    from tracker.game.sources import FileSource, MemorySource, write_demo_file
    if args.demo:
        source = FileSource(write_demo_file())
    elif args.lua:
        source = FileSource(args.file)
    else:
        source = MemorySource(pid=args.pid)

    from PySide6.QtWidgets import QApplication
    from tracker.ui.main_window import MainWindow
    from tracker.ui.style import STYLE

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow(source)
    win.resize(1280, 720)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

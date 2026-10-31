import sys

if sys.platform != "win32":
    raise SystemExit("This launcher requires Windows.")

from apps.desktop.overlay import main

raise SystemExit(main())

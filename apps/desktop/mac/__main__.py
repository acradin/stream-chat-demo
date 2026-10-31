import sys

if sys.platform != "darwin":
    raise SystemExit("This launcher requires macOS 14 or newer.")

from apps.desktop.overlay import main

raise SystemExit(main())

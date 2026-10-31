import sys

if not sys.platform.startswith("linux"):
    raise SystemExit("This launcher requires Linux.")

from apps.desktop.overlay import main

raise SystemExit(main())

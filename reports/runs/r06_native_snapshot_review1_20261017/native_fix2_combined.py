"""Run the original seven identities then one three-generation closure in the approved window."""

import native_probe_fix2
import native_multigeneration_fix2

if native_probe_fix2.main():
    raise SystemExit(1)
native_multigeneration_fix2.main()

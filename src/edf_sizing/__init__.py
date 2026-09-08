"""edf_sizing: reduced-order actuator-disk / momentum-theory EDF sizing tools.

Milestone 1 scope only: ideal 1-D actuator-disk (momentum theory) thrust,
induced velocity, and ideal power for static and axial forward-flight
operation, plus an explicitly separated non-ideal efficiency bookkeeping
layer. See DESIGN.md for sources and assumptions.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("edf-sizing")
except PackageNotFoundError:  # pragma: no cover - local/editable install w/o metadata
    __version__ = "0.0.0+unknown"

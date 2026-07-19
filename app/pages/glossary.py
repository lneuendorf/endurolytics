"""Glossary page: definitions and formulas for the training-load metrics."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html
from sqlalchemy.engine import Engine

from app.components import section_card

_TSS = r"""
**Training Stress Score** — a single number for how much stress one session put on
the body, combining **intensity** and **duration**. All disciplines reduce to the
same core formula once an *Intensity Factor* (IF) is known:

```
TSS = duration_hours × IF² × 100
```

By definition, **1 hour at threshold (IF = 1.0) = 100 TSS**.
"""

_IF = r"""
**Intensity Factor** — how hard the session was relative to *your* threshold
(1.0 = right at threshold). How IF is derived depends on the sport and the best
signal available:

**Bike (power)** — normalized power preferred, else average power:

```
IF = power ÷ FTP
```

**Run (pace)** — a faster (smaller) pace raises IF. Threshold pace is entered as
min/mile in Settings:

```
IF = threshold_pace ÷ activity_pace
```

**Swim (CSS)** — same ratio, using Critical Swim Speed per 100 m:

```
IF = CSS_pace ÷ activity_pace
```

**Heart-rate fallback** (any sport, when power/pace is missing). With resting HR
set, heart-rate *reserve* is used; otherwise a simple ratio:

```
IF = (avg_HR − resting_HR) ÷ (threshold_HR − resting_HR)
IF = avg_HR ÷ threshold_HR        (when no resting HR is set)
```

**Duration-only fallback** (last resort, no thresholds/HR available): a fixed
estimated intensity of **IF = 0.70** (easy-aerobic) is assumed and the result is
flagged as an estimate.
"""

_METHOD = r"""
For each activity the most accurate method the data supports is chosen, in order:

1. **Power** (bike) / **Pace** (run, swim) — needs FTP, threshold pace, or CSS.
2. **Heart rate** — needs threshold HR.
3. **Duration** — fixed IF 0.70 estimate.

Set your thresholds on the **Settings** page to move activities up this ladder.
The method used is stored per activity as `tss_method`.
"""

_CTL = r"""
**Chronic Training Load** — your long-term *fitness*. An exponentially weighted
moving average of daily TSS with a **42-day** time constant:

```
CTL_today = CTL_yesterday × e^(−1/42) + TSS_today × (1 − e^(−1/42))
```

Rises slowly as consistent training accumulates.
"""

_ATL = r"""
**Acute Training Load** — your short-term *fatigue*. The same moving average as
CTL but with a **7-day** time constant, so it reacts quickly to recent load:

```
ATL_today = ATL_yesterday × e^(−1/7) + TSS_today × (1 − e^(−1/7))
```
"""

_TSB = r"""
**Training Stress Balance** — your *form* (freshness), simply fitness minus fatigue:

```
TSB = CTL − ATL
```

**Positive** TSB → fresh/tapered. **Negative** TSB → carrying fatigue (normal
during a training block).
"""


def _entry(title: str, markdown: str):
    return section_card(title, dcc.Markdown(markdown))


def layout(engine: Engine):
    return dbc.Container(
        [
            html.H1("Metrics Glossary", className="mt-2 mb-2"),
            html.P(
                "How each training-load metric is defined and calculated, including "
                "the per-sport methods.",
                className="text-muted",
            ),
            _entry("TSS — Training Stress Score", _TSS),
            _entry("IF — Intensity Factor (per sport)", _IF),
            _entry("How the TSS method is chosen", _METHOD),
            _entry("CTL — Fitness", _CTL),
            _entry("ATL — Fatigue", _ATL),
            _entry("TSB — Form", _TSB),
        ],
        fluid=True,
    )

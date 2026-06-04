"""Turn job data + session times + PDF page counts into invoice line items,
using the prices and rules in rates.yaml. Pure arithmetic -- no AI, no network.
This is the file to extend as your billing rules grow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LineItem:
    description: str
    quantity: float
    unit: str
    unit_price: float
    amount: float


def _parse_hhmm(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _session_hours(start: str | None, end: str | None) -> float:
    s, e = _parse_hhmm(start), _parse_hhmm(end)
    if not s or not e:
        return 0.0
    hours = (e - s).total_seconds() / 3600.0
    return round(hours, 2) if hours > 0 else 0.0


def _after_hours(end: str | None, threshold: str) -> float:
    e, t = _parse_hhmm(end), _parse_hhmm(threshold)
    if not e or not t:
        return 0.0
    hours = (e - t).total_seconds() / 3600.0
    return round(hours, 2) if hours > 0 else 0.0


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def build_line_items(job, sessions, docs, rates) -> list[LineItem]:
    items: list[LineItem] = []

    transcript_pages = sum(d.page_count or 0 for d in docs if d.doc_type == "transcript")
    exhibit_pages = sum(d.page_count or 0 for d in docs if d.doc_type == "exhibit")

    t = rates["transcript"]
    add = rates["add_ons"]
    billed_t_pages = max(transcript_pages, t.get("minimum_pages", 0) or 0)

    # Certified original, with optional expedite multiplier on the unit price.
    expedite = job["expedite"] or "none"
    mult = 1.0
    if expedite == "same_day":
        mult = add.get("expedite_same_day_multiplier", 1.0)
    elif expedite == "daily":
        mult = add.get("expedite_daily_multiplier", 1.0)
    if billed_t_pages > 0 and t["original_per_page"] > 0:
        unit = _r2(t["original_per_page"] * mult)
        label = "Certified transcript (original)"
        if mult != 1.0:
            label += f" - expedited x{mult:g}"
        items.append(LineItem(label, billed_t_pages, "page", unit, _r2(billed_t_pages * unit)))

    # Additional certified copies.
    copies = job["copies"] or 0
    if copies > 0 and t.get("copy_per_page", 0) > 0 and billed_t_pages > 0:
        qty = copies * billed_t_pages
        items.append(LineItem(f"Transcript copies (x{copies})", qty, "page",
                              t["copy_per_page"], _r2(qty * t["copy_per_page"])))

    # Rough draft / ASCII.
    if (job["rough_draft"] or 0) and rates["rough_draft"]["per_page"] > 0 and transcript_pages > 0:
        rp = rates["rough_draft"]["per_page"]
        items.append(LineItem("Rough draft / ASCII", transcript_pages, "page", rp,
                              _r2(transcript_pages * rp)))

    # Exhibit handling, with an optional flat floor.
    ex = rates["exhibits"]
    if exhibit_pages > 0 and ex["per_page"] > 0:
        amount = _r2(exhibit_pages * ex["per_page"])
        floor = ex.get("minimum_charge", 0) or 0
        if amount < floor:
            items.append(LineItem("Exhibit handling (minimum)", 1, "flat", floor, floor))
        else:
            items.append(LineItem("Exhibit scanning / handling", exhibit_pages, "page",
                                  ex["per_page"], amount))

    # Appearance: per session OR hourly.
    app = rates["appearance"]
    n_sessions = len(sessions)
    total_hours = _r2(sum(_session_hours(s["start_time"], s["end_time"]) for s in sessions))
    if app.get("per_session", 0) > 0 and n_sessions > 0:
        items.append(LineItem("Appearance / per diem", n_sessions, "session",
                              app["per_session"], _r2(n_sessions * app["per_session"])))
    elif app.get("hourly", 0) > 0 and total_hours > 0:
        items.append(LineItem("Appearance (hourly)", total_hours, "hour",
                              app["hourly"], _r2(total_hours * app["hourly"])))

    # After-hours surcharge: hourly past the threshold OR flat.
    ah = rates["after_hours"]
    ah_hours = _r2(sum(_after_hours(s["end_time"], ah["threshold"]) for s in sessions))
    if ah_hours > 0:
        if ah.get("hourly", 0) > 0:
            items.append(LineItem(f"After-hours surcharge (past {ah['threshold']})",
                                  ah_hours, "hour", ah["hourly"], _r2(ah_hours * ah["hourly"])))
        elif ah.get("flat", 0) > 0:
            items.append(LineItem(f"After-hours surcharge (past {ah['threshold']})",
                                  1, "flat", ah["flat"], ah["flat"]))

    # E-transcript delivery.
    if (job["e_transcript"] or 0) and add.get("e_transcript", 0) > 0:
        items.append(LineItem("E-transcript / electronic delivery", 1, "flat",
                              add["e_transcript"], add["e_transcript"]))

    return items


def totals(items: list[LineItem]) -> tuple[float, float]:
    subtotal = _r2(sum(i.amount for i in items))
    return subtotal, subtotal  # Stage 0 has no tax; total == subtotal

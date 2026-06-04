"""Render a computed invoice by filling an editable template file.

The invoice LAYOUT lives in templates/*.j2 (markdown or HTML) -- edit those to
change how the draft looks, with zero code changes. The billing math stays in
billing.py. Switching from a plain markdown draft to a branded HTML/PDF invoice
is just pointing config.yaml's `template` at a different file."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _docs_summary(docs) -> dict:
    return {
        "transcript_pages": sum(d.page_count or 0 for d in docs if d.doc_type == "transcript"),
        "exhibit_pages": sum(d.page_count or 0 for d in docs if d.doc_type == "exhibit"),
        "unreadable": [
            {"file_path": d.file_path, "error": d.error}
            for d in docs
            if d.page_count is None
        ],
    }


def render_invoice(cfg, currency, job, sessions, docs, items, subtotal, total, created_at) -> str:
    template_path = Path(cfg["template"])
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=".html" in template_path.name,  # escape only for HTML templates
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["money"] = _money
    template = env.get_template(template_path.name)
    return template.render(
        firm=cfg["firm"],
        currency=currency,
        job=dict(job),
        sessions=[dict(s) for s in sessions],
        docs=_docs_summary(docs),
        items=[i.__dict__ for i in items],
        subtotal=subtotal,
        total=total,
        created_at=created_at,
    )


def write_draft(cfg, job_id, stamp, text) -> Path:
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    # Output extension follows the template: invoice.md.j2 -> .md, invoice.html.j2 -> .html
    name = Path(cfg["template"]).name
    if name.endswith(".j2"):
        name = name[:-3]
    suffix = Path(name).suffix or ".md"
    path = out_dir / f"invoice_{job_id}_{stamp}{suffix}"
    path.write_text(text)
    return path

# Report: the other pitfalls

## Layout
- **Two panels side by side, each with its legend**: the legend lands on the axis label (`tight_layout` shrinks the
  axes) → `fig.tight_layout()` **then** `fig.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, 0.0))`.
- **Orphan `h3`** at the bottom of a page → `break-after: avoid` (base); a box alone at the top of a page → reduce
  the preceding figure.
- **Macros defined in the base invisible from the child template** (jinja) → file `report_macros.html` imported;
  an imported macro does not see the template context: the base texts `L` are a jinja **global**.
- **Glyphs (→ ↔) absent from the font** used by matplotlib → fallback `DejaVu Sans` in `font.family` (base).

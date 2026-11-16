"""Generic native PDF layout, table cells and review previews; no semantic inference."""
from __future__ import annotations

import io


def enrich(raw, result):
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTImage, LTLine, LTRect, LTCurve, LTContainer
    # Use the same native PDFMiner engine as the retained pipeline, without
    # importing a rendering library into the read-only/no-socket parser.
    for page, output in zip(extract_pages(io.BytesIO(raw)), result["pages"], strict=True):
        chars, images, lines, rectangles, curves, shapes = [], [], [], [], [], []
        def visit(item):
            box = [float(item.x0), float(page.height-item.y1), float(item.x1), float(page.height-item.y0)] if hasattr(item, "bbox") else None
            if isinstance(item, LTChar):
                chars.append({"bbox": box, "text": item.get_text()})
            elif isinstance(item, LTImage):
                images.append({"bbox": box, "name": item.name})
            elif isinstance(item, LTLine):
                lines.append(box)
            elif isinstance(item, LTRect):
                rectangles.append(box)
                x0, y0, x1, y1 = box
                lines.extend(([x0,y0,x1,y0], [x0,y1,x1,y1], [x0,y0,x0,y1], [x1,y0,x1,y1]))
            elif isinstance(item, LTCurve):
                curves.append(box)
            if isinstance(item, (LTLine, LTRect, LTCurve)):
                shapes.append({"object_index": len(shapes), "kind": type(item).__name__, "bbox": box,
                    "points": [[float(x), float(page.height-y)] for x,y in item.pts]})
                if len(shapes) > 10000:
                    raise ValueError("PDF_GRAPHIC_OBJECT_LIMIT")
            if isinstance(item, LTContainer):
                for child in item:
                    visit(child)
        visit(page)
        from campus247_worker.knowledge_table_layout import closed_grid_cells
        cells, grid_issues = closed_grid_cells(lines, chars)
        tables = [{"cells": cells, "method": "closed-axis-regions-v2", "semantics_verified": False}] if len(cells)>=4 else []
        result["issues"].extend({**issue, "page": output["page"]} for issue in grid_issues)
        if images:
            route, reason = "RASTER_OR_MIXED", "RASTER_COVERAGE_REQUIRES_REVIEW"
        elif tables:
            route, reason = "NATIVE_TABLE", "TABLE_CONDITIONS_REQUIRES_REVIEW"
        elif lines or curves or rectangles:
            route, reason = "NATIVE_GRAPHICS", "GRAPHIC_RELATIONS_REQUIRES_REVIEW"
        else:
            route, reason = "NATIVE_TEXT", None
        output["layout"] = {"route": route, "width": page.width, "height": page.height,
            "coordinate_system": "PDF points; x from left, y from top", "rotation": page.rotate,
            "tables": tables, "images": images, "lines": lines, "curve_count": len(curves),
            "shapes": shapes,
            "rectangle_count": len(rectangles), "characters": chars, "semantics_verified": False, "ocr_applied": False}
        if reason:
            result["issues"].append({"page": output["page"], "code": reason,
                "fields": ["coverage", "units", "conditions", "relationships"]})
        if reason or any(issue["page"] == output["page"] for issue in result["issues"]):
            output["preview_status"] = "PENDING_RENDER"
    return result

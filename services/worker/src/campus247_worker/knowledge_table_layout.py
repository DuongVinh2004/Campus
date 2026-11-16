"""Bounded closed PDF grid regions, including rectangular merged cells.

Connectivity is geometric candidate evidence only. It does not assign headers,
units, row meaning, credits, reading correctness, or admission.
"""
from collections import deque
import math


def closed_grid_cells(lines, characters):
    if any(len(line) != 4 or any(not math.isfinite(value) for value in line) for line in lines):
        raise ValueError("Nonfinite PDF grid geometry")
    horizontal = [line for line in lines if abs(line[1]-line[3]) < .5]
    vertical = [line for line in lines if abs(line[0]-line[2]) < .5]
    xs = sorted({round(line[0], 2) for line in vertical})
    ys = sorted({round(line[1], 2) for line in horizontal})
    if len(xs)*len(ys) > 5000:
        return [], [{"code": "TABLE_GRID_LIMIT", "grid_vertices": len(xs)*len(ys)}]
    rows, columns = len(ys)-1, len(xs)-1
    if rows < 1 or columns < 1:
        return [], []

    def covered(segments, start, end):
        # Adjacent drawn segments can form a border. The existing half-point
        # PDF tolerance is kept; an actual gap is never silently bridged.
        reach = start
        for low, high in sorted(segments):
            if low > reach+.5:
                break
            if high >= reach-.5:
                reach = max(reach, high)
            if reach >= end-.5:
                return True
        return False

    h = {(row, column): covered([(min(a,c), max(a,c)) for a,b,c,d in horizontal if abs(b-y)<.5], left, right)
        for row,y in enumerate(ys) for column,(left,right) in enumerate(zip(xs,xs[1:]))}
    v = {(row, column): covered([(min(b,d), max(b,d)) for a,b,c,d in vertical if abs(a-x)<.5], top, bottom)
        for column,x in enumerate(xs) for row,(top,bottom) in enumerate(zip(ys,ys[1:]))}
    visited, cells, issues = set(), [], []
    for row in range(rows):
        for column in range(columns):
            if (row,column) in visited:
                continue
            pending, component, exterior = deque([(row,column)]), set(), False
            visited.add((row,column))
            while pending:
                r,c = pending.popleft()
                component.add((r,c))
                neighbours = ((r-1,c,h[r,c]), (r+1,c,h[r+1,c]), (r,c-1,v[r,c]), (r,c+1,v[r,c+1]))
                for nr,nc,wall in neighbours:
                    if wall:
                        continue
                    if not (0 <= nr < rows and 0 <= nc < columns):
                        exterior = True
                    elif (nr,nc) not in visited:
                        visited.add((nr,nc)); pending.append((nr,nc))
            if exterior:
                continue
            top_row, bottom_row = min(r for r,c in component), max(r for r,c in component)+1
            left_column, right_column = min(c for r,c in component), max(c for r,c in component)+1
            if len(component) != (bottom_row-top_row)*(right_column-left_column):
                issues.append({"code": "TABLE_NONRECTANGULAR_REGION", "grid_cells": sorted(component)})
                continue
            # An interior partial stroke can be a damaged separator. Keep the
            # ambiguity instead of calling an L/T-shaped region one merged cell.
            internal_h = any(h[r,c] for r in range(top_row+1,bottom_row) for c in range(left_column,right_column))
            internal_v = any(v[r,c] for r in range(top_row,bottom_row) for c in range(left_column+1,right_column))
            if internal_h or internal_v:
                issues.append({"code": "TABLE_PARTIAL_INTERNAL_BORDER", "grid_cells": sorted(component)})
                continue
            left,top,right,bottom = xs[left_column],ys[top_row],xs[right_column],ys[bottom_row]
            content = [char for char in characters if left <= (char["bbox"][0]+char["bbox"][2])/2 < right
                and top <= (char["bbox"][1]+char["bbox"][3])/2 < bottom]
            cells.append({"row": top_row, "column": left_column, "row_span": bottom_row-top_row,
                "column_span": right_column-left_column, "bbox": [left,top,right,bottom],
                "text": "".join(char["text"] for char in content), "characters": content,
                "structure_verified": False})
    return cells, issues

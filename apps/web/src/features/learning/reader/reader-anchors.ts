export interface NormalizedRect { x: number; y: number; width: number; height: number }
export interface ReaderAnchor {
  kind: "PAGE" | "TEXT" | "REGION";
  rects?: NormalizedRect[];
  text_quote?: { exact: string; prefix?: string; suffix?: string };
}
export interface ReaderSelection { version_id: string; page_no: number; anchor: ReaderAnchor }
export interface ReaderAnnotation extends ReaderSelection { id: string; body?: string }

const bounded = (v: number) => Math.max(0, Math.min(1, Number.isFinite(v) ? v : 0));
function rotatePoint(x: number, y: number, rotation: number): [number, number] {
  switch (((rotation % 360) + 360) % 360) {
    case 90: return [1 - y, x];
    case 180: return [1 - x, 1 - y];
    case 270: return [y, 1 - x];
    default: return [x, y];
  }
}
/** Canonical coordinates are relative to the original unrotated page, independent of zoom. */
export function rotateAnchorRect(rect: NormalizedRect, rotation: number): NormalizedRect {
  const x1=bounded(rect.x), y1=bounded(rect.y), x2=bounded(rect.x+rect.width), y2=bounded(rect.y+rect.height);
  const corners=[rotatePoint(x1,y1,rotation),rotatePoint(x2,y1,rotation),rotatePoint(x1,y2,rotation),rotatePoint(x2,y2,rotation)];
  const xs=corners.map(c=>c[0]), ys=corners.map(c=>c[1]);
  const left=Math.min(...xs),top=Math.min(...ys);
  return {x:left,y:top,width:Math.max(...xs)-left,height:Math.max(...ys)-top};
}
export function canonicalAnchorRect(rect: NormalizedRect, rotation: number): NormalizedRect { return rotateAnchorRect(rect, -rotation); }

export function rectFromClient(client: Pick<DOMRect,"left"|"top"|"width"|"height">, page: Pick<DOMRect,"left"|"top"|"width"|"height">, rotation: number): NormalizedRect {
  if (page.width <= 0 || page.height <= 0) return {x:0,y:0,width:0,height:0};
  const x=bounded((client.left-page.left)/page.width), y=bounded((client.top-page.top)/page.height);
  const right=bounded((client.left+client.width-page.left)/page.width), bottom=bounded((client.top+client.height-page.top)/page.height);
  return canonicalAnchorRect({x,y,width:Math.max(0,right-x),height:Math.max(0,bottom-y)},rotation);
}

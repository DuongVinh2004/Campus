import {describe,it,expect} from "vitest";
import {canonicalAnchorRect,rectFromClient,rotateAnchorRect} from "./reader-anchors";

describe("Version page anchors remain stable through rotation and zoom",()=>{
  it.each([0,90,180,270])("round trips normalized coordinates through rotation %i",rotation=>{
    const original={x:0.1,y:0.2,width:0.3,height:0.1};
    const restored=canonicalAnchorRect(rotateAnchorRect(original,rotation),rotation);
    for(const key of ["x","y","width","height"] as const)expect(restored[key]).toBeCloseTo(original[key],6);
  });
  it("normalizes the same text rectangle at two zoom levels",()=>{
    const a=rectFromClient({left:120,top:240,width:60,height:20},{left:100,top:200,width:200,height:400},0);
    const b=rectFromClient({left:140,top:280,width:120,height:40},{left:100,top:200,width:400,height:800},0);
    expect(a).toEqual(b);expect(a.x).toBeCloseTo(.1);expect(a.y).toBeCloseTo(.1);expect(a.width).toBeCloseTo(.3);expect(a.height).toBeCloseTo(.05);
  });
  it("clamps an out of bounds region instead of drawing over another page",()=>{
    const rect=rectFromClient({left:-100,top:80,width:1000,height:1000},{left:0,top:0,width:200,height:200},0);
    expect(rect.x).toBe(0);expect(rect.y).toBeCloseTo(.4);expect(rect.width).toBe(1);expect(rect.height).toBeCloseTo(.6);
  });
  it("clips the part outside the page rather than shifting its width inside",()=>{
    const rect=rectFromClient({left:-100,top:0,width:120,height:20},{left:0,top:0,width:200,height:200},0);
    expect(rect.x).toBe(0);expect(rect.width).toBeCloseTo(.1);
  });
});

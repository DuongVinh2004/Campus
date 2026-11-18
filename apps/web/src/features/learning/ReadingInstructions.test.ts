import { describe, expect, it } from "vitest";
import { parseReadingRanges } from "./ReadingInstructions";
describe("reading instruction physical page ranges",()=>{
  it("parses individual pages and inclusive ranges",()=>expect(parseReadingRanges("1-3, 5, 8 - 10")).toEqual([{start:1,end:3},{start:5,end:5},{start:8,end:10}]));
  it("rejects page zero and reversed ranges",()=>{for(const value of ["0","3-1","-1","1.5","abc","1-2-3",""])expect(()=>parseReadingRanges(value)).toThrow();});
  it("caps the number of ranges before sending a request",()=>expect(()=>parseReadingRanges(Array.from({length:31},(_,index)=>String(index+1)).join(","))).toThrow());
});

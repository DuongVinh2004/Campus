import { expect, it } from "vitest";
import { ApiClientError, type ProblemDetails } from "./client";

it("shows a clear expired-session message while retaining structured diagnostics",()=>{
  const problem:ProblemDetails={type:"https://campus247.example/problems/authentication-required",title:"Authentication Required",status:401,
    code:"AUTHENTICATION_REQUIRED",detail:"{'status':401,'detail':'A valid Bearer token or signed session is required.'}",request_id:"request-1"};
  const error=new ApiClientError(problem);
  expect(error.message).toContain("Vui lòng đăng nhập lại");
  expect(error.message).not.toContain("Bearer");
  expect(error.problem).toBe(problem);
});

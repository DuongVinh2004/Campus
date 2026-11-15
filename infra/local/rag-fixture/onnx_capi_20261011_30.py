"""Restricted signed ONNX CPU C API, with no custom-op/provider registration."""
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RELEASE = HERE / "onnx-review-20261007-29/publisher-release/onnxruntime-win-x64-1.30.0"
# Linux: the publisher's onnxruntime-linux-x64 release, pinned by hash in linux-release.json (acquired 2026-11-15).
LINUX_DIR = HERE / "onnx-linux-20261115"
LINUX_RECORD = LINUX_DIR / "linux-release.json"
REVIEW = HERE / "acceptance-20261011-30-runtime-technical-review.json"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


class CPU:
    ALLOWED = {"GetErrorCode", "GetErrorMessage", "CreateEnv", "DisableTelemetryEvents", "CreateSession", "Run",
        "CreateSessionOptions", "SetSessionExecutionMode", "SetSessionGraphOptimizationLevel", "SetIntraOpNumThreads", "SetInterOpNumThreads",
        "SessionGetInputCount", "SessionGetOutputCount", "SessionGetInputName", "SessionGetOutputName", "CreateRunOptions", "RunOptionsSetTerminate",
        "CreateTensorWithDataAsOrtValue", "GetTensorMutableData", "GetTensorTypeAndShape", "GetDimensionsCount", "GetDimensions",
        "GetTensorShapeElementCount", "GetTensorElementType", "CreateCpuMemoryInfo", "GetAllocatorWithDefaultOptions", "AllocatorFree",
        "ReleaseEnv", "ReleaseStatus", "ReleaseMemoryInfo", "ReleaseSession", "ReleaseValue", "ReleaseRunOptions", "ReleaseTensorTypeAndShapeInfo", "ReleaseSessionOptions"}

    def __init__(self):
        review = json.loads(REVIEW.read_bytes())
        assert review["runtime_clearance"] == "accepted_local_synthetic_signed_C_API_only" and review["exit_code"] == 0
        if os.name == "nt":
            dll = RELEASE / "lib/onnxruntime.dll"
            assert dll.resolve().is_relative_to(ROOT) and digest(dll) == review["dll_sha256"]
            acquisition = json.loads((HERE / "acceptance-20261011-30-release-acquisition.json").read_bytes())
            header = RELEASE / "include/onnxruntime_c_api.h"
            assert digest(header) == acquisition["files"][header.relative_to(ROOT).as_posix()]
        else:
            record = json.loads(LINUX_RECORD.read_bytes())
            assert record["schema"] == "onnx-linux-release-v1" and record["version"] == "1.30.0" and record["tgz_matches_publisher_digest"]
            dll = LINUX_DIR / record["lib"]
            assert dll.resolve().is_relative_to(ROOT) and digest(dll) == record["lib_sha256"]
            header = LINUX_DIR / record["header"]
            assert digest(header) == record["header_sha256"]
        text = header.read_text(encoding="utf-8")
        assert re.search(r"#define ORT_API_VERSION\s+30\b", text)
        body = text.split("struct OrtApi {", 1)[1].split("\n};", 1)[0]
        body = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.S)
        pattern = r"ORT_API2_STATUS\s*\(\s*(\w+)|ORT_CLASS_RELEASE\s*\(\s*(\w+)|\(\s*ORT_API_CALL\s*\*\s*(\w+)\s*\)"
        names = [status or ("Release" + release if release else plain) for status, release, plain in re.findall(pattern, body)]
        assert names[:4] == ["CreateStatus", "GetErrorCode", "GetErrorMessage", "CreateEnv"]
        assert names[6] == "DisableTelemetryEvents" and names[9] == "Run" and names[92:101] == ["ReleaseEnv", "ReleaseStatus", "ReleaseMemoryInfo", "ReleaseSession", "ReleaseValue", "ReleaseRunOptions", "ReleaseTypeInfo", "ReleaseTensorTypeAndShapeInfo", "ReleaseSessionOptions"]
        self.fields = {name: index for index, name in enumerate(names)}
        assert self.ALLOWED <= self.fields.keys()
        # Normal OS loader and policy enforcement, restricted to these reviewed bytes (Windows: signed DLL and installed
        # system dependencies; Linux: the hash-pinned publisher .so). Both use the C calling convention of their ABI.
        if os.name == "nt":
            self.library = ct.WinDLL(str(dll), winmode=0x100 | 0x800)
            self.FUNC = ct.WINFUNCTYPE
        else:
            self.library = ct.CDLL(str(dll))
            self.FUNC = ct.CFUNCTYPE
        self.library.OrtGetApiBase.argtypes = []
        self.library.OrtGetApiBase.restype = ct.POINTER(ct.c_void_p)
        api_base = self.library.OrtGetApiBase()
        get_api = self.FUNC(ct.POINTER(ct.c_void_p), ct.c_uint32)(api_base[0])
        get_version = self.FUNC(ct.c_char_p)(api_base[1])
        self.version = get_version().decode("ascii")
        assert self.version == "1.30.0"
        self.api = get_api(30)
        assert self.api
        self.env = ct.c_void_p()
        self.status("CreateEnv", [ct.c_int, ct.c_char_p, ct.POINTER(ct.c_void_p)], 2, b"campus247-M1-synthetic", ct.byref(self.env))
        self.status("DisableTelemetryEvents", [ct.c_void_p], self.env)

    def function(self, name, result, arguments):
        assert name in self.ALLOWED
        return self.FUNC(result, *arguments)(self.api[self.fields[name]])

    def status(self, name, arguments, *values):
        status = self.function(name, ct.c_void_p, arguments)(*values)
        if status:
            code = self.function("GetErrorCode", ct.c_int, [ct.c_void_p])(status)
            self.function("ReleaseStatus", None, [ct.c_void_p])(status)
            raise RuntimeError(f"ONNX_RUNTIME_STATUS_{code}")

    def close(self):
        if self.env.value:
            self.function("ReleaseEnv", None, [ct.c_void_p])(self.env)
            self.env = ct.c_void_p()


def smoke():
    engine = CPU()
    try:
        print(json.dumps({"runtime": "onnxruntime", "version": engine.version, "api_version": 30,
            "host_policy_accepted_actual_load": True, "env_created": True, "telemetry_disabled": True,
            "custom_op_registration": False, "model_calls": 0, "protection_changes": 0}), flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    smoke()

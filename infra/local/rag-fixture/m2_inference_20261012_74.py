"""No-network signed C API sessions; explicit shape and configured finite Run bounds."""
import ctypes as ct
import json
import math
import os
import threading
import time

from onnx_capi_20261011_30 import digest
from onnx_graph_20261011_30 import DEST, fields, one, text, values
from onnx_reranker_graph_20261011_30 import field, encode
import continuation_audit as audit
import acceptance_continuation_20261005_10 as base

from m2_config_20261012_74 import config
DEADLINES = config()
base.LABEL = "acceptance-20261012-53"
OPERATORS = {"Constant", "Shape", "Gather", "Unsqueeze", "Slice", "Concat", "Reshape", "ConstantOfShape", "Mul", "Equal", "Where", "Expand", "Cast", "Sub", "Not", "CumSum", "Add", "ReduceMean", "Pow", "Sqrt", "Div", "MatMul", "Transpose", "Softmax", "Erf", "Abs", "ReduceSum", "Clip", "Gemm", "Tanh", "Sigmoid"}


def raw_graph():
    source = audit.checked(DEST / "reranker.onnx")
    binding = json.loads((audit.HERE / "acceptance-20261011-30-reranker-graph-binding.json").read_bytes())
    assert digest(source) == binding["graph_sha256"]
    model = source.read_bytes(); graph = one(model, 7)
    output = values(graph, 12)
    assert len(output) == 1 and text(output[0], 1) == "scores"
    logits = encode([(n, w, b"logits" if n == 1 else v) for n, w, v in fields(output[0])])
    graph += field(12, logits)
    target = audit.checked(DEST / "reranker-logits.onnx")
    with target.open("xb") as out:
        out.write(encode([(n, w, graph if n == 7 else v) for n, w, v in fields(model)]))
    base.put("reranker-raw-graph", {"exit_code": 0, "source_graph_sha256": binding["graph_sha256"], "graph_sha256": digest(target),
        "graph_path": target.relative_to(audit.ROOT).as_posix(), "outputs": ["scores", "logits"], "reason": "Preserve actual logits for TEI raw_scores=true; no inverse sigmoid approximation", "model_execution": False})


def validate_model(path):
    path = audit.checked(path)
    assert path.parent.resolve() == DEST.resolve()
    model = path.read_bytes(); assert len(model) < 2_000_000
    assert set(n for n, _, _ in fields(model)) <= {1, 2, 3, 7, 8}
    assert one(model, 1) == 6
    imports = values(model, 8)
    assert len(imports) == 1 and one(imports[0], 2) == 11 and text(imports[0], 1) == ""
    graph = one(model, 7)
    locations = set(); tensor_count = 0
    def validate_tensor(tensor):
        nonlocal tensor_count
        dims = values(tensor, 1)
        assert all(type(d) is int and 0 <= d <= 250002 for d in dims)
        assert one(tensor, 2) in {1, 6, 7, 9}
        ext = {text(kv, 1): text(kv, 2) for kv in values(tensor, 13)}
        if ext:
            assert set(ext) == {"location", "offset", "length"}
            assert ext["location"] in {"model.onnx_data", "Constant_7_attr__value", "reranker.weights.safetensors"}
            location = audit.checked(path.parent / ext["location"])
            assert location.parent.resolve() == path.parent.resolve() and location.is_file()
            start, length = int(ext["offset"]), int(ext["length"])
            assert start >= 0 and length > 0 and start + length <= location.stat().st_size
            assert length == math.prod(dims) * {1: 4, 6: 4, 7: 8, 9: 1}[one(tensor, 2)]
            assert one(tensor, 14) == 1 and not one(tensor, 9, b"")
            locations.add(ext["location"])
        tensor_count += 1
    initializers = values(graph, 5)
    for tensor in initializers:
        validate_tensor(tensor)
    nodes = values(graph, 1)
    for item in nodes:
        assert text(item, 7) == "" and text(item, 4) in OPERATORS
        assert set(n for n, _, _ in fields(item)) <= {1, 2, 3, 4, 5}
        for attribute in values(item, 5):
            assert one(attribute, 20) in {1, 2, 3, 4, 6, 7, 8}
            assert not any(n in {6, 10, 11, 14, 15, 21, 22, 23} for n, _, _ in fields(attribute))
            for tensor in values(attribute, 5):
                validate_tensor(tensor)
    return {"graph_sha256": digest(path), "initializers": len(initializers), "nodes": len(nodes), "checked_tensors": tensor_count,
        "external_files": sorted(locations), "custom_ops": False, "subgraphs": False, "executable_model_code": False}


class Session:
    def __init__(self, engine, path, optimization=99):
        self.engine = engine; self.handle = ct.c_void_p(); self.options = ct.c_void_p()
        self.validation = validate_model(path)
        started = time.monotonic()
        engine.status("CreateSessionOptions", [ct.POINTER(ct.c_void_p)], ct.byref(self.options))
        try:
            engine.status("SetSessionExecutionMode", [ct.c_void_p, ct.c_int], self.options, 0)
            engine.status("SetIntraOpNumThreads", [ct.c_void_p, ct.c_int], self.options, 4)
            engine.status("SetInterOpNumThreads", [ct.c_void_p, ct.c_int], self.options, 1)
            engine.status("SetSessionGraphOptimizationLevel", [ct.c_void_p, ct.c_int], self.options, optimization)
            engine.status("CreateSession", [ct.c_void_p, ct.c_wchar_p if os.name == "nt" else ct.c_char_p, ct.c_void_p, ct.POINTER(ct.c_void_p)], engine.env, str(path) if os.name == "nt" else os.fsencode(path), self.options, ct.byref(self.handle))
        finally:
            engine.function("ReleaseSessionOptions", None, [ct.c_void_p])(self.options)
        self.load_seconds = time.monotonic() - started
        for kind, count_function in (("Input", "SessionGetInputCount"), ("Output", "SessionGetOutputCount")):
            count = ct.c_size_t()
            engine.status(count_function, [ct.c_void_p, ct.POINTER(ct.c_size_t)], self.handle, ct.byref(count))
            assert count.value == 2

    def run(self, sequences, output_name):
        assert output_name in {b"sentence_embedding", b"logits", b"scores"}
        assert 1 <= len(sequences) <= 50 and all(isinstance(row, list) and 2 <= len(row) <= 900 for row in sequences)
        assert all(type(i) is int and 0 <= i < 250002 for row in sequences for i in row)
        assert all(row[0] == 0 and row[-1] == 2 for row in sequences)
        width = max(map(len, sequences)); count = len(sequences) * width
        ids = (ct.c_int64 * count)(*(i for row in sequences for i in row + [1] * (width - len(row))))
        mask = (ct.c_int64 * count)(*(i for row in sequences for i in [1] * len(row) + [0] * (width - len(row))))
        shape = (ct.c_int64 * 2)(len(sequences), width)
        memory = ct.c_void_p(); options = ct.c_void_p(); input_values = (ct.c_void_p * 2)(); outputs = (ct.c_void_p * 1)()
        engine = self.engine; fired = threading.Event(); timer = None
        try:
            engine.status("CreateCpuMemoryInfo", [ct.c_int, ct.c_int, ct.POINTER(ct.c_void_p)], 1, 0, ct.byref(memory))
            for index, data in enumerate((ids, mask)):
                value = ct.c_void_p()
                engine.status("CreateTensorWithDataAsOrtValue", [ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.POINTER(ct.c_int64), ct.c_size_t, ct.c_int, ct.POINTER(ct.c_void_p)], memory, ct.cast(data, ct.c_void_p), ct.sizeof(data), shape, 2, 7, ct.byref(value))
                input_values[index] = value.value
            engine.status("CreateRunOptions", [ct.POINTER(ct.c_void_p)], ct.byref(options))
            def terminate():
                fired.set()
                engine.status("RunOptionsSetTerminate", [ct.c_void_p], options)
            timer = threading.Timer(DEADLINES.native_ms / 1000, terminate); timer.daemon = True
            started = time.monotonic(); timer.start()
            try:
                engine.status("Run", [ct.c_void_p, ct.c_void_p, ct.POINTER(ct.c_char_p), ct.POINTER(ct.c_void_p), ct.c_size_t, ct.POINTER(ct.c_char_p), ct.c_size_t, ct.POINTER(ct.c_void_p)], self.handle, options,
                    (ct.c_char_p * 2)(b"input_ids", b"attention_mask"), input_values, 2, (ct.c_char_p * 1)(output_name), 1, outputs)
            except RuntimeError:
                if fired.is_set():
                    raise TimeoutError(f"{DEADLINES.native_ms}ms model deadline reached; native Run terminated") from None
                raise
            elapsed = time.monotonic() - started
            timer.cancel(); timer.join()
            if fired.is_set() or elapsed > DEADLINES.native_ms / 1000:
                raise TimeoutError(f"{DEADLINES.native_ms}ms model deadline reached; output discarded")
            info = ct.c_void_p()
            engine.status("GetTensorTypeAndShape", [ct.c_void_p, ct.POINTER(ct.c_void_p)], outputs[0], ct.byref(info))
            try:
                dtype = ct.c_int(); rank = ct.c_size_t(); length = ct.c_size_t()
                engine.status("GetTensorElementType", [ct.c_void_p, ct.POINTER(ct.c_int)], info, ct.byref(dtype))
                engine.status("GetDimensionsCount", [ct.c_void_p, ct.POINTER(ct.c_size_t)], info, ct.byref(rank))
                assert dtype.value == 1 and rank.value == 2
                dimensions = (ct.c_int64 * 2)()
                engine.status("GetDimensions", [ct.c_void_p, ct.POINTER(ct.c_int64), ct.c_size_t], info, dimensions, 2)
                assert list(dimensions) == [len(sequences), 1024 if output_name == b"sentence_embedding" else 1]
                engine.status("GetTensorShapeElementCount", [ct.c_void_p, ct.POINTER(ct.c_size_t)], info, ct.byref(length))
                assert length.value == math.prod(dimensions)
                pointer = ct.c_void_p()
                engine.status("GetTensorMutableData", [ct.c_void_p, ct.POINTER(ct.c_void_p)], outputs[0], ct.byref(pointer))
                data = ct.cast(pointer, ct.POINTER(ct.c_float))
                result = [[float(data[row * dimensions[1] + col]) for col in range(dimensions[1])] for row in range(dimensions[0])]
                assert all(math.isfinite(i) for row in result for i in row)
                return result, elapsed
            finally:
                engine.function("ReleaseTensorTypeAndShapeInfo", None, [ct.c_void_p])(info)
        finally:
            if timer:
                timer.cancel(); timer.join()
            for value in [*input_values, *outputs]:
                if value:
                    engine.function("ReleaseValue", None, [ct.c_void_p])(value)
            if options.value:
                engine.function("ReleaseRunOptions", None, [ct.c_void_p])(options)
            if memory.value:
                engine.function("ReleaseMemoryInfo", None, [ct.c_void_p])(memory)

    def close(self):
        if self.handle.value:
            self.engine.function("ReleaseSession", None, [ct.c_void_p])(self.handle)
            self.handle = ct.c_void_p()


if __name__ == "__main__":
    raw_graph()

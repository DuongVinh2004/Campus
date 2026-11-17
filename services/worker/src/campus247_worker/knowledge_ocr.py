"""One bounded page through the retained installed local Vietnamese OCR engine.

The read-only document parser remains separate. OCR text, confidence and pixel
boxes are candidate witnesses, never verified table/arrow/course semantics.
"""
import asyncio
import json
import os
import struct
import time
from pathlib import Path
from uuid import uuid4

from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.infrastructure.knowledge.storage import checked_path


class LocalOcrAdapter:
    def __init__(self, storage, *, node, package_root):
        self.storage = storage
        self.node = Path(node).resolve(strict=True)
        if Path(package_root).name != "package.json":
            raise ValueError("Explicit installed Node package resolution anchor required")
        # createRequire uses an absolute resolution anchor; that JSON filename
        # need not exist. The actual installed engine/core directories must.
        self.package_root = Path(package_root).parent.resolve(strict=True) / "package.json"
        package = self.package_root.parent / "node_modules/tesseract.js"
        core = self.package_root.parent / "node_modules/tesseract.js-core"
        if self.node.name != "node.exe" or not package.is_dir() or not core.is_dir():
            raise ValueError("Existing bundled local OCR runtime required")
        self.package, self.core = package,core
        self.script = checked_path(storage.workspace / "scripts/huce_document_ocr.mjs",storage.workspace)
        self.guard = checked_path(Path(__file__).with_name("knowledge_ocr_network_guard.cjs"),storage.workspace)
        self.language = checked_path(storage.workspace / "data/huce-public-20261013/vie.traineddata",storage.workspace)
        # Pin installed executable, engine/core closure and language without a
        # package install, download, additional provider or changed budget cap.
        self.profile = {"engine":"tesseract.js", "version":json.loads((package / "package.json").read_text())["version"],
            "dependency_closure_sha256":self.dependency_hash(),"node_sha256":digest(self.node.read_bytes()),
            "language":"vie","traineddata_sha256":digest(self.language.read_bytes()),"script_sha256":digest(self.script.read_bytes()),
            "guard_sha256":digest(self.guard.read_bytes()),"adapter_sha256":digest(Path(__file__).read_bytes()),
            "schema":"local-page-ocr-unverified-v1","semantics_verified":False}
        self.config_hash = digest(self.profile)

    def dependency_hash(self):
        closure = {}
        for root in (self.package,self.core):
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    closure[root.name+"/"+path.relative_to(root).as_posix()] = digest(path.read_bytes())
        return digest(closure)

    def check_profile(self):
        if (digest(self.language.read_bytes()) != self.profile["traineddata_sha256"] or digest(self.script.read_bytes()) != self.profile["script_sha256"]
            or digest(self.guard.read_bytes()) != self.profile["guard_sha256"] or self.dependency_hash()!=self.profile["dependency_closure_sha256"]
            or digest(self.node.read_bytes())!=self.profile["node_sha256"] or digest(Path(__file__).read_bytes())!=self.profile["adapter_sha256"]):
            raise PlatformError(409,"OCR_PROFILE_CHANGED","OCR dependency đổi giữa các bước; cần pipeline revision mới.")

    async def recognize(self, original, image, page):
        self.storage.read(original)
        png = self.storage.read(image)
        if png[:8] != b"\x89PNG\r\n\x1a\n" or len(png)<24:
            raise PlatformError(409,"OCR_IMAGE_INVALID","Ảnh OCR không phải PNG có binding hợp lệ.")
        width,height = struct.unpack(">II",png[16:24])
        if not 0 < width*height <= 2700**2:
            raise PlatformError(422,"OCR_IMAGE_LIMIT","Ảnh vượt giới hạn OCR cục bộ.")
        # Profile must remain the same between planning and the invocation.
        self.check_profile()
        scope = checked_path(self.storage.root.parent / "ocr-work" / uuid4().hex,self.storage.workspace)
        scope.mkdir(parents=True)
        for name in ("temp","appdata","localappdata"):
            checked_path(scope / name,self.storage.workspace).mkdir()
        output = checked_path(scope / "result",self.storage.workspace); output.mkdir()
        job = {"page":page,"source_file":self.storage.path(original["object_key"]).relative_to(self.storage.workspace).as_posix(),
            "source_sha256":original["sha256"],"image":self.storage.path(image["object_key"]).relative_to(self.storage.workspace).as_posix(),
            "image_sha256":image["sha256"]}
        manifest = {"pages":[job],"node_package_root":str(self.package_root),"language_directory":str(self.language.parent),"output_directory":str(output)}
        input_file = checked_path(scope / "input.json",self.storage.workspace)
        with input_file.open("xb") as stream: stream.write(json.dumps(manifest).encode())
        environment = {key:value for key,value in os.environ.items() if key.upper() in {"PATH","SYSTEMROOT","WINDIR"}}
        environment.update(TEMP=str(scope / "temp"),TMP=str(scope / "temp"),APPDATA=str(scope / "appdata"),LOCALAPPDATA=str(scope / "localappdata"),
            NODE_OPTIONS='--require="'+self.guard.as_posix()+'"')
        started = time.perf_counter()
        child = await asyncio.create_subprocess_exec(str(self.node),str(self.script),str(input_file),cwd=scope,env=environment,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=getattr(__import__("subprocess"),"CREATE_NO_WINDOW",0))
        try:
            stdout,stderr = await asyncio.wait_for(child.communicate(),timeout=120)
            for name,content in (("stdout.log",stdout),("stderr.log",stderr)):
                with (scope / name).open("xb") as stream: stream.write(content)
            if child.returncode or len(stdout)>100000 or len(stderr)>100000:
                raise PlatformError(422,"LOCAL_OCR_FAILED","OCR cục bộ chưa hoàn tất; ảnh và kết quả dở được giữ để đối chiếu.")
            files = list(output.glob("page-*.json"))
            if len(files)!=1:
                raise PlatformError(409,"OCR_RESULT_INVALID","OCR chưa trả một kết quả có binding rõ ràng.")
            path = checked_path(files[0],self.storage.workspace)
            if path.stat().st_size>32*1024**2:
                raise PlatformError(413,"OCR_OUTPUT_LIMIT","OCR vượt giới hạn bằng chứng.")
            payload = json.loads(path.read_bytes())
            if (any(payload.get(key)!=value for key,value in job.items()) or payload.get("dependency",{}).get("traineddata_sha256")!=self.profile["traineddata_sha256"]
                or payload.get("dependency",{}).get("version")!=self.profile["version"] or payload.get("index_status")!="not_admitted"):
                raise PlatformError(409,"OCR_RESULT_BINDING","Kết quả OCR không khớp nguồn, ảnh hoặc engine.")
            payload.update(automation_profile=self.profile,image_width=width,image_height=height)
            self.check_profile()
            saved = self.storage.write_json(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode(),"ocr-unverified")
            return saved,{"page":page,"ocr_invocations":1,"embedding_calls":0,"paid_model_calls":0,
                "wall_seconds":time.perf_counter()-started,"input_pixels":width*height,"cpu_seconds":None,"cpu_measurement":"not measured",
                "output_characters":len(payload.get("text","")),"semantics_verified":False}
        finally:
            if child.returncode is None:
                child.kill(); await child.wait()  # Only this task-owned child.

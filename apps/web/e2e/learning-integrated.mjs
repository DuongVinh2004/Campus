// Actual authenticated UI integration against the isolated Campus test host.
// No HAR, trace, storageState, passwords, cookies or tokens are written to reports.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { chromium, expect } from "@playwright/test";

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../../..");
const run=process.env.LEARNING_BROWSER_RUN||"20261104-01";
if(!/^[a-z0-9-]+$/.test(run))throw new Error("Invalid run identifier");
const tooling=fs.realpathSync(path.join(repo,".tooling"));
const output=path.resolve(tooling,`learning-browser-${run}`);
if(path.dirname(output)!==tooling||fs.existsSync(output))throw new Error("Output must be a new directory inside tooling");
fs.mkdirSync(output);
const temp=path.join(output,"temp");fs.mkdirSync(temp);process.env.TEMP=temp;process.env.TMP=temp;
const credentialPath=fs.realpathSync(process.env.LEARNING_TEST_CREDENTIALS||path.join(repo,"infra/local/learning-materials-20261104-01/credentials.json"));
if(!credentialPath.startsWith(repo+path.sep)||path.basename(credentialPath)!=="credentials.json")throw new Error("Synthetic workspace credentials are required");
const identityFixture=JSON.parse(fs.readFileSync(credentialPath,"utf8"));
if(identityFixture.synthetic_only!==true)throw new Error("Only synthetic accounts are permitted");
const accounts=identityFixture.accounts;
const base=process.env.LEARNING_TEST_URL||"http://127.0.0.1:8025";
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base))throw new Error("Only isolated loopback host allowed");
const checks=[],errors=[];let pptxSource=null;
const secretValues=accounts.flatMap(account=>[account.username,account.password]).filter(Boolean);
const safe=error=>secretValues.reduce((text,secret)=>text.split(secret).join("[redacted]"),String(error.message||error));
const contexts=[];
function fixturePdf(){
  if(!process.env.LEARNING_TEST_PDF&&!process.env.LEARNING_TEST_PPTX)return makePdf();
  const source=fs.realpathSync(process.env.LEARNING_TEST_PPTX||process.env.LEARNING_TEST_PDF);
  if(!source.startsWith(repo+path.sep)||!source.toLowerCase().endsWith(process.env.LEARNING_TEST_PPTX?'.pptx':'.pdf'))throw new Error('An exact workspace fixture is required');
  return fs.readFileSync(source);
}
async function login(role,viewport={width:1440,height:1000},ordinal=0,device=""){
  const account=accounts.filter(item=>item.role===role)[ordinal];if(!account)throw new Error(`Missing synthetic role ${role}`);
  const profile=path.join(output,`browser-profile-${role.toLowerCase()}-${ordinal}${device}`);
  if(path.dirname(profile)!==output||fs.existsSync(profile))throw new Error("Browser profile must be new and task-owned");
  const context=await chromium.launchPersistentContext(profile,{viewport,timezoneId:"UTC",hasTouch:viewport.width<600,headless:true,executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe"});contexts.push(context);const page=await context.newPage();
  page.on("pageerror",error=>errors.push(safe(error)));
  await page.goto(`${base}/login?redirect=%2Flearning`);await page.getByLabel("Tài khoản",{exact:true}).fill(account.username);await page.getByLabel("Mật khẩu",{exact:true}).fill(account.password);await page.getByRole("button",{name:"Đăng nhập",exact:true}).click();await page.waitForURL("**/learning");await expect(page.getByRole("heading",{name:"Học liệu theo buổi học",exact:true})).toBeVisible();return {page,context,account};
}
async function managementConfirm(page){await expect(page.getByRole("button",{name:"Xác nhận thay đổi"})).toBeDisabled();await page.getByLabel("Tôi đã kiểm tra thông tin và tác động.").check();await page.getByRole("button",{name:"Xác nhận thay đổi"}).click();await expect(page.getByRole("button",{name:"Xác nhận thay đổi"})).toHaveCount(0);}
async function pinchReader(page,context){
  const viewport=page.locator('.learning-reader-viewport');await viewport.scrollIntoViewIfNeeded();
  const rect=await viewport.boundingBox();if(!rect)throw new Error('Missing reader viewport');
  const x=rect.x+rect.width/2,y=Math.max(40,Math.min(750,rect.y+rect.height/2));
  const before=await page.getByLabel('Mức phóng',{exact:true}).innerText();
  const cdp=await context.newCDPSession(page);
  const points=gap=>[{x:x-gap/2,y,id:1,radiusX:5,radiusY:5},{x:x+gap/2,y,id:2,radiusX:5,radiusY:5}];
  try{
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points(80)});
    for(const gap of [120,160,200,240])await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:points(gap)});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await expect(page.getByLabel('Mức phóng',{exact:true})).not.toHaveText(before);
  }finally{await cdp.detach();}
  await page.getByRole('button',{name:'Vừa rộng',exact:true}).click();
}
async function capturePageCanvas(page,pageNo,name){
  const canvas=page.locator(`.learning-reader-viewport .page[data-page-number="${pageNo}"][data-loaded="true"] .canvasWrapper canvas`);
  let data;
  await expect.poll(async()=>{
    try {data=await canvas.evaluate(element=>element.width>32&&element.height>32?element.toDataURL('image/png'):null,undefined,{timeout:1200});}
    catch {return false;}
    return typeof data==='string'&&data.startsWith('data:image/png;base64,')&&data.length>1024;
  },{timeout:20000}).toBe(true);
  fs.writeFileSync(path.join(output,name),Buffer.from(data.split(',')[1],'base64'),{flag:'wx'});
}
async function readerTools(page){
  if(process.env.LEARNING_TEST_PDF)await expect(page.locator('.learning-reader-viewport .page[data-page-number="1"] .textLayer')).toContainText('Học liệu tiếng Việt');
  if(process.env.LEARNING_TEST_PPTX){
    const first=page.locator('.learning-reader-viewport .page[data-page-number="1"]');
    await expect(first.locator('.textLayer')).toContainText('Nguyễn Thị Ánh');
    await capturePageCanvas(page,1,'pptx-table.png');
  }
  await page.getByLabel('Tìm trong bài',{exact:true}).fill('JOIN');
  await page.getByRole('button',{name:'Tìm tiếp',exact:true}).click();
  await expect(page.locator('.learning-reader-search [role="status"]')).toHaveText(/[1-9]\d*\/[1-9]\d* kết quả/);
  await page.getByRole('button',{name:'Ảnh trang',exact:true}).click();
  const last=page.getByRole('button',{name:'Đến trang 3',exact:true});await last.scrollIntoViewIfNeeded();
  await expect(last.locator('canvas')).toBeVisible();await last.click();
  await expect(page.getByLabel('Số trang',{exact:true})).toHaveValue('3');
  if(process.env.LEARNING_TEST_PPTX)await capturePageCanvas(page,3,'pptx-formula.png');
  await page.getByRole('button',{name:'Đóng điều hướng',exact:true}).click();
  if(process.env.LEARNING_TEST_PPTX){
    await page.getByLabel('Số trang',{exact:true}).fill('2');
    const chart=page.locator('.learning-reader-viewport .page[data-page-number="2"]');
    await expect(chart.locator('.textLayer')).toContainText('24');
    await capturePageCanvas(page,2,'pptx-chart.png');
  }
  await page.getByLabel('Số trang',{exact:true}).fill('1');
  const leaf=page.locator('.learning-reader-viewport .page[data-page-number="1"]');
  const before=await leaf.evaluate(element=>element.getBoundingClientRect().width/element.getBoundingClientRect().height);
  await page.getByRole('button',{name:'Xoay',exact:true}).click();
  await expect.poll(async()=>Math.abs(await leaf.evaluate(element=>element.getBoundingClientRect().width/element.getBoundingClientRect().height)-1/before)).toBeLessThan(0.05);
  for(let index=0;index<3;index++)await page.getByRole('button',{name:'Xoay',exact:true}).click();
  await page.getByRole('button',{name:'Mục lục',exact:true}).click();
  await expect(page.getByRole('complementary',{name:'Điều hướng tài liệu',exact:true})).toBeVisible();
  if(process.env.LEARNING_TEST_PDF){
    await page.getByRole('button',{name:'Buổi 2: SQL JOIN trên trang ngang',exact:true}).click();
    await expect(page.getByLabel('Số trang',{exact:true})).toHaveValue('2');
    await expect.poll(()=>page.locator('.learning-reader-viewport .page[data-page-number="2"]').evaluate(element=>element.clientWidth>element.clientHeight)).toBe(true);
    await page.getByLabel('Số trang',{exact:true}).fill('1');
  }
  await page.getByRole('button',{name:'Đóng điều hướng',exact:true}).click();
  await page.getByRole('button',{name:'Toàn màn hình',exact:true}).click();
  await expect(page.locator('.learning-pdf-reader')).toHaveClass(/learning-reader-focused/);
  await page.getByRole('button',{name:'Thoát tập trung',exact:true}).click();
  await expect(page.locator('.learning-pdf-reader')).not.toHaveClass(/learning-reader-focused/);
}
async function verifyPptxSource(page,context){
  const source=await page.getByRole('link',{name:'Tải bản gốc',exact:true}).getAttribute('href');
  if(!/^\/v1\/learning\/versions\/[0-9a-f-]{36}\/download$/.test(source||''))throw new Error('Invalid original download source');
  const original=await context.request.get(base+source);
  expect(original.status()).toBe(200);expect(original.headers()['content-type']).toBe('application/vnd.openxmlformats-officedocument.presentationml.presentation');
  const bytes=await original.body();expect(createHash('sha256').update(bytes).digest('hex')).toBe(createHash('sha256').update(fixturePdf()).digest('hex'));
  const range=await context.request.get(base+source.replace('/download','/content'),{headers:{Range:'bytes=0-15'}});
  expect(range.status()).toBe(206);expect(range.headers()['content-type']).toBe('application/pdf');expect((await range.body()).subarray(0,5).toString()).toBe('%PDF-');
  const metadata=await(await context.request.get(base+source.replace('/download',''))).json();
  expect(metadata.rendition_id).toMatch(/^[0-9a-f-]{36}$/);expect(metadata.source_media_type).toBe('application/vnd.openxmlformats-officedocument.presentationml.presentation');
  return {versionId:metadata.id,renditionId:metadata.rendition_id};
}
function makePdf(withLink=false){
  const parts=["%PDF-1.4\n"],offsets=[0];
  const objects=["<< /Type /Catalog /Pages 2 0 R >>","<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R] /Count 3 >>"];
  for(let index=0;index<3;index++){
    const stream=`BT /F1 20 Tf 50 740 Td (Learning page ${index+1} - SQL joins) Tj ET`;
    const annotations=withLink&&index===0?" /Annots [10 0 R]":"";
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 9 0 R >> >> /Contents ${4+index*2} 0 R${annotations} >>`,
      `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`);
  }
  objects.push("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
  if(withLink)objects.push("<< /Type /Annot /Subtype /Link /Rect [50 730 315 770] /A << /S /URI /URI (https://campus-links.invalid/reading) >> >>");
  objects.forEach((object,index)=>{offsets.push(Buffer.byteLength(parts.join("")));parts.push(`${index+1} 0 obj\n${object}\nendobj\n`);});
  const xref=Buffer.byteLength(parts.join(""));
  parts.push(`xref\n0 ${objects.length+1}\n0000000000 65535 f \n${offsets.slice(1).map(offset=>String(offset).padStart(10,"0")+" 00000 n ").join("\n")}\ntrailer\n<< /Size ${objects.length+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return Buffer.from(parts.join(""));
}
try{
  const admin=await login("SYSTEM_ADMIN");checks.push("admin login and protected learning page");
  const page=admin.page,term=`Học kỳ ${run}`,course=`Môn SQL ${run}`,classTitle=`Lớp SQL ${run}`,lectureTitle=`Bài giảng SQL joins ${run}`;
  await page.getByText("Quản trị học kỳ, môn học và thành viên",{exact:true}).click();
  await page.getByLabel("Tên học kỳ",{exact:true}).fill(term);await page.getByLabel("Ngày bắt đầu",{exact:true}).fill("2026-11-01");await page.getByLabel("Ngày kết thúc",{exact:true}).fill("2027-01-31");await page.getByRole("button",{name:"Tạo học kỳ",exact:true}).click();await managementConfirm(page);await expect(page.getByText("Đã tạo học kỳ.",{exact:true})).toBeVisible();checks.push("admin creates term via confirmed UI");
  await page.getByLabel("Mã môn",{exact:true}).fill(`SQL-${run}`);await page.getByLabel("Tên môn",{exact:true}).fill(course);await page.getByRole("button",{name:"Tạo môn học",exact:true}).click();await managementConfirm(page);await expect(page.getByText("Đã tạo môn học.",{exact:true})).toBeVisible();
  await page.locator('select[name="term_id"]').selectOption({label:term});await page.locator('select[name="course_id"]').selectOption({label:course});await page.getByLabel("Mã lớp",{exact:true}).fill(`L-${run}`);await page.getByLabel("Tên lớp",{exact:true}).fill(classTitle);await page.getByRole("button",{name:"Tạo lớp",exact:true}).click();await managementConfirm(page);await expect(page.getByText("Đã tạo lớp học phần.",{exact:true})).toBeVisible();checks.push("admin creates course and offering via confirmed UI");
  for(const account of accounts.filter(item=>item.role==="LECTURER"||item.role==="STUDENT")){await page.locator('select[name="actor_subject_id"]').selectOption(account.subject_id);await page.locator('select[name="role"]').selectOption(account.role==="LECTURER"?"INSTRUCTOR":"STUDENT");await page.getByRole("button",{name:"Thêm thành viên",exact:true}).click();await managementConfirm(page);await expect(page.getByText("Đã phân công thành viên.",{exact:true})).toBeVisible();}
  checks.push("admin assigns separate lecturer and student");await page.screenshot({path:path.join(output,"admin.png"),fullPage:true});
  const teacher=await login("LECTURER");await teacher.page.locator("select").first().selectOption({label:`${classTitle} · Đang học`});await teacher.page.getByLabel("Tên buổi mới",{exact:true}).fill("Buổi 1 SQL joins");await teacher.page.getByRole("button",{name:"Thêm buổi",exact:true}).click();await expect(teacher.page.getByRole("heading",{name:"Buổi 1 SQL joins",exact:true})).toBeVisible();checks.push("teacher creates session in assigned offering");
  await teacher.page.getByText(/^Thêm bài giảng PDF(?: hoặc PowerPoint)?$/).click();await teacher.page.getByLabel("Tiêu đề bài giảng",{exact:true}).fill(lectureTitle);await teacher.page.getByLabel(/^File PDF(?: hoặc PPTX)?$/).setInputFiles({name:process.env.LEARNING_TEST_PPTX?"lecture.pptx":"sql-joins.pdf",mimeType:process.env.LEARNING_TEST_PPTX?"application/vnd.openxmlformats-officedocument.presentationml.presentation":"application/pdf",buffer:fixturePdf()});await teacher.page.getByRole("button",{name:"Tải và lưu nháp",exact:true}).click();await expect(teacher.page.getByRole("heading",{name:lectureTitle,exact:true})).toBeVisible();
  await teacher.page.getByText("Lịch sử phiên bản",{exact:true}).click();await expect(teacher.page.getByRole("button",{name:"Xem trước",exact:true})).toBeVisible({timeout:process.env.LEARNING_TEST_PPTX?140000:60000});await teacher.page.getByRole("button",{name:"Xem trước",exact:true}).click();await expect(teacher.page.locator(".learning-reader-viewport .page canvas").first()).toBeVisible({timeout:20000});checks.push(process.env.LEARNING_TEST_PPTX?"teacher uploads PowerPoint, real converter and scanner produce PDF preview":"teacher uploads PDF, worker processes it and viewer renders preview");
  if(process.env.LEARNING_TEST_PPTX){pptxSource=await verifyPptxSource(teacher.page,teacher.context);checks.push('PowerPoint original hash is preserved while content endpoint returns authenticated PDF rendition ranges');}
  await teacher.page.getByRole("button",{name:"Công bố",exact:true}).click();await expect(teacher.page.getByRole("button",{name:"Xác nhận",exact:true})).toBeDisabled();await teacher.page.getByLabel("Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.").check();await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();await expect(teacher.page.getByText("Đã cập nhật trạng thái công bố trên máy chủ.",{exact:true})).toBeVisible();checks.push("publication requires explicit confirmation");await teacher.page.locator(".learning-pdf-reader").screenshot({path:path.join(output,"teacher-reader-initial.png")});
  await readerTools(teacher.page);checks.push('PDF text search, lazy thumbnails, page rotation, outline panel and focus mode work');
  await teacher.page.getByText("Thêm chỉ dẫn đọc",{exact:true}).click();await teacher.page.locator('select[name="version_id"]').selectOption({index:1});await teacher.page.getByLabel("Trang cần đọc",{exact:true}).fill("1-2");await teacher.page.getByLabel("Mục đích",{exact:true}).fill("Đọc và chuẩn bị phép nối SQL");await teacher.page.getByLabel("Câu hỏi tự kiểm tra mỗi dòng một câu",{exact:true}).fill("Khi nào dùng LEFT JOIN?");await teacher.page.getByRole("button",{name:"Lưu chỉ dẫn",exact:true}).click();await expect(teacher.page.getByText("Đọc và chuẩn bị phép nối SQL",{exact:true})).toBeVisible();checks.push("teacher creates page-bound reading instruction");
  const student=await login("STUDENT",{width:390,height:844});await student.page.locator("select").first().selectOption({label:`${classTitle} · Đang học`});const firstPageStarted=performance.now();await student.page.getByRole("button",{name:"Đọc bài giảng",exact:true}).click();await expect(student.page.locator(".learning-reader-viewport .page canvas").first()).toBeVisible({timeout:20000});const firstPageMs=Math.round(performance.now()-firstPageStarted);await expect(student.page.getByRole("button",{name:"Công bố",exact:true})).toHaveCount(0);checks.push("student reads published PDF on mobile without teacher controls");
  await pinchReader(student.page,student.context);checks.push('CDP touch gesture changes PDF zoom within the viewer');
  await student.page.getByLabel("Cách xem PDF",{exact:true}).selectOption("horizontal");await expect(student.page.getByLabel("Cách xem PDF",{exact:true})).toHaveValue("horizontal");await student.page.getByLabel("Cách xem PDF",{exact:true}).selectOption("page");await student.page.getByLabel("Số trang",{exact:true}).fill("2");await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");const beforeZoom=await student.page.getByLabel("Mức phóng",{exact:true}).innerText();await student.page.getByRole("button",{name:"Phóng to",exact:true}).click();await expect(student.page.getByLabel("Mức phóng",{exact:true})).not.toHaveText(beforeZoom);await student.page.getByLabel("Cách xem PDF",{exact:true}).selectOption("vertical");await student.page.locator(".learning-pdf-reader").screenshot({path:path.join(output,"student-mobile.png")});const mobileTools=student.page.getByRole("button",{name:"Công cụ đọc",exact:true});await expect(mobileTools).toBeVisible();await expect(student.page.getByRole("button",{name:"Xoay",exact:true})).toBeHidden();const mobileToolbarHeight=await student.page.locator(".learning-reader-toolbar").evaluate(element=>element.getBoundingClientRect().height);if(mobileToolbarHeight>240)throw new Error("Collapsed mobile toolbar exceeds240px");checks.push("mobile advanced tools start collapsed and toolbar height is bounded");await mobileTools.click();await expect(student.page.getByRole("button",{name:"Xoay",exact:true})).toBeVisible();await student.page.getByRole("button",{name:"Đánh dấu trang này",exact:true}).click();await expect(student.page.getByText("Đã đánh dấu trang.",{exact:true})).toBeVisible();checks.push("mobile reader modes, physical page, zoom and bookmark work through real UI");
  await student.page.locator(".learning-pdf-reader").screenshot({path:path.join(output,"student-tools-mobile.png")});await teacher.page.locator(".learning-pdf-reader").screenshot({path:path.join(output,"teacher-reader.png")});
  await student.page.getByRole("button",{name:"Ghi chú cả trang",exact:true}).click();await student.page.getByLabel("Nội dung ghi chú",{exact:true}).fill("Ghi chú riêng của sinh viên kiểm thử");await student.page.getByRole("button",{name:"Lưu ghi chú riêng",exact:true}).click();await expect(student.page.getByText("Đã lưu ghi chú riêng.",{exact:true})).toBeVisible();
  if(pptxSource){const notes=await(await student.context.request.get(`${base}/v1/learning/me/annotations?version_id=${pptxSource.versionId}`)).json();expect(notes.items).toEqual(expect.arrayContaining([expect.objectContaining({rendition_id:pptxSource.renditionId,page_no:2})]));checks.push('PowerPoint annotation is stored on the same immutable PDF rendition');}
  await student.page.getByText("Đặt câu hỏi tại vị trí đang chọn",{exact:true}).click();await student.page.getByLabel("Câu hỏi",{exact:true}).fill("Vì sao LEFT JOIN giữ hàng bên trái?");await student.page.getByRole("button",{name:"Gửi câu hỏi",exact:true}).click();await expect(student.page.getByText("Đã gửi câu hỏi theo phạm vi chia sẻ bạn chọn.",{exact:true})).toBeVisible();
  await teacher.page.getByRole("button",{name:"Tải lại trao đổi",exact:true}).click();await expect(teacher.page.getByText("Vì sao LEFT JOIN giữ hàng bên trái?",{exact:true})).toBeVisible();await expect(teacher.page.getByText("Ghi chú riêng của sinh viên kiểm thử",{exact:true})).toHaveCount(0);const thread=teacher.page.getByText("Vì sao LEFT JOIN giữ hàng bên trái?",{exact:true}).locator("..");const replyText="Phép nối giữ hàng bảng trái và điền NULL khi không có hàng tương ứng.";await thread.getByLabel("Trả lời",{exact:true}).fill(replyText);await thread.getByRole("button",{name:"Gửi trả lời",exact:true}).click();await expect(thread.getByText(replyText,{exact:true})).toBeVisible();await student.page.getByRole("button",{name:"Tải lại trao đổi",exact:true}).click();await expect(student.page.getByText(replyText,{exact:true})).toBeVisible();checks.push("private student note stays private while instructor can answer a source-bound private question");
  const studentInstruction=student.page.getByRole("region",{name:"Chỉ dẫn đọc theo buổi"});
  await studentInstruction.getByRole("button",{name:"Mở trang 1–2",exact:true}).click();
  await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("1");
  await expect(student.page.locator(".learning-reader-viewport .page canvas").first()).toBeVisible();
  await studentInstruction.getByRole("button",{name:"Đánh dấu đã xem",exact:true}).click();
  await expect(studentInstruction.getByText("Đã đánh dấu xem",{exact:true})).toBeVisible();
  await student.page.getByLabel("Số trang",{exact:true}).fill("2");
  let classmate=null;
  if(accounts.filter(item=>item.role==="STUDENT").length>1){
    classmate=await login("STUDENT",{width:1280,height:900},1);
    await classmate.page.locator("select").first().selectOption({label:`${classTitle} · Đang học`});
    await classmate.page.getByRole("button",{name:"Đọc bài giảng",exact:true}).click();
    await expect(classmate.page.getByRole("button",{name:"Đánh dấu đã xem",exact:true})).toBeVisible();
    await expect(classmate.page.getByText("Chưa có câu hỏi được phép xem.",{exact:true})).toBeVisible();
    await student.page.getByRole("button",{name:"Xem trước khi chia sẻ với lớp",exact:true}).click();
    const modal=student.page.getByRole("dialog",{name:"Xác nhận phạm vi câu hỏi"});
    await expect(modal.getByText("Vì sao LEFT JOIN giữ hàng bên trái?",{exact:true})).toBeVisible();
    await expect(modal.getByRole("button",{name:"Xác nhận đổi phạm vi"})).toBeDisabled();
    await modal.getByRole("checkbox").check();await modal.getByRole("button",{name:"Xác nhận đổi phạm vi"}).click();
    await expect(student.page.getByText("Đã chia sẻ câu hỏi với lớp. Các phản hồi riêng vẫn được giữ riêng.",{exact:true})).toBeVisible();
    await classmate.page.getByRole("button",{name:"Tải lại trao đổi",exact:true}).click();
    await expect(classmate.page.getByText("Vì sao LEFT JOIN giữ hàng bên trái?",{exact:true})).toBeVisible();
    await expect(classmate.page.getByText("Phép nối giữ hàng bảng trái và điền NULL khi không có hàng tương ứng.",{exact:true})).toHaveCount(0);
    const notice=classmate.page.getByText(/^Cập nhật học liệu ·/);
    await notice.click();await classmate.page.getByRole("button",{name:"Tải lại thông báo",exact:true}).click();
    const currentNotice=classmate.page.getByRole("listitem").filter({hasText:lectureTitle}).filter({hasText:"Phạm vi một câu hỏi đã thay đổi"});
    await expect(currentNotice).toBeVisible();
    await currentNotice.getByRole("button",{name:"Mở trang câu hỏi",exact:true}).click();
    await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");
    await classmate.page.getByLabel("Số trang",{exact:true}).fill("1");
    await classmate.page.getByRole("button",{name:"Mở trang 2 của câu hỏi",exact:true}).click();
    await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");
    checks.push("author confirms scope; classmate gets the question and source notice but never the private reply");
  }
  const shareableNote="Ghi chú thứ hai cần hỏi giảng viên";
  const expandReaderTools=student.page.getByRole("button",{name:"Công cụ đọc",exact:true});
  if(await expandReaderTools.isVisible())await expandReaderTools.click();
  await student.page.getByRole("button",{name:"Ghi chú cả trang",exact:true}).click();
  await student.page.getByLabel("Nội dung ghi chú",{exact:true}).fill(shareableNote);
  await student.page.getByRole("button",{name:"Lưu ghi chú riêng",exact:true}).click();
  const noteItem=student.page.getByRole("listitem").filter({hasText:shareableNote}).filter({has:student.page.getByRole("button",{name:"Xem trước khi gửi ghi chú",exact:true})});
  await noteItem.getByRole("button",{name:"Xem trước khi gửi ghi chú",exact:true}).click();
  const shareNote=student.page.getByRole("dialog",{name:"Gửi bản sao ghi chú cho giảng viên"});
  await expect(shareNote.getByText(shareableNote,{exact:true})).toBeVisible();
  const confirmNote=shareNote.getByRole("button",{name:"Xác nhận gửi bản sao",exact:true});
  await expect(confirmNote).toBeDisabled();
  await shareNote.getByRole("checkbox").check();
  await confirmNote.click();
  await expect(student.page.getByText("Đã gửi một bản sao cho giảng viên. Ghi chú gốc vẫn là của riêng bạn.",{exact:true})).toBeVisible();
  await teacher.page.getByRole("button",{name:"Tải lại trao đổi",exact:true}).click();
  await expect(teacher.page.getByText(shareableNote,{exact:true})).toBeVisible();
  if(classmate){
    await classmate.page.getByRole("button",{name:"Tải lại trao đổi",exact:true}).click();
    await expect(classmate.page.getByText(shareableNote,{exact:true})).toHaveCount(0);
  }
  checks.push("the student previews a note copy for instructors and classmates cannot see it");
  const teacherInstruction=teacher.page.getByRole("region",{name:"Chỉ dẫn đọc theo buổi"});
  await teacherInstruction.getByRole("button",{name:"Sửa chỉ dẫn",exact:true}).click();
  await teacherInstruction.getByLabel("Mục đích",{exact:true}).fill("Ôn lại phép nối SQL");
  await teacherInstruction.getByRole("button",{name:"Lưu chỉ dẫn",exact:true}).click();
  await expect(teacherInstruction.getByText("Ôn lại phép nối SQL",{exact:true})).toBeVisible();
  await teacherInstruction.getByText("Lịch sử chỉnh sửa chỉ dẫn",{exact:true}).click();
  await expect(teacherInstruction.getByText("Đọc và chuẩn bị phép nối SQL",{exact:true})).toBeVisible();
  checks.push("reading instruction opens its page range, tracks each learner independently, and retains revisions");
  await teacher.page.getByRole("button",{name:"Bắt đầu trình bày tài liệu này",exact:true}).click();
  await expect(teacher.page.getByRole("button",{name:"Kết thúc trình bày",exact:true})).toBeVisible();
  for(const follower of [student,classmate].filter(Boolean)){
    await follower.page.getByRole("button",{name:"Tải lại phiên trình bày",exact:true}).click();
    await follower.page.getByRole("button",{name:/Chọn phiên trình bày/}).first().click({timeout:20000});
    await follower.page.getByRole("button",{name:"Theo giảng viên",exact:true}).click();
  }
  await teacher.page.getByLabel("Số trang",{exact:true}).fill("3");
  await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("3",{timeout:15000});
  if(classmate){
    await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("3",{timeout:15000});
    await classmate.context.setOffline(true);
    await expect(classmate.page.getByText(/^Mất kết nối phiên trình bày\./)).toBeVisible();
    await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");
    await classmate.context.setOffline(false);
  }
  await student.page.getByRole("button",{name:"Tạm rời giảng viên",exact:true}).click();
  await student.page.getByLabel("Số trang",{exact:true}).fill("2");
  await teacher.page.getByLabel("Số trang",{exact:true}).fill("1");
  await expect(teacher.page.getByText("Đang trình bày trang 1.",{exact:false})).toBeVisible();
  if(classmate){
    await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");
    await classmate.page.getByRole("button",{name:"Tải lại phiên trình bày",exact:true}).click();
    await classmate.page.getByRole("button",{name:/Chọn phiên trình bày/}).first().click();
    await classmate.page.getByRole("button",{name:/^(Theo giảng viên|Quay lại giảng viên)$/}).click();
    await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("1",{timeout:15000});
    checks.push("offline presentation restores personal page and reconnecting requires explicit opt-in");
  }
  await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");
  await student.page.getByRole("button",{name:"Quay lại giảng viên",exact:true}).click();
  await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("1",{timeout:10000});
  await teacher.page.getByRole("button",{name:"Kết thúc trình bày",exact:true}).click();
  if(classmate)await expect(classmate.page.getByLabel("Số trang",{exact:true})).toHaveValue("2",{timeout:15000});
  checks.push(classmate?"two students opt in independently, one pauses, and ending restores both personal pages":"live instructor presentation follows only after opt-in and preserves independent reading when paused");
  await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("2",{timeout:15000});await student.page.getByRole("button",{name:"Đóng trình đọc",exact:true}).click();await expect(student.page.locator(".learning-pdf-reader")).toHaveCount(0);await student.page.getByRole("button",{name:"Đọc bài giảng",exact:true}).click();await expect(student.page.locator(".learning-reader-viewport .page canvas").first()).toBeVisible();await expect(student.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");await expect(student.page.getByText("Ghi chú riêng của sinh viên kiểm thử",{exact:true})).toBeVisible();checks.push("ending presentation restores personal page and reopening keeps saved state and private annotation");
  await student.page.screenshot({path:path.join(output,"student-discussion-mobile.png"),fullPage:false});
  await student.page.setViewportSize({width:360,height:800});
  await student.page.getByRole('button',{name:'Vừa rộng',exact:true}).click();
  await expect.poll(()=>student.page.locator('.learning-reader-viewport').evaluate(host=>{
    const current=host.querySelector('.page[data-page-number="2"]');
    return Boolean(current&&current.clientWidth<=host.clientWidth+1);
  })).toBe(true);
  await expect(student.page.getByRole('button',{name:'Công cụ đọc',exact:true})).toBeVisible();
  const narrowOverflow=await student.page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
  if(narrowOverflow)throw new Error('360px shell has horizontal overflow');
  await student.page.screenshot({path:path.join(output,'student-360.png'),fullPage:false});
  await student.page.locator('.learning-pdf-reader').screenshot({path:path.join(output,'reader-360.png')});
  checks.push('mobile shell and collapsed reader tools fit 360px viewport');
  await student.page.setViewportSize({width:390,height:844});
  const overflow=await student.page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);if(overflow)throw new Error("Mobile shell has horizontal overflow");checks.push("mobile shell fits 390px viewport");
  if(process.env.LEARNING_TEST_READER_SYNC==="1"){
    const source=await teacher.page.getByRole("link",{name:"Tải bản gốc",exact:true}).getAttribute("href");
    const versionId=source?.match(/^\/v1\/learning\/versions\/([a-f0-9-]{36})\/download$/)?.[1];
    if(!versionId)throw new Error("Missing reader state source");
    const endpoint=`${base}/v1/learning/me/reader-state/${versionId}`;
    const pageInput=student.page.getByLabel("Số trang",{exact:true});
    const readPosition=async()=>await(await student.context.request.get(endpoint)).json();
    await expect.poll(async()=>(await readPosition()).page_no,{timeout:12000}).toBe(2);
    await student.page.getByLabel("Cách xem PDF",{exact:true}).selectOption("page");
    await student.context.setOffline(true);
    await pageInput.fill("1");
    await expect(student.page.getByRole("button",{name:"Thử lưu lại vị trí",exact:true})).toBeVisible({timeout:12000});
    await expect(student.page.locator('.learning-reader-viewport .page[data-page-number="1"] canvas').first()).toBeVisible();
    await student.context.setOffline(false);
    await expect.poll(async()=>(await readPosition()).page_no,{timeout:12000}).toBe(1);
    checks.push("offline view retains rendered content and reconnect saves the queued position");

    const baseline=await readPosition();
    const remote=await student.context.request.put(endpoint,{
      headers:{"X-Campus-Request":"learning","X-Campus-Reader-Actor":student.account.subject_id},
      data:{page_no:3,revision:baseline.revision},
    });
    expect(remote.status()).toBe(200);
    await pageInput.fill("2");
    await expect(student.page.getByText("Vị trí đọc đã thay đổi trên thiết bị khác. Chọn vị trí muốn giữ.",{exact:true})).toBeVisible({timeout:12000});
    expect((await readPosition()).page_no).toBe(3);
    await student.page.getByRole("button",{name:"Giữ vị trí trên thiết bị này",exact:true}).click();
    await expect.poll(async()=>(await readPosition()).page_no,{timeout:12000}).toBe(2);
    checks.push("stale reader cannot overwrite a newer revision until the reader chooses their local position");

    const toolbar=student.page.getByRole("toolbar",{name:"Công cụ đọc PDF"});
    if(await toolbar.getByRole("button",{name:"Công cụ đọc",exact:true}).isVisible()){
      await toolbar.getByRole("button",{name:"Công cụ đọc",exact:true}).click();
    }
    await toolbar.getByRole("button",{name:"Đánh dấu",exact:true}).click();
    await student.page.getByLabel("Nhãn đánh dấu",{exact:true}).fill("Bảng ví dụ");
    await student.page.getByRole("button",{name:"Lưu đánh dấu",exact:true}).click();
    await expect(student.page.getByRole("button",{name:"Bảng ví dụ",exact:true})).toBeVisible();
    await pageInput.fill("1");
    await student.page.getByRole("button",{name:"Bảng ví dụ",exact:true}).click();
    await expect(pageInput).toHaveValue("2");
    checks.push("optional bookmark label is stored and opens the exact page");
  }
  if(process.env.LEARNING_TEST_VERSION_HISTORY==="1"){
    const source=await teacher.page.getByRole("link",{name:"Tải bản gốc",exact:true}).getAttribute("href");
    const versionId=source?.match(/^\/v1\/learning\/versions\/([a-f0-9-]{36})\/download$/)?.[1];
    if(!versionId)throw new Error("Missing original source");
    const old=(await student.context.request.get(base+source));
    expect(old.status()).toBe(200);
    const originalHash=createHash("sha256").update(await old.body()).digest("hex");
    const notes=await(await student.context.request.get(`${base}/v1/learning/me/annotations?version_id=${versionId}`)).json();
    const anchor=notes.items.find(item=>item.page_no===2&&item.body==="Ghi chú riêng của sinh viên kiểm thử");
    if(!anchor)throw new Error("Private note not bound to page 2");
    // Capture the reader's position after the responsive viewport checks.
    await student.page.getByLabel("Cách xem PDF",{exact:true}).selectOption("page");
    const currentPage=student.page.getByLabel("Số trang",{exact:true});
    await currentPage.fill("2");
    await expect(currentPage).toHaveValue("2");
    await teacher.page.getByText("Tải phiên bản mới",{exact:true}).click();
    const replacement=teacher.page.getByText("Tải phiên bản mới",{exact:true}).locator("..");
    const changed=makePdf(true);
    expect(createHash("sha256").update(changed).digest("hex")).not.toBe(originalHash);
    await replacement.getByLabel(/^File PDF(?: hoặc PPTX)?$/).setInputFiles({name:"updated.pdf",mimeType:"application/pdf",buffer:changed});
    await replacement.getByRole("button",{name:"Tải phiên bản",exact:true}).click();
    const next=teacher.page.getByText(/^Phiên bản 2 ·/).locator("..");
    await expect(next.getByRole("button",{name:"Xem trước lịch",exact:true})).toBeVisible({timeout:60000});
    await expect(teacher.page.getByText("Múi giờ của lớp Asia/Bangkok",{exact:true})).toBeVisible();
    await next.getByLabel("Hẹn giờ công bố",{exact:true}).fill("2099-12-01T09:30");
    const scheduleResponse=teacher.page.waitForResponse(response=>response.url().endsWith("/publication-preview")&&response.request().method()==="POST");
    await next.getByRole("button",{name:"Xem trước lịch",exact:true}).click();
    const schedule=(await (await scheduleResponse).json());
    expect(schedule.payload.scheduled_at).toBe("2099-12-01T02:30:00Z");
    await expect(teacher.page.getByRole("dialog").getByText(/Tài liệu sẽ được công bố lúc .*Asia\/Bangkok/)).toBeVisible();
    await teacher.page.getByLabel("Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.").check();
    await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();
    await expect(next.getByText(/^Phiên bản 2 · .*Đã hẹn công bố$/)).toBeVisible();
    expect((await student.context.request.get(`${base}/v1/learning/versions/${schedule.target_id}/content`,{headers:{Range:"bytes=0-15"}})).status()).toBe(404);
    await next.getByRole("button",{name:"Hủy lịch công bố",exact:true}).click();
    await teacher.page.getByLabel("Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.").check();
    await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();
    await expect(next.getByText(/^Phiên bản 2 · .*Bản nháp$/)).toBeVisible();
    checks.push("the UTC browser schedules in class time and students cannot read bytes before publication");
    await next.getByRole("button",{name:"Công bố",exact:true}).click({timeout:60000});
    await teacher.page.getByLabel("Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.").check();
    await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();
    await expect(next.getByText(/^Phiên bản 2 · .*Đã công bố$/)).toBeVisible();
    await student.page.evaluate(()=>window.dispatchEvent(new Event("focus")));
    await expect(student.page.getByText("Bạn đang đọc một phiên bản khác với bản hiện hành.",{exact:true})).toBeVisible();
    await expect(currentPage).toHaveValue("2");
    const oldAgain=await student.context.request.get(base+source);
    expect(createHash("sha256").update(await oldAgain.body()).digest("hex")).toBe(originalHash);
    const deep=`${base}/learning?version_id=${versionId}&page_no=2&anchor_id=${anchor.id}`;
    const second=await login("STUDENT",{width:1280,height:900},0,"-second");
    await second.page.goto(deep);
    await expect(second.page.getByLabel("Số trang",{exact:true})).toHaveValue("2");
    await expect(second.page.locator('.learning-reader-annotation[data-focused="true"]')).toBeVisible();
    await second.page.getByRole("button",{name:"Mở bản hiện hành",exact:true}).click();
    await expect(second.page.getByRole("region",{name:"Trình đọc bài giảng"}).getByText("Phiên bản 2",{exact:true})).toBeVisible();
    await expect(second.page.getByText("Ghi chú riêng của sinh viên kiểm thử",{exact:true})).toHaveCount(0);
    checks.push("old deep link opens its exact page and private annotation after replacement; student chooses whether to switch");
    await second.page.getByLabel("Số trang",{exact:true}).fill("1");
    const tabCount=second.context.pages().length;
    const externalLink=second.page.locator('.annotationLayer a[title="Liên kết ngoài tới campus-links.invalid"]');
    await expect(externalLink).toHaveAttribute("href","#");
    await externalLink.click();
    const linkWarning=second.page.getByRole("dialog",{name:"Mở liên kết ngoài?"});
    await expect(linkWarning.getByRole("link",{name:"Mở trang web"})).toHaveAttribute("href","https://campus-links.invalid/reading");
    await linkWarning.getByRole("button",{name:"Quay lại tài liệu"}).click();
    await expect(linkWarning).toHaveCount(0);
    expect(second.context.pages()).toHaveLength(tabCount);
    await second.context.route("https://campus-links.invalid/reading",route=>route.fulfill({body:"Local test response"}));
    await externalLink.click();
    const [opened]=await Promise.all([second.page.waitForEvent("popup"),linkWarning.getByRole("link",{name:"Mở trang web"}).click()]);
    await expect(opened.getByText("Local test response")).toBeVisible();
    expect(await opened.evaluate(()=>window.opener===null)).toBe(true);
    await opened.close();
    checks.push("PDF web link warns before navigating, cancellation opens nothing, and confirming isolates the destination tab");
    await next.getByRole("button",{name:"Thu hồi",exact:true}).click();
    const publicationConsent=teacher.page.getByLabel("Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.");
    await publicationConsent.check();
    await teacher.page.getByLabel("Bản hiện hành sau khi thu hồi").selectOption({label:"Phiên bản 1 đã công bố"});
    await expect(publicationConsent).toBeEnabled();
    await expect(publicationConsent).not.toBeChecked();
    await publicationConsent.check();
    await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();
    await expect(next.getByText(/^Phiên bản 2 · .*Đã thu hồi$/)).toBeVisible();
    const fallback=await student.context.request.get(`${base}/v1/learning/versions/${versionId}`);
    expect(fallback.ok()).toBe(true);
    expect((await fallback.json()).current_published_version_id).toBe(versionId);
    checks.push("retracting the current version can make an older published version current with fresh confirmation");
    await next.getByRole("button",{name:"Công bố",exact:true}).click();
    await publicationConsent.check();
    await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();
    await expect(next.getByText(/^Phiên bản 2 · .*Đã công bố$/)).toBeVisible();
    await teacher.page.getByText(/^Phiên bản 1 · .*Đã công bố$/).locator("..").getByRole("button",{name:"Thu hồi",exact:true}).click();
    await teacher.page.getByLabel("Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.").check();
    await teacher.page.getByRole("button",{name:"Xác nhận",exact:true}).click();
    await expect(teacher.page.getByText(/^Phiên bản 1 · .*Đã thu hồi$/)).toBeVisible();
    await second.page.goto(deep);
    await expect(second.page.getByText("Phiên bản trong liên kết không còn được cung cấp.",{exact:true})).toBeVisible();
    await expect(second.page.getByRole("region",{name:"Trình đọc bài giảng"})).toHaveCount(0);
    expect((await student.context.request.get(`${base}/v1/learning/versions/${versionId}/content`,{headers:{Range:"bytes=0-15"}})).status()).toBe(404);
    checks.push("retraction rejects the old link and byte ranges without silently substituting the new version");
  }
  if(errors.length)throw new Error(`Browser page errors: ${errors.join(" | ")}`);
  fs.writeFileSync(path.join(output,"report.json"),JSON.stringify({status:"passed",base_url:base,checks,page_errors:errors,first_page_ms:firstPageMs,first_page_corpus:{synthetic:true,byte_size:fixturePdf().length,sha256:createHash("sha256").update(fixturePdf()).digest("hex"),source:process.env.LEARNING_TEST_PPTX?"PowerPoint with Vietnamese, native table/chart and hidden equation slide":process.env.LEARNING_TEST_PDF?"Vietnamese, landscape, vector and raster corpus":"in-script three-page PDF",performance_benchmark:false}},null,2),{flag:"wx"});console.log(JSON.stringify({status:"passed",checks:checks.length,output}));
}catch(error){const safeError=safe(error);for(const context of contexts){for(const [index,page]of context.pages().entries()){try{await page.screenshot({path:path.join(output,`failure-${contexts.indexOf(context)}-${index}.png`),fullPage:true});}catch{}}}fs.writeFileSync(path.join(output,"report.json"),JSON.stringify({status:"failed",base_url:base,checks,error:safeError,page_errors:errors},null,2),{flag:"wx"});console.log(JSON.stringify({status:"failed",checks:checks.length,output,error:safeError}));process.exitCode=1;}finally{for(const context of contexts)await context.close();}

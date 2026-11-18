// Generate a retained, synthetic Vietnamese/landscape/scan PDF using local Chromium.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';

const repo=fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'));
const output=path.join(repo,'.tooling','learning-reader-corpus-20261105-01');
if(fs.existsSync(output)||fs.realpathSync(path.dirname(output))!==path.join(repo,'.tooling'))throw new Error('A new workspace corpus directory is required');
fs.mkdirSync(output);const temp=path.join(output,'temp');fs.mkdirSync(temp);process.env.TEMP=temp;process.env.TMP=temp;
const context=await chromium.launchPersistentContext(path.join(output,'browser-profile-corpus'),{headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const page=await context.newPage();
 await page.setContent(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>
 @page{size:A4;margin:20mm} @page wide{size:A4 landscape;margin:20mm}
 body{font-family:Arial,sans-serif;font-size:16pt;color:#111}section{break-after:page}section:last-child{break-after:auto}.wide{page:wide}
 h1{font-size:24pt;color:#163b67}table{border-collapse:collapse}td,th{border:1px solid #333;padding:12px}img{width:100%}
 </style></head><body>
 <section><h1>Buổi 1: Cơ sở dữ liệu</h1><p>Học liệu tiếng Việt: giảng viên, sinh viên, nghiên cứu và sáng tạo.</p><p>SQL JOIN kết hợp các hàng theo điều kiện nối.</p><p>Công thức: E = mc²; ∑ xᵢ = x₁ + x₂ + … + xₙ.</p><table><tr><th>Mã</th><th>Họ và tên</th></tr><tr><td>SV01</td><td>Nguyễn Thị Ánh</td></tr><tr><td>SV02</td><td>Đặng Văn Đức</td></tr></table></section>
 <section class="wide"><h1>Buổi 2: SQL JOIN trên trang ngang</h1><p>LEFT JOIN giữ hàng ở bảng trái khi không có bản ghi khớp ở bảng phải.</p><svg width="680" height="220" viewBox="0 0 680 220"><rect x="10" y="20" width="220" height="150" fill="#dcf2ff" stroke="#163b67"/><rect x="440" y="20" width="220" height="150" fill="#e8f7dc" stroke="#39621e"/><path d="M230 95 H440" stroke="#163b67" stroke-width="4"/><text x="35" y="90" font-size="22">Bảng sinh viên</text><text x="460" y="90" font-size="22">Bảng lớp</text><text x="275" y="75" font-size="20">JOIN</text></svg></section>
 <section><h1>Bản scan minh họa</h1><img id="scan" alt="" /></section>
 </body></html>`);
 await page.evaluate(()=>{
   const canvas=document.createElement('canvas');canvas.width=900;canvas.height=1100;
   const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,900,1100);ctx.fillStyle='#14345a';ctx.font='32px Arial';
   ctx.fillText('Bản scan: chỉ có hình ảnh',40,100);ctx.fillText('Nghiên cứu – sáng tạo – đề xuất',40,180);
   ctx.strokeStyle='#14345a';ctx.strokeRect(40,240,800,300);ctx.fillText('x² + y² = r²',80,340);
   document.querySelector('#scan').src=canvas.toDataURL('image/png');
 });
 await page.evaluate(()=>Promise.all([...document.images].map(image=>image.decode())));
 const bytes=await page.pdf({printBackground:true,preferCSSPageSize:true,tagged:true,outline:true});
 fs.writeFileSync(path.join(output,'vietnamese-landscape-scan.pdf'),bytes,{flag:'wx'});
 fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify({synthetic:true,sha256:createHash('sha256').update(bytes).digest('hex'),byte_size:bytes.length,expected_pages:3,expected_text:['Học liệu tiếng Việt','Nguyễn Thị Ánh','Đặng Văn Đức','LEFT JOIN'],scan_image_text:'Nghiên cứu – sáng tạo – đề xuất',source:'locally authored HTML, vector table/diagram, generated raster image'},null,2),{flag:'wx'});
 console.log(JSON.stringify({output,bytes:bytes.length}));
}finally{await context.close();}

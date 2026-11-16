"""Acquire one public attachment actually linked by the retained FIT source page."""
import asyncio
from datetime import UTC, datetime
import hashlib
import io
from urllib.parse import urljoin, urlsplit

import httpx
from pypdf import PdfReader
import pypdfium2 as pdfium

from huce_document_pipeline import BASE, ROOT, checked, event, preflight, rel, save, sha, stamp
from huce_source_registry import public_address


async def main():
    event('preflight',preflight())
    publisher=checked(ROOT/'data/huce-discovery-20261020/objects/365e16404a1c72f83bdef1bb3916297ac0e4a498a884ce9ad1e516509329ea31')
    assert sha(publisher.read_bytes())==publisher.name
    did='1Zu1VbkLNmQicqlzVEYUIbnfgCk9iKlW9'
    source_url='https://drive.google.com/file/d/'+did+'/view'
    assert source_url in publisher.read_text(encoding='utf8')
    url='https://drive.google.com/uc?export=download&id='+did
    receipt={'drive_id':did,'url':source_url,'publisher_url':'https://fit.huce.edu.vn/chuong-trinh-dao-tao',
             'publisher_file':rel(publisher),'publisher_sha256':publisher.name,
             'collected_at':datetime.now(UTC).isoformat(),'rag_admission':'not_admitted_pending_all_page_content_review'}
    async with httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False) as client:
        for _ in range(4):
            parsed=urlsplit(url)
            assert parsed.scheme=='https' and not parsed.username and not parsed.password and parsed.port in (None,443)
            assert parsed.hostname in {'drive.google.com','drive.usercontent.google.com'}
            await asyncio.to_thread(public_address,parsed.hostname)
            async with client.stream('GET',url) as response:
                if response.is_redirect:
                    url=urljoin(url,response.headers['location']);continue
                response.raise_for_status()
                body=bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    assert len(body)<=20_000_000,'attachment size cap exceeded'
                assert body.startswith(b'%PDF'),'public PDF required; no login or HTML payload admitted'
                break
        else:raise RuntimeError('redirect cap exceeded')
    digest=hashlib.sha256(body).hexdigest()
    original=checked(ROOT/'data/huce-discovery-20261020/objects'/digest)
    if original.exists():assert sha(original.read_bytes())==digest
    else:
        with original.open('xb') as stream:stream.write(body)
    receipt.update(source_file=rel(original),source_sha256=digest,bytes=len(body),final_download_url=url)
    # Commit acquisition evidence before extraction, so a later render failure is resumable.
    event('it-attachment-acquired',receipt)
    pdf=PdfReader(io.BytesIO(body));assert 0<len(pdf.pages)<=100
    dest=checked(BASE/'attachments'/did/digest)
    dest.mkdir(parents=True,exist_ok=True)
    pages=[]
    with pdfium.PdfDocument(str(original)) as renderer:
        assert len(renderer)==len(pdf.pages)
        for number,page in enumerate(pdf.pages,1):
            data=checked(dest/f'page-{number}.json');image=checked(dest/f'page-{number}.png')
            if not data.exists():save(data,{'page':number,'text':page.extract_text() or ''})
            if not image.exists():
                rp=renderer[number-1];bitmap=rp.render(scale=2700/max(rp.get_size()))
                with image.open('xb') as stream:bitmap.to_pil().save(stream,format='PNG')
                bitmap.close();rp.close()
            pages.append({'page':number,'data':rel(data),'data_sha256':sha(data.read_bytes()),
                          'image':rel(image),'image_sha256':sha(image.read_bytes())})
    receipt.update(page_count=len(pages),pages=pages)
    target=checked(dest/('acquisition-'+stamp()+'.json'));save(target,receipt)
    print({'acquisition':rel(target),'pages':len(pages),'sha256':digest,'rag_admitted':False},flush=True)


if __name__=='__main__':asyncio.run(main())

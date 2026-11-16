"""Bounded public source refresh and explicitly linked PDF acquisition."""
import argparse
import asyncio
from datetime import UTC, datetime
import io
from urllib.parse import urljoin, urlsplit

import httpx
from pypdf import PdfReader
import pypdfium2 as pdfium

from huce_document_pipeline import ROOT, BASE, checked, event, preflight, read, rel, save, sha, stamp
from huce_source_registry import official, public_address, Page


async def fetch(client,url,drive=False):
    for _ in range(5):
        parsed=urlsplit(url)
        assert parsed.scheme=='https' and not parsed.username and not parsed.password and parsed.port in (None,443)
        assert parsed.hostname in {'drive.google.com','drive.usercontent.google.com'} if drive else official(url)
        await asyncio.to_thread(public_address,parsed.hostname)
        async with client.stream('GET',url) as response:
            if response.is_redirect:
                url=urljoin(url,response.headers['location']);continue
            response.raise_for_status();data=bytearray()
            async for block in response.aiter_bytes():
                data.extend(block);assert len(data)<=20_000_000
            return bytes(data),url,response.headers.get('content-type')
    raise RuntimeError('redirect cap exceeded')


def retain(data):
    digest=sha(data);target=checked(ROOT/'data/huce-discovery-20261020/objects'/digest)
    if target.exists():assert sha(target.read_bytes())==digest
    else:
        with target.open('xb') as stream:stream.write(data)
    return target,digest


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--web',nargs='+');parser.add_argument('--pdf-spec')
    args=parser.parse_args();assert bool(args.web)!=bool(args.pdf_spec)
    event('preflight',preflight());results=[]
    async with httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False) as client:
        if args.web:
            for url in args.web:
                data,final,kind=await fetch(client,url)
                assert 'html' in (kind or '')
                original,digest=retain(data);page=Page();page.feed(data.decode('utf8'))
                results.append({'url':url,'final_url':final,'source_file':rel(original),'source_sha256':digest,
                    'content_type':kind,'links':page.links,'rag_admission':'not_admitted'})
        else:
            for entry in read(ROOT/args.pdf_spec)['pdfs']:
                publisher=checked(ROOT/entry['publisher_file'])
                assert sha(publisher.read_bytes())==entry['publisher_sha256']
                assert entry['linked_url'] in publisher.read_text(encoding='utf8')
                did=entry['drive_id'];assert all(c.isalnum() or c in '_-' for c in did) and len(did)>10
                data,final,kind=await fetch(client,'https://drive.google.com/uc?export=download&id='+did,drive=True)
                assert data.startswith(b'%PDF'),'public PDF required; no login bypass'
                original,digest=retain(data);dest=checked(BASE/'attachments'/did/digest);dest.mkdir(parents=True,exist_ok=True)
                result=dict(entry,source_file=rel(original),source_sha256=digest,final_url=final,
                    collected_at=datetime.now(UTC).isoformat(),rag_admission='not_admitted')
                event('it-english-pdf-acquired',result)
                reader=PdfReader(io.BytesIO(data));assert 0<len(reader.pages)<=100
                pages=[]
                with pdfium.PdfDocument(str(original)) as renderer:
                    assert len(renderer)==len(reader.pages)
                    for number,page in enumerate(reader.pages,1):
                        text=checked(dest/f'page-{number}.json');image=checked(dest/f'page-{number}.png')
                        if not text.exists():save(text,{'page':number,'text':page.extract_text() or ''})
                        if not image.exists():
                            rp=renderer[number-1];bitmap=rp.render(scale=2700/max(rp.get_size()))
                            with image.open('xb') as stream:bitmap.to_pil().save(stream,format='PNG')
                            bitmap.close();rp.close()
                        pages.append({'page':number,'data':rel(text),'data_sha256':sha(text.read_bytes()),'image':rel(image),'image_sha256':sha(image.read_bytes())})
                result.update(pages=pages,page_count=len(pages));results.append(result)
    file=checked(BASE/('it-english-acquisition-'+stamp()+'.json'))
    save(file,{'acquired_at':datetime.now(UTC).isoformat(),'results':results,'not_admitted':True})
    print({'receipt':rel(file),'sources':[{'url':r.get('url',r.get('linked_url')),'sha256':r['source_sha256'],'pages':r.get('page_count')} for r in results]},flush=True)


if __name__=='__main__':asyncio.run(main())

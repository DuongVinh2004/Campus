"""Read the one anonymous PDF directly embedded in the retained HUCE notice."""
import hashlib
from urllib.parse import urlsplit, urljoin
import httpx
from huce_source_registry import ROOT, checked, save, public_address

def main():
    out = checked(ROOT / 'data/huce-discovery-20261020/reconciliation-20261021-v3/stem-attachment.pdf')
    if out.exists():
        raise FileExistsError(out)
    url = 'https://drive.google.com/uc?export=download&id=15aajVthfvwJoRiaBFZvsje03VsAxrXci'
    history = []
    with httpx.Client(timeout=25, trust_env=False, follow_redirects=False) as client:
        for _ in range(4):
            host = urlsplit(url).hostname
            if host not in {'drive.google.com', 'drive.usercontent.google.com'}:
                raise ValueError('unreviewed redirect or login barrier')
            public_address(host)
            with client.stream('GET', url) as response:
                history.append({'url':url,'status':response.status_code})
                if response.is_redirect:
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data)>20_000_000:
                        raise ValueError('existing acquisition size cap')
                if not data.startswith(b'%PDF'):
                    raise ValueError('not an anonymous PDF')
                with out.open('xb') as stream:
                    stream.write(data)
                save(out.with_suffix('.receipt.json'), {'source_html':'data/huce-discovery-20261020/objects/e6573329b27b79d3dfb31f5620d6e5b5ed8beb70aabaac6a80a6fc79f0bae1a5', 'history':history,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
                print(out)
                return
        raise ValueError('redirect cap')

if __name__ == '__main__':
    main()

import {expect,it,vi} from 'vitest';
import {LearningGateway} from './learning-gateway';
const material='00000000-0000-4000-8000-000000000001';
const intent='00000000-0000-4000-8000-000000000002';
const version='00000000-0000-4000-8000-000000000003';
const ok=(value:unknown)=>new Response(JSON.stringify(value));
it('recovers a committed complete response through its original intent without creating or streaming again',async()=>{
  const calls:{path:string;method:string;key:string|null}[]=[];let completed=false;
  const fetcher=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
    const path=String(input);calls.push({path,method:init?.method??'GET',key:new Headers(init?.headers).get('Idempotency-Key')});
    if(path.endsWith('/upload-intents'))return ok({id:intent});
    if(path.endsWith('/content'))return ok({state:'RECEIVED'});
    if(path.endsWith('/complete')){completed=true;throw new Error('Lost complete acknowledgement');}
    if(path.endsWith('/upload-intents/'+intent))return ok({id:intent,material_id:material,state:'RECEIVED',version_id:completed?version:undefined});
    if(path.endsWith('/versions/'+version))return ok({id:version,version_no:2,processing_state:'QUEUED'});
    throw new Error('Unexpected request');
  });
  const gateway=new LearningGateway(fetcher),file=new File(['synthetic'],'audit.pdf',{type:'application/pdf'});
  const attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID()};
  await expect(gateway.upload(material,file,undefined,undefined,attempt)).rejects.toThrow();
  expect((await gateway.upload(material,file,undefined,undefined,attempt)).id).toBe(version);
  expect(calls.filter(c=>c.path.endsWith('/upload-intents'))).toHaveLength(1);expect(calls.filter(c=>c.path.endsWith('/content'))).toHaveLength(1);expect(calls.filter(c=>c.path.endsWith('/complete'))).toHaveLength(1);
});
it('completes an acknowledged server receipt after a lost content response without streaming again',async()=>{
  const calls:{path:string;key:string|null}[]=[];
  const fetcher=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
    const path=String(input);calls.push({path,key:new Headers(init?.headers).get('Idempotency-Key')});
    if(path.endsWith('/upload-intents'))return ok({id:intent});
    if(path.endsWith('/content'))throw new Error('Lost content response');
    if(path.endsWith('/upload-intents/'+intent))return ok({id:intent,material_id:material,state:'RECEIVED'});
    if(path.endsWith('/complete'))return ok({id:version,version_no:2});
    throw new Error('Unexpected');
  });
  const file=new File(['synthetic'],'audit.pdf'),attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID()},gateway=new LearningGateway(fetcher);
  await expect(gateway.upload(material,file,undefined,undefined,attempt)).rejects.toThrow();
  expect((await gateway.upload(material,file,undefined,undefined,attempt)).id).toBe(version);
  expect(calls.filter(c=>c.path.endsWith('/content'))).toHaveLength(1);expect(calls.find(c=>c.path.endsWith('/complete'))?.key).toBe(attempt.completeKey);
});
it('does not stream or complete while the original server transfer is still receiving',async()=>{
  const fetcher=vi.fn(async()=>ok({id:intent,material_id:material,state:'RECEIVING'})),file=new File(['synthetic'],'audit.pdf');
  const attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID(),intentId:intent,started:true};
  await expect(new LearningGateway(fetcher).upload(material,file,undefined,undefined,attempt)).rejects.toMatchObject({code:'UPLOAD_IN_PROGRESS'});
  expect(fetcher).toHaveBeenCalledTimes(1);expect(fetcher.mock.calls[0]).toHaveLength(2);
});
it.each(['ABORTED','EXPIRED'])('retains a stopped %s attempt without silently creating another intent',async state=>{
  const fetcher=vi.fn(async()=>ok({id:intent,material_id:material,state})),file=new File(['synthetic'],'audit.pdf');
  const attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID(),intentId:intent,started:true};
  await expect(new LearningGateway(fetcher).upload(material,file,undefined,undefined,attempt)).rejects.toMatchObject({code:'UPLOAD_'+state});expect(fetcher).toHaveBeenCalledTimes(1);
});
it('reuses the original creation key after losing the intent response',async()=>{
  const keys:(string|null)[]=[];let reads=0;
  const fetcher=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
    const path=String(input);
    if(path.endsWith('/upload-intents')){keys.push(new Headers(init?.headers).get('Idempotency-Key'));if(keys.length===1)throw new Error('Lost intent response');return ok({id:intent});}
    if(path.endsWith('/upload-intents/'+intent)){reads++;return ok({id:intent,material_id:material,state:'CREATED'});}
    return ok(path.endsWith('/complete')?{id:version}:{state:'RECEIVED'});
  });
  const file=new File(['synthetic'],'audit.pdf'),attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID()},gateway=new LearningGateway(fetcher);
  await expect(gateway.upload(material,file,undefined,undefined,attempt)).rejects.toThrow();await gateway.upload(material,file,undefined,undefined,attempt);
  expect(keys).toEqual([attempt.intentKey,attempt.intentKey]);expect(reads).toBe(1);
});
it('stops a resumed transfer when cancellation arrives during its status check',async()=>{
  const controller=new AbortController(),fetcher=vi.fn(async()=>{controller.abort();return ok({id:intent,material_id:material,state:'CREATED'});});
  const attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID(),intentId:intent,started:true};
  await expect(new LearningGateway(fetcher).upload(material,new File(['synthetic'],'audit.pdf'),controller.signal,undefined,attempt)).rejects.toMatchObject({name:'AbortError'});
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('does not reuse an attempt for a different selected File',async()=>{
  const original=new File(['one'],'audit.pdf'),fetcher=vi.fn(),attempt={intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID(),file:original,materialId:material};
  await expect(new LearningGateway(fetcher).upload(material,new File(['two'],'audit.pdf'),undefined,undefined,attempt)).rejects.toThrow('không khớp');expect(fetcher).not.toHaveBeenCalled();
});

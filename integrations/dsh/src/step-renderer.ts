/** Observe the actual frozen SDK serializer at a local render-only receiver.
 * No request reaches a model service. The receiver returns HTTP 418, never
 * a fabricated model result or usage. Credentials and headers aren't recorded.
 */
import { createServer } from 'node:http';
import { Context, Service } from '@deepseek-ai/cordis';
import LlmRuntime, { type GenerateOptions } from '@deepseek-ai/dsh-llm';
import * as PiAi from '@deepseek-ai/dsh-llm-pi-ai';
import type { GatedAdapterSource } from './request-accounting.js';
import { decodeWire, isObject, immutable, type JsonObject, type JsonValue } from './wire.js';

class RenderCredentials extends Service {
  constructor(ctx: Context) { super(ctx,'credentials'); }
  async resolve() { return { value: 'c2p-render-only-no-secret' }; }
  async listRecords() { return []; }
}

function mirror(value: JsonValue, endpoint: string): JsonValue {
  if (Array.isArray(value)) return value.map(item=>mirror(item,endpoint));
  if (!isObject(value)) return value;
  const result:JsonObject={};
  for (const [key,item] of Object.entries(value)) {
    // Catalog per-model overrides may also own an endpoint. Redirect every
    // supported spelling, not only the profile's root, before SDK resolution.
    if (key==='baseURL' || key==='baseUrl') result[key]=endpoint;
    else if (key==='headers') {
      if (!isObject(item)) throw new Error('step_render_profile_invalid');
      result[key]=Object.fromEntries(Object.entries(item).filter(([name])=>!['authorization','proxy-authorization','x-api-key'].includes(name.toLowerCase())));
    } else result[key]=mirror(item,endpoint);
  }
  return result;
}

/** Only supports the designated local OpenAI-completions provider profile.
 * Transport endpoint/credential substitution is explicit; all material profile
 * fields and the actual request remain unchanged and are kernel-checked later.
 */
export async function observeLocalWriterWire(providerConfig: JsonObject, request: GenerateOptions): Promise<JsonObject> {
  const providers=providerConfig['providers'];
  const profile=isObject(providers) ? providers[request.provider] : undefined;
  if (!isObject(profile) || typeof profile['baseURL']!=='string'
    || !isObject(profile['retryPolicy']) || profile['retryPolicy']['maxRetries']!==0) throw new Error('step_render_profile_invalid');
  const original=new URL(profile['baseURL']);
  if (original.protocol!=='http:' || original.hostname!=='127.0.0.1' || original.username || original.password
    || original.search || original.hash) throw new Error('step_render_local_profile_required');
  request.signal?.throwIfAborted();
  const ctx=new Context();let native:GatedAdapterSource|undefined;let observed:JsonObject|undefined;let arrivals=0;
  let failure:Error|undefined;
  const server=createServer(async(incoming,response)=>{
    arrivals++;
    try {
      if (arrivals!==1 || incoming.method!=='POST' || incoming.url!==`${original.pathname.replace(/\/$/,'')}/chat/completions`) {
        throw new Error('step_render_transport_unexpected');
      }
      const chunks:Buffer[]=[];let size=0;
      for await (const part of incoming) {
        const chunk=Buffer.from(part);size+=chunk.length;
        if(size>1<<20)throw new Error('step_render_wire_too_large');
        chunks.push(chunk);
      }
      const body=decodeWire(Buffer.concat(chunks));
      if(!isObject(body))throw new Error('step_render_wire_invalid');
      observed=immutable(body);
    } catch { failure=new Error('step_render_transport_invalid'); }
    response.writeHead(418,{'content-type':'application/json'});
    response.end('{"error":{"message":"render-only receiver; no model executed","type":"render_only"}}');
  });
  try {
    await new Promise<void>((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
    const address=server.address();if(address===null || typeof address==='string')throw new Error('step_render_receiver_unavailable');
    const endpoint=`http://127.0.0.1:${address.port}${original.pathname}`;
    const mirrored=mirror(profile,endpoint);
    if(!isObject(mirrored))throw new Error('step_render_profile_invalid');
    mirrored['baseURL']=endpoint;mirrored['apiKeyEnv']='C2P_DSH_RENDER_ONLY_KEY';
    new LlmRuntime(ctx);new RenderCredentials(ctx);
    const register=ctx.llm.registerAdapter.bind(ctx.llm);
    ctx.llm.registerAdapter=(routes,adapter)=>{native=adapter as unknown as GatedAdapterSource;return register(routes,adapter);};
    await ctx.plugin(PiAi,{providers:{[request.provider]:mirrored}} as never);
    if(native===undefined)throw new Error('step_render_adapter_unavailable');
    const signal=AbortSignal.any([AbortSignal.timeout(15_000),...(request.signal===undefined?[]:[request.signal])]);
    // Deliberately outside ctx.llm.stream: this private serializer instance can
    // address only the receiver above. It has no real model send capability.
    for await(const _chunk of native.stream({...request,signal})) { /* no fake output accepted */ }
    request.signal?.throwIfAborted();
    if(failure!==undefined)throw failure;
    if(arrivals!==1 || observed===undefined)throw new Error('step_render_wire_unobserved');
    return observed;
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve=>server.close(()=>resolve()));
    await ctx.fiber.dispose();
  }
}

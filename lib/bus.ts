// super-light in-memory pub/sub for SSE
type Subscriber = (payload: any) => void;

const globalAny = globalThis as any;
if (!globalAny.__PM_BUS__) {
  globalAny.__PM_BUS__ = new Set<Subscriber>();
}
const subs: Set<Subscriber> = globalAny.__PM_BUS__;

export function publish(payload: any) {
  for (const s of subs) {
    try { s(payload); } catch {}
  }
}

export function subscribe(fn: Subscriber) {
  subs.add(fn);
  return () => subs.delete(fn);
}

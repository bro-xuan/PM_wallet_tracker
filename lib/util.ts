export const isAddress = (a: string) => /^0x[a-fA-F0-9]{40}$/.test(a.trim());
export const dollars  = (n: number) => '$' + n.toFixed(2);
export const notional = (size: number, price: number) => size * price;

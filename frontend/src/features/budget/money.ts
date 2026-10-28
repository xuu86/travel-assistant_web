export function parseYuanToFen(value: string): number | null {
  const normalized = value.trim();
  if (normalized === "") return null;
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) {
    throw new Error("金额最多填写两位小数，且不能为负数。");
  }

  const [yuan, fraction = ""] = normalized.split(".");
  const fen = BigInt(yuan) * 100n + BigInt(fraction.padEnd(2, "0"));
  if (fen > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error("金额超出当前可安全计算的范围。");
  }
  return Number(fen);
}

export function formatFen(fen: number | null): string {
  if (fen === null) return "待核实";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
  }).format(fen / 100);
}

export function formatFenInput(fen: number | null): string {
  if (fen === null) return "";
  const value = BigInt(fen);
  const yuan = value / 100n;
  const fraction = String(value % 100n).padStart(2, "0");
  return `${yuan}.${fraction}`;
}

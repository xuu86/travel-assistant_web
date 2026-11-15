import { afterEach, describe, expect, it, vi } from "vitest";
import { extractOrderPrices, findPriceCandidates } from "./order-import";

const parserMocks = vi.hoisted(() => ({
  extractDocxText: vi.fn(),
  getPdfDocument: vi.fn(),
  createOcrWorker: vi.fn(),
}));

vi.mock("mammoth", () => ({ default: { extractRawText: parserMocks.extractDocxText } }));
vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: parserMocks.getPdfDocument,
}));
vi.mock("tesseract.js", () => ({ createWorker: parserMocks.createOcrWorker }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function makeDocxFile(): File {
  const archiveEnd = new Uint8Array(22);
  new DataView(archiveEnd.buffer).setUint32(0, 0x06054b50, true);
  return new File([archiveEnd], "order.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
}

describe("findPriceCandidates", () => {
  it("prefers paid order totals over listed prices and removes duplicate labels", () => {
    const candidates = findPriceCandidates("订单金额：￥399.00 优惠：50.00 实付款：￥349.00");

    expect(candidates).toEqual([
      { amount: "349.00", label: "实付款", priority: 0 },
      { amount: "399.00", label: "订单金额", priority: 1 },
    ]);
  });

  it("supports full-width digits and currency-only fallback", () => {
    expect(findPriceCandidates("票价：￥１２８.５０")[0]).toEqual({
      amount: "128.50", label: "票价", priority: 2,
    });
    expect(findPriceCandidates("¥68.00")[0]).toEqual({
      amount: "68.00", label: "识别到的金额", priority: 5,
    });
  });

  it("normalizes OCR spacing inside Chinese payment labels", () => {
    expect(findPriceCandidates("实 付款 : 关 128.00")).toEqual([
      { amount: "128.00", label: "实付款", priority: 0 },
    ]);
  });

  it("does not infer a zero amount", () => {
    expect(findPriceCandidates("实付款：¥0.00")).toEqual([]);
  });

  it("extracts a DOCX order locally", async () => {
    parserMocks.extractDocxText.mockResolvedValue({ value: "实付款：¥349.50" });

    await expect(extractOrderPrices(makeDocxFile())).resolves.toEqual([
      { amount: "349.50", label: "实付款", priority: 0 },
    ]);
    expect(parserMocks.extractDocxText).toHaveBeenCalledOnce();
  });

  it("extracts text PDF orders and always releases the PDF document", async () => {
    const page = {
      getTextContent: vi.fn().mockResolvedValue({ items: [{ str: "实付金额：¥349.50" }] }),
      cleanup: vi.fn(),
    };
    const document = { numPages: 1, getPage: vi.fn().mockResolvedValue(page) };
    const loadingTask = { promise: Promise.resolve(document), destroy: vi.fn().mockResolvedValue(undefined) };
    parserMocks.getPdfDocument.mockReturnValue(loadingTask);

    await expect(extractOrderPrices(new File(["pdf"], "ticket.pdf", { type: "application/pdf" }))).resolves.toEqual([
      { amount: "349.50", label: "实付金额", priority: 0 },
    ]);
    expect(page.cleanup).toHaveBeenCalledOnce();
    expect(loadingTask.destroy).toHaveBeenCalledOnce();
  });

  it("uses local OCR for image orders and terminates the worker", async () => {
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue({ width: 1200, height: 800, close: vi.fn() }));
    const recognize = vi.fn().mockResolvedValue({ data: { text: "实付款：¥128.00" } });
    const terminate = vi.fn().mockResolvedValue(undefined);
    parserMocks.createOcrWorker.mockResolvedValue({ recognize, terminate });

    await expect(extractOrderPrices(new File(["image"], "ticket.jpg", { type: "image/jpeg" }))).resolves.toEqual([
      { amount: "128.00", label: "实付款", priority: 0 },
    ]);
    expect(recognize).toHaveBeenCalledOnce();
    expect(terminate).toHaveBeenCalledOnce();
  });

  it("rejects unsupported formats and oversized files before invoking a parser", async () => {
    await expect(extractOrderPrices(new File(["legacy"], "ticket.doc"))).rejects.toThrow("暂不支持此格式");
    await expect(extractOrderPrices(new File([new Uint8Array(20 * 1024 * 1024 + 1)], "large.pdf")))
      .rejects.toThrow("超过 20 MB");
    expect(parserMocks.extractDocxText).not.toHaveBeenCalled();
    expect(parserMocks.getPdfDocument).not.toHaveBeenCalled();
  });

  it("rejects PDFs above the local page limit and destroys the loading task", async () => {
    const loadingTask = { promise: Promise.resolve({ numPages: 51 }), destroy: vi.fn().mockResolvedValue(undefined) };
    parserMocks.getPdfDocument.mockReturnValue(loadingTask);

    await expect(extractOrderPrices(new File(["pdf"], "long.pdf", { type: "application/pdf" })))
      .rejects.toThrow("超过 50 页");
    expect(loadingTask.destroy).toHaveBeenCalledOnce();
  });

  it("rejects images above the local pixel limit and releases the bitmap", async () => {
    const close = vi.fn();
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue({ width: 8000, height: 6000, close }));

    await expect(extractOrderPrices(new File(["image"], "large.png", { type: "image/png" })))
      .rejects.toThrow("图片尺寸超过本地识别上限");
    expect(close).toHaveBeenCalledOnce();
  });
});

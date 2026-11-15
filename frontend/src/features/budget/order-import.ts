import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";

export type PriceCandidate = {
  amount: string;
  label: string;
  priority: number;
};

const MAX_FILE_BYTES = 20 * 1024 * 1024;
const MAX_DOCX_EXPANDED_BYTES = 100 * 1024 * 1024;
const MAX_DOCX_ENTRIES = 5_000;
const MAX_PDF_PAGES = 50;
const MAX_IMAGE_PIXELS = 40_000_000;
const MAX_TEXT_CHARACTERS = 2_000_000;
const OCR_WORKER_OPTIONS = {
  workerPath: "/ocr/worker.min.js",
  corePath: "/ocr/tesseract-core-simd-lstm.wasm.js",
  langPath: "/ocr",
  workerBlobURL: false,
};
const PRICE_LABELS = [
  { label: "实付金额", priority: 0 },
  { label: "实付款", priority: 0 },
  { label: "实付", priority: 0 },
  { label: "支付总额", priority: 1 },
  { label: "支付金额", priority: 1 },
  { label: "订单金额", priority: 1 },
  { label: "订单总额", priority: 1 },
  { label: "票价", priority: 2 },
  { label: "成人票价", priority: 2 },
  { label: "合计", priority: 3 },
  { label: "总价", priority: 3 },
  { label: "金额", priority: 4 },
  { label: "价格", priority: 4 },
];

const amountPattern = "(?:[￥¥]\\s*)?((?:\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.\\d{1,2})?)(?:\\s*元)?";

export function findPriceCandidates(text: string): PriceCandidate[] {
  const normalized = text
    .replace(/(\p{Script=Han})\s+(?=\p{Script=Han})/gu, "$1")
    .replace(/[０-９]/g, (digit) => String.fromCharCode(digit.charCodeAt(0) - 0xfee0))
    .replace(/[，]/g, ",").replace(/[：]/g, ":");
  const found: PriceCandidate[] = [];

  for (const { label, priority } of PRICE_LABELS) {
    const pattern = new RegExp(`${label}[^\\d￥¥]{0,18}${amountPattern}`, "gi");
    for (const match of normalized.matchAll(pattern)) {
      const amount = match[1]?.replaceAll(",", "");
      if (amount && Number(amount) > 0) found.push({ amount, label, priority });
    }
  }

  if (found.length === 0) {
    const pattern = /[￥¥]\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)|((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)\s*元/g;
    for (const match of normalized.matchAll(pattern)) {
      const amount = (match[1] ?? match[2] ?? "").replaceAll(",", "").trim();
      if (amount && Number(amount) > 0) found.push({ amount, label: "识别到的金额", priority: 5 });
    }
  }

  const unique = new Map<string, PriceCandidate>();
  for (const candidate of found) {
    const previous = unique.get(candidate.amount);
    if (!previous || candidate.priority < previous.priority) unique.set(candidate.amount, candidate);
  }
  return [...unique.values()].sort((a, b) => a.priority - b.priority);
}

function validateFile(file: File): string {
  if (!file.size) throw new Error("文件为空，请选择有效的订单文件。");
  if (file.size > MAX_FILE_BYTES) throw new Error("文件超过 20 MB，请压缩或拆分后重试。");

  const extension = file.name.split(".").at(-1)?.toLowerCase();
  if (extension === "docx") return extension;
  if (extension === "pdf") return extension;
  if (["jpg", "jpeg", "png"].includes(extension ?? "")) return "image";
  throw new Error("暂不支持此格式，请导入 .docx、.pdf、.jpg 或 .png 文件。");
}

function validateDocxArchive(buffer: ArrayBuffer): void {
  const view = new DataView(buffer);
  const earliestEocd = Math.max(0, view.byteLength - 65_557);
  let eocdOffset = -1;
  for (let offset = view.byteLength - 22; offset >= earliestEocd; offset -= 1) {
    if (view.getUint32(offset, true) === 0x06054b50) {
      eocdOffset = offset;
      break;
    }
  }
  if (eocdOffset < 0) throw new Error("Word 文件结构无效或无法读取。");

  const entryCount = view.getUint16(eocdOffset + 10, true);
  const centralDirectorySize = view.getUint32(eocdOffset + 12, true);
  const centralDirectoryOffset = view.getUint32(eocdOffset + 16, true);
  if (entryCount === 0xffff || centralDirectorySize === 0xffffffff || centralDirectoryOffset === 0xffffffff ||
    entryCount > MAX_DOCX_ENTRIES || centralDirectoryOffset + centralDirectorySize > eocdOffset) {
    throw new Error("Word 文件结构超出本地处理上限。");
  }

  let offset = centralDirectoryOffset;
  let expandedBytes = 0;
  for (let index = 0; index < entryCount; index += 1) {
    if (offset + 46 > view.byteLength || view.getUint32(offset, true) !== 0x02014b50) {
      throw new Error("Word 文件结构无效或无法读取。");
    }
    expandedBytes += view.getUint32(offset + 24, true);
    if (expandedBytes > MAX_DOCX_EXPANDED_BYTES) {
      throw new Error("Word 文件解压后超过本地处理上限。");
    }
    offset += 46 + view.getUint16(offset + 28, true) + view.getUint16(offset + 30, true) + view.getUint16(offset + 32, true);
  }
  if (offset > centralDirectoryOffset + centralDirectorySize) {
    throw new Error("Word 文件结构无效或无法读取。");
  }
}

async function validateImageSize(file: File): Promise<void> {
  let image: ImageBitmap | undefined;
  try {
    image = await createImageBitmap(file);
  } catch (cause) {
    if (cause instanceof Error && cause.message.includes("本地识别上限")) throw cause;
    throw new Error("图片无法读取，请确认它是有效的 JPG 或 PNG 文件。", { cause });
  }
  const exceedsLimit = image.width * image.height > MAX_IMAGE_PIXELS;
  image.close();
  if (exceedsLimit) throw new Error("图片尺寸超过本地识别上限，请缩小图片后重试。");
}

async function readPdf(file: File): Promise<{ loadingTask: PDFDocumentLoadingTask; document: PDFDocumentProxy; text: string }> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
  const loadingTask = pdfjs.getDocument({ data: await file.arrayBuffer() });
  const document = await loadingTask.promise;
  if (document.numPages > MAX_PDF_PAGES) {
    await loadingTask.destroy();
    throw new Error("PDF 超过 50 页，请拆分后重试。");
  }

  const pages: string[] = [];
  try {
    for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
      const page = await document.getPage(pageNumber);
      const content = await page.getTextContent();
      pages.push(content.items.map((item) => "str" in item ? item.str : "").join(" "));
      page.cleanup();
    }
    return { loadingTask, document, text: pages.join("\n").slice(0, MAX_TEXT_CHARACTERS) };
  } catch (cause) {
    await loadingTask.destroy();
    throw cause;
  }
}

async function recognizeImage(image: File | Blob, onProgress: (progress: number) => void): Promise<string> {
  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("chi_sim", 1, {
    ...OCR_WORKER_OPTIONS,
    logger: (message) => {
      if (message.status === "recognizing text") onProgress(message.progress);
    },
  });
  try {
    const result = await worker.recognize(image);
    return result.data.text.slice(0, MAX_TEXT_CHARACTERS);
  } finally {
    await worker.terminate();
  }
}

async function recognizePdf(document: PDFDocumentProxy, onProgress: (progress: number) => void): Promise<string> {
  const { createWorker } = await import("tesseract.js");
  const texts: string[] = [];
  let currentPage = 0;
  const worker = await createWorker("chi_sim", 1, {
    ...OCR_WORKER_OPTIONS,
    logger: (message) => {
      if (message.status === "recognizing text") onProgress((currentPage + message.progress) / document.numPages);
    },
  });
  try {
    for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
      currentPage = pageNumber - 1;
      const page = await document.getPage(pageNumber);
      const initial = page.getViewport({ scale: 1 });
      const scale = Math.min(2, 6_000 / Math.max(initial.width, initial.height));
      const viewport = page.getViewport({ scale });
      const canvas = window.document.createElement("canvas");
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      const context = canvas.getContext("2d");
      if (!context) throw new Error("当前浏览器无法创建本地 PDF 识别画布。");
      await page.render({ canvas, canvasContext: context, viewport }).promise;
      const result = await worker.recognize(canvas);
      texts.push(result.data.text);
      canvas.width = 0;
      canvas.height = 0;
      page.cleanup();
      if (texts.join("\n").length > MAX_TEXT_CHARACTERS) break;
    }
  } finally {
    await worker.terminate();
  }
  return texts.join("\n").slice(0, MAX_TEXT_CHARACTERS);
}

export async function extractOrderPrices(
  file: File,
  onProgress: (progress: number) => void = () => undefined,
): Promise<PriceCandidate[]> {
  const fileKind = validateFile(file);
  let text: string;

  if (fileKind === "docx") {
    const arrayBuffer = await file.arrayBuffer();
    validateDocxArchive(arrayBuffer);
    const { default: mammoth } = await import("mammoth");
    const result = await mammoth.extractRawText({ arrayBuffer });
    text = result.value.slice(0, MAX_TEXT_CHARACTERS);
  } else if (fileKind === "pdf") {
    const { loadingTask, document, text: extractedText } = await readPdf(file);
    try {
      text = findPriceCandidates(extractedText).length > 0
        ? extractedText
        : await recognizePdf(document, onProgress);
    } finally {
      await loadingTask.destroy();
    }
  } else {
    await validateImageSize(file);
    text = await recognizeImage(file, onProgress);
  }

  const candidates = findPriceCandidates(text);
  if (candidates.length === 0) throw new Error("没有识别到订单金额，请确认文件清晰且包含价格信息。");
  return candidates;
}

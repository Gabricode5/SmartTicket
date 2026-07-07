import { downloadCsv } from "@/lib/csv";

function readBlobAsText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

describe("downloadCsv", () => {
  let createObjectURL: jest.Mock;
  let revokeObjectURL: jest.Mock;
  let clickSpy: jest.SpyInstance;
  let capturedBlob: Blob | null;
  let capturedFilename: string | null;

  beforeEach(() => {
    capturedBlob = null;
    capturedFilename = null;
    createObjectURL = jest.fn((blob: Blob) => {
      capturedBlob = blob;
      return "blob:mock-url";
    });
    revokeObjectURL = jest.fn();
    URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as unknown as typeof URL.revokeObjectURL;

    clickSpy = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      capturedFilename = this.download;
    });
  });

  afterEach(() => {
    clickSpy.mockRestore();
    jest.restoreAllMocks();
  });

  it("builds a CSV blob with sections, headers and rows, and triggers a download", async () => {
    downloadCsv("export-test.csv", [
      { title: "Section A", headers: ["Jour", "IA"], rows: [["5 janv", 3], ["6 janv", 7]] },
      { title: "Section B", headers: ["Agent"], rows: [["Bob"]] },
    ]);

    expect(capturedFilename).toBe("export-test.csv");
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    const rawText = await readBlobAsText(capturedBlob!);
    const BOM = String.fromCharCode(0xfeff);
    const text = rawText.startsWith(BOM) ? rawText.slice(1) : rawText;
    expect(text.split("\r\n")).toEqual([
      "Section A",
      "Jour,IA",
      "5 janv,3",
      "6 janv,7",
      "",
      "Section B",
      "Agent",
      "Bob",
      "",
    ]);
  });

  it("quotes cells containing commas, quotes or newlines", async () => {
    downloadCsv("escape-test.csv", [
      { title: "S", headers: ["Nom"], rows: [['Dupont, Jean "Le Grand"']] },
    ]);

    const text = await readBlobAsText(capturedBlob!);
    expect(text).toContain('"Dupont, Jean ""Le Grand"""');
  });
});

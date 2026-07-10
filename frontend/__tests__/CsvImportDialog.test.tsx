import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CsvImportDialog } from "@/components/dashboard/CsvImportDialog";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

function makeCsvFile() {
  return new File(["email,username,prenom,nom\na@example.com,a_user,A,A\n"], "import.csv", { type: "text/csv" });
}

describe("CsvImportDialog", () => {
  it("uploads the selected file and shows the created/skipped summary", async () => {
    const onImported = jest.fn();
    const fetchMock = mockFetch((url) =>
      url === "/api/users/import-csv"
        ? jsonResponse({ total_rows: 2, created: 1, skipped: [{ row: 3, email: "b@example.com", reason: "email déjà utilisé" }] })
        : jsonResponse({}, 404)
    );

    render(<CsvImportDialog onImported={onImported} />);
    fireEvent.click(screen.getByRole("button", { name: /importer un csv/i }));

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [makeCsvFile()] } });

    fireEvent.click(screen.getByRole("button", { name: /^importer$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/users/import-csv", expect.objectContaining({ method: "POST" }));
    });
    expect(await screen.findByText(/1 compte créé sur 2 lignes/i)).toBeInTheDocument();
    expect(screen.getByText(/1 ligne ignorée/i)).toBeInTheDocument();
    expect(onImported).toHaveBeenCalled();
  });

  it("shows an error and does not call onImported if the import fails", async () => {
    const onImported = jest.fn();
    mockFetch(() => jsonResponse({ detail: "Colonnes requises manquantes : 'email' et 'username'." }, 400));

    render(<CsvImportDialog onImported={onImported} />);
    fireEvent.click(screen.getByRole("button", { name: /importer un csv/i }));

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [makeCsvFile()] } });
    fireEvent.click(screen.getByRole("button", { name: /^importer$/i }));

    expect(await screen.findByText(/colonnes requises manquantes/i)).toBeInTheDocument();
    expect(onImported).not.toHaveBeenCalled();
  });

  it("disables the import button until a file is selected", async () => {
    render(<CsvImportDialog onImported={jest.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /importer un csv/i }));

    expect(screen.getByRole("button", { name: /^importer$/i })).toBeDisabled();
  });
});

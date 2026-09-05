import { callApi } from "./index";

export interface BackupFile {
  filename: string;
  mime: string;
  content_b64: string;
}

export interface ImportResult {
  files: number;
  manifest_present: boolean;
  db_backed_up: boolean;
}

export const backupApi = {
  export: () => callApi<BackupFile>("GET", "/backup/export"),
  import: (zipB64: string, overwrite = true) =>
    callApi<ImportResult>("POST", "/backup/import", {
      zip_b64: zipB64,
      overwrite,
    }),
};

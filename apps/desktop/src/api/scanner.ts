import { callApi } from "./index";

export interface DetectedChapter {
  title: string;
  path: string;
  word_count: number;
  preview: string;
}

export interface DetectedNovel {
  dir_path: string;
  title: string;
  chapter_count: number;
  total_words: number;
  chapters: DetectedChapter[];
}

export interface ScanResult {
  novels: DetectedNovel[];
}

export interface ImportResult {
  novel_id: number;
  name: string;
  chapter_count: number;
}

export const scannerApi = {
  scan: (path: string, maxDepth = 3) =>
    callApi<ScanResult>("POST", "/scanner/scan", { path, max_depth: maxDepth }),
  import: (dirPath: string, genre = "xiuxian") =>
    callApi<ImportResult>("POST", "/scanner/import", {
      dir_path: dirPath,
      genre,
    }),
};

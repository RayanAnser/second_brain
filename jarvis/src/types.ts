export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface DocEntry {
  key: string;     // "projets/foo.md"
  name: string;    // "foo"
  size_kb: number;
  subdir: string;  // "projets" | "concepts" | "perso"
}

export interface Capture {
  intent: string;
  content: string;
  section?: string;
}

export interface MemoryContext {
  soul: string;
  user: string;
  memory: string;
}

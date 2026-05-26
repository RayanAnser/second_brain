import { create } from "zustand";
import { Capture, MemoryContext, Message } from "./types";

interface AppState {
  messages: Message[];
  addMessage: (msg: Message) => void;
  appendToLastAssistant: (token: string) => void;

  isListening: boolean;
  isSpeaking: boolean;
  isThinking: boolean;
  audioLevel: number;
  setIsListening: (v: boolean) => void;
  setIsSpeaking: (v: boolean) => void;
  setIsThinking: (v: boolean) => void;
  setAudioLevel: (v: number) => void;

  isCompact: boolean;
  setIsCompact: (v: boolean) => void;

  memoryContext: MemoryContext | null;
  setMemoryContext: (ctx: MemoryContext) => void;

  captures: Capture[];
  setCaptures: (c: Capture[]) => void;
}

export const useStore = create<AppState>((set) => ({
  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLastAssistant: (token) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + token };
      } else {
        msgs.push({
          id: `${Date.now()}-a`,
          role: "assistant",
          content: token,
          timestamp: Date.now(),
        });
      }
      return { messages: msgs };
    }),

  isListening: false,
  isSpeaking: false,
  isThinking: false,
  audioLevel: 0,
  setIsListening: (v) => set({ isListening: v }),
  setIsSpeaking: (v) => set({ isSpeaking: v }),
  setIsThinking: (v) => set({ isThinking: v }),
  setAudioLevel: (v) => set({ audioLevel: v }),

  isCompact: true,
  setIsCompact: (v) => set({ isCompact: v }),

  memoryContext: null,
  setMemoryContext: (ctx) => set({ memoryContext: ctx }),

  captures: [],
  setCaptures: (c) => set({ captures: c }),
}));

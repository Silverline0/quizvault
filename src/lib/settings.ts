/**
 * App settings — persisted to localStorage, separate from quiz progress.
 */

export interface AppSettings {
  // Display
  fontSize: "small" | "medium" | "large";
  theme: "light" | "dark" | "sepia";

  // Quiz behavior
  spacedRepEnabled: boolean;
  hapticFeedback: boolean;
  showKeyboardHints: boolean;

  // Keyboard mapping
  keyMap: {
    optionA: string;
    optionB: string;
    optionC: string;
    optionD: string;
    next: string;
    prev: string;
  };

  // Study plan
  examDate?: string; // ISO date string
  dailyGoal?: number; // questions per day
}

const SETTINGS_KEY = "quizvault_settings";

const defaultSettings: AppSettings = {
  fontSize: "medium",
  theme: "light",
  spacedRepEnabled: true,
  hapticFeedback: true,
  showKeyboardHints: true,
  keyMap: {
    optionA: "A",
    optionB: "B",
    optionC: "C",
    optionD: "D",
    next: "ArrowRight",
    prev: "ArrowLeft",
  },
};

export function getSettings(): AppSettings {
  if (typeof window === "undefined") return defaultSettings;
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return defaultSettings;
    return { ...defaultSettings, ...JSON.parse(raw) };
  } catch {
    return defaultSettings;
  }
}

export function saveSettings(settings: Partial<AppSettings>): AppSettings {
  const current = getSettings();
  const updated = { ...current, ...settings };
  if (typeof window !== "undefined") {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(updated));
  }
  return updated;
}

export function getSetting<K extends keyof AppSettings>(key: K): AppSettings[K] {
  return getSettings()[key];
}

export function getFontSizeClass(): string {
  const size = getSetting("fontSize");
  switch (size) {
    case "small": return "text-sm";
    case "large": return "text-lg md:text-xl";
    default: return "text-base md:text-lg";
  }
}

export function triggerHaptic(type: "success" | "error" | "light" = "light"): void {
  if (typeof window === "undefined") return;
  if (!getSetting("hapticFeedback")) return;
  if (!navigator.vibrate) return;

  switch (type) {
    case "success":
      navigator.vibrate([10, 50, 10]); // double tap
      break;
    case "error":
      navigator.vibrate(30); // single buzz
      break;
    case "light":
      navigator.vibrate(5); // micro tap
      break;
  }
}

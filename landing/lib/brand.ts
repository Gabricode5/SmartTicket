// NEXT_PUBLIC_* est bakée au BUILD Next.js, jamais réévaluée au runtime — voir la
// même remarque dans le frontend principal (lib/brand.ts).
export const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME || "SmartTicket";

// URL de l'app principale (frontend/backend complet) vers laquelle pointent les CTA
// (login, sign-up, chat) et les pages légales — cette landing statique ne les sert pas.
export const APP_URL = (
  process.env.NEXT_PUBLIC_APP_URL || "https://smartticket-frontend.onrender.com"
).replace(/\/$/, "");

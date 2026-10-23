// Password policy — kept in sync with the backend (backend/app/schemas/auth.py).
// Simple + memorable: at least 8 characters, mixing letters and numbers.

export const PASSWORD_MIN_LEN = 8;

export type PasswordRule = { key: string; label: string; test: (pw: string) => boolean };

export const PASSWORD_RULES: PasswordRule[] = [
  { key: "length", label: `At least ${PASSWORD_MIN_LEN} characters`, test: (pw) => pw.length >= PASSWORD_MIN_LEN },
  { key: "letter", label: "Includes a letter", test: (pw) => /[A-Za-z]/.test(pw) },
  { key: "number", label: "Includes a number", test: (pw) => /\d/.test(pw) },
];

export function passwordValid(pw: string): boolean {
  return PASSWORD_RULES.every((r) => r.test(pw));
}

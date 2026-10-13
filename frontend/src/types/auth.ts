export type UserRole = "ADMIN" | "ANALYST" | "VIEWER";

export type User = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  created_at: string;
};

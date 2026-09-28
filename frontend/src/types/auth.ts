export type UserRole = "ADMIN" | "ANALYST" | "VIEWER";

export type User = {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

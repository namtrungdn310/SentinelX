/**
 * Authentication service and validation utilities for SentinelX.
 * Designed for PBL demo and local persistence with standard security rules.
 */

export interface User {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface PasswordCriteria {
  minLength: boolean;
  hasUppercase: boolean;
  hasAlphaNumeric: boolean;
  hasSpecialChar: boolean;
  isValid: boolean;
}

const STORAGE_USERS_KEY = "sentinelx_users_store";
const STORAGE_CURRENT_USER_KEY = "sentinelx_current_user";
const STORAGE_REMEMBERED_EMAIL_KEY = "sentinelx_remembered_email";

// Default admin user seeded for PBL presentation / evaluation
const DEFAULT_DEMO_USERS = [
  {
    id: "77db55e0-1ebe-4b69-be7c-286519d21442",
    username: "admin",
    email: "admin@sentinelx.vn",
    passwordHash: "Admin@123456", // meets all 4 password criteria
    created_at: "2026-10-14T08:00:00.000Z",
  },
];

export function validatePasswordCriteria(password: string): PasswordCriteria {
  const minLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLetters = /[a-zA-Z]/.test(password);
  const hasNumbers = /[0-9]/.test(password);
  const hasAlphaNumeric = hasLetters && hasNumbers;
  const hasSpecialChar = /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(password);

  return {
    minLength,
    hasUppercase,
    hasAlphaNumeric,
    hasSpecialChar,
    isValid: minLength && hasUppercase && hasAlphaNumeric && hasSpecialChar,
  };
}

export function validateUsername(username: string): { valid: boolean; error?: string } {
  const trimmed = username.trim();
  if (!trimmed) {
    return { valid: false, error: "Vui lòng nhập tên đăng nhập." };
  }
  if (trimmed.length < 3) {
    return { valid: false, error: "Tên đăng nhập phải có ít nhất 3 ký tự." };
  }
  if (trimmed.length > 30) {
    return { valid: false, error: "Tên đăng nhập không được vượt quá 30 ký tự." };
  }
  if (!/^[a-zA-Z0-9_.-]+$/.test(trimmed)) {
    return {
      valid: false,
      error: "Tên đăng nhập chỉ được chứa chữ cái, số, gạch dưới (_) hoặc gạch ngang (-).",
    };
  }
  return { valid: true };
}

export function validateEmail(email: string): { valid: boolean; error?: string } {
  const trimmed = email.trim();
  if (!trimmed) {
    return { valid: false, error: "Vui lòng nhập địa chỉ email." };
  }
  // Standard RFC email pattern
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) {
    return { valid: false, error: "Địa chỉ email không đúng định dạng." };
  }
  return { valid: true };
}

interface StoredUser extends User {
  passwordHash: string;
}

class AuthService {
  private getUsers(): StoredUser[] {
    try {
      const data = localStorage.getItem(STORAGE_USERS_KEY);
      if (!data) {
        localStorage.setItem(STORAGE_USERS_KEY, JSON.stringify(DEFAULT_DEMO_USERS));
        return DEFAULT_DEMO_USERS;
      }
      return JSON.parse(data) as StoredUser[];
    } catch {
      return DEFAULT_DEMO_USERS;
    }
  }

  private saveUsers(users: StoredUser[]): void {
    try {
      localStorage.setItem(STORAGE_USERS_KEY, JSON.stringify(users));
    } catch {
      // storage unavailable or full
    }
  }

  public getRememberedEmail(): string {
    try {
      return localStorage.getItem(STORAGE_REMEMBERED_EMAIL_KEY) || "";
    } catch {
      return "";
    }
  }

  public setRememberedEmail(email: string, remember: boolean): void {
    try {
      if (remember && email.trim()) {
        localStorage.setItem(STORAGE_REMEMBERED_EMAIL_KEY, email.trim());
      } else {
        localStorage.removeItem(STORAGE_REMEMBERED_EMAIL_KEY);
      }
    } catch {
      // storage unavailable
    }
  }

  public getCurrentUser(): User | null {
    try {
      const data = localStorage.getItem(STORAGE_CURRENT_USER_KEY);
      if (!data) return null;
      return JSON.parse(data) as User;
    } catch {
      return null;
    }
  }

  /**
   * Log in with Email and Password.
   * Does NOT require username.
   */
  public login(email: string, password: string): User {
    const cleanEmail = email.trim().toLowerCase();
    const cleanPass = password;

    if (!cleanEmail || !cleanPass) {
      throw new Error("Vui lòng nhập đầy đủ địa chỉ email và mật khẩu.");
    }

    const users = this.getUsers();
    const user = users.find((u) => u.email.toLowerCase() === cleanEmail);

    if (!user) {
      throw new Error("Tài khoản với địa chỉ email này không tồn tại.");
    }

    if (user.passwordHash !== cleanPass) {
      throw new Error("Mật khẩu không chính xác. Vui lòng kiểm tra lại.");
    }

    const sessionUser: User = {
      id: user.id,
      username: user.username,
      email: user.email,
      created_at: user.created_at,
    };

    localStorage.setItem(STORAGE_CURRENT_USER_KEY, JSON.stringify(sessionUser));
    return sessionUser;
  }

  public register(username: string, email: string, password: string): User {
    const uCheck = validateUsername(username);
    if (!uCheck.valid) throw new Error(uCheck.error);

    const eCheck = validateEmail(email);
    if (!eCheck.valid) throw new Error(eCheck.error);

    const pCheck = validatePasswordCriteria(password);
    if (!pCheck.isValid) {
      throw new Error("Mật khẩu chưa đáp ứng đầy đủ 4 tiêu chuẩn an toàn.");
    }

    const cleanUsername = username.trim();
    const cleanEmail = email.trim();
    const users = this.getUsers();

    if (users.some((u) => u.username.toLowerCase() === cleanUsername.toLowerCase())) {
      throw new Error(`Tên đăng nhập "${cleanUsername}" đã được sử dụng. Vui lòng chọn tên khác.`);
    }

    if (users.some((u) => u.email.toLowerCase() === cleanEmail.toLowerCase())) {
      throw new Error(`Email "${cleanEmail}" đã được đăng ký cho một tài khoản khác.`);
    }

    const newUser: StoredUser = {
      id: typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `usr-${Date.now()}`,
      username: cleanUsername,
      email: cleanEmail,
      passwordHash: password,
      created_at: new Date().toISOString(),
    };

    const updated = [...users, newUser];
    this.saveUsers(updated);

    const sessionUser: User = {
      id: newUser.id,
      username: newUser.username,
      email: newUser.email,
      created_at: newUser.created_at,
    };

    localStorage.setItem(STORAGE_CURRENT_USER_KEY, JSON.stringify(sessionUser));
    return sessionUser;
  }

  public resetPassword(email: string, newPassword: string): void {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      throw new Error("Vui lòng nhập email tài khoản cần đặt lại mật khẩu.");
    }

    const pCheck = validatePasswordCriteria(newPassword);
    if (!pCheck.isValid) {
      throw new Error("Mật khẩu mới chưa đáp ứng đầy đủ 4 tiêu chuẩn an toàn.");
    }

    const users = this.getUsers();
    const userIndex = users.findIndex((u) => u.email.toLowerCase() === cleanEmail);

    if (userIndex === -1) {
      throw new Error("Không tìm thấy tài khoản với địa chỉ email này.");
    }

    users[userIndex].passwordHash = newPassword;
    this.saveUsers(users);

    // If current session matches this user, update session as well
    const current = this.getCurrentUser();
    if (current && current.id === users[userIndex].id) {
      localStorage.setItem(STORAGE_CURRENT_USER_KEY, JSON.stringify({
        id: users[userIndex].id,
        username: users[userIndex].username,
        email: users[userIndex].email,
        created_at: users[userIndex].created_at,
      }));
    }
  }

  public logout(): void {
    localStorage.removeItem(STORAGE_CURRENT_USER_KEY);
  }
}

export const authService = new AuthService();

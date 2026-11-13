import { useState } from "react";
import { Eye, EyeOff, Check, X } from "lucide-react";
import {
  authService,
  validatePasswordCriteria,
  type User,
} from "../auth";

interface AuthViewProps {
  onAuthenticated: (user: User) => void;
}

type AuthMode = "login" | "register" | "forgot";

export function AuthView({ onAuthenticated }: AuthViewProps) {
  const [mode, setMode] = useState<AuthMode>("login");

  // Form states
  const [rememberMe, setRememberMe] = useState(() => Boolean(authService.getRememberedEmail()));
  const [email, setEmail] = useState(() => authService.getRememberedEmail());
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Status feedback
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const resetFields = () => {
    setError(null);
    setSuccess(null);
    setPassword("");
    setConfirmPassword("");
  };

  const switchMode = (nextMode: AuthMode) => {
    resetFields();
    setMode(nextMode);
  };

  // Live password validation
  const activePassword = mode === "register" || mode === "forgot" ? password : "";
  const criteria = validatePasswordCriteria(activePassword);

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const user = authService.login(email, password);
      authService.setRememberedEmail(email, rememberMe);
      onAuthenticated(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (username.trim().length < 3) {
      setError("Tên đăng nhập phải có ít nhất 3 ký tự.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp. Vui lòng kiểm tra lại.");
      return;
    }

    if (!criteria.isValid) {
      setError("Mật khẩu chưa đáp ứng đầy đủ 4 tiêu chuẩn an toàn.");
      return;
    }

    setLoading(true);
    try {
      const user = authService.register(username, email, password);
      onAuthenticated(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }

    if (!criteria.isValid) {
      setError("Mật khẩu mới chưa đáp ứng đầy đủ 4 tiêu chuẩn an toàn.");
      return;
    }

    setLoading(true);
    try {
      authService.resetPassword(email, password);
      setSuccess("Đặt lại mật khẩu thành công! Bạn có thể dùng mật khẩu mới để đăng nhập.");
      setPassword("");
      setConfirmPassword("");
      setTimeout(() => {
        switchMode("login");
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể đặt lại mật khẩu.");
    } finally {
      setLoading(false);
    }
  };

  const fillDemoAccount = () => {
    setEmail("admin@sentinelx.vn");
    setPassword("Admin@123456");
    setError(null);
  };

  return (
    <div className="auth-viewport">
      <div className="auth-card">
        {/* Brand header */}
        <div className="auth-header">
          <div className="auth-brand">
            <span className="brand-mark">
              <img
                src={`${import.meta.env.BASE_URL}sentinelx-mark-v2.svg`}
                alt=""
                width={40}
                height={40}
                decoding="async"
              />
            </span>
            <span className="auth-brand-name">
              Sentinel<span className="brand-x">X</span>
            </span>
          </div>
          <p className="auth-tagline">Nền tảng Quản trị & Giám sát An ninh Hạ tầng</p>
        </div>

        {/* Feedback banners */}
        {error && (
          <div className="feedback-banner feedback-error" role="alert">
            <span>{error}</span>
          </div>
        )}
        {success && (
          <div className="feedback-banner feedback-success" role="status">
            <span>{success}</span>
          </div>
        )}

        {/* --- MODE: LOGIN --- */}
        {mode === "login" && (
          <form onSubmit={handleLoginSubmit} className="auth-form">
            <div className="auth-title-group">
              <h1 className="auth-title">Đăng nhập</h1>
              <p className="auth-subtitle">
                Đăng nhập bằng Email để vào không gian giám sát hạ tầng.
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="login-email">Email *</label>
              <input
                id="login-email"
                type="email"
                className="form-input"
                placeholder="VD: admin@sentinelx.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <div className="form-label-row">
                <label htmlFor="login-password">Mật khẩu *</label>
                <button
                  type="button"
                  className="auth-link-inline"
                  onClick={() => switchMode("forgot")}
                >
                  Quên mật khẩu?
                </button>
              </div>
              <div className="password-input-wrapper">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  className="form-input"
                  placeholder="Nhập mật khẩu"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  title={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Remember Me Option */}
            <div className="auth-remember-row">
              <label className="checkbox-label" htmlFor="login-remember">
                <input
                  id="login-remember"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                <span>Ghi nhớ tài khoản</span>
              </label>
            </div>

            <button
              type="submit"
              className="btn btn-primary auth-submit-btn"
              disabled={loading || !email.trim() || !password}
            >
              {loading ? "Đang xác thực..." : "Đăng nhập"}
            </button>

            {/* Quick Demo Helper for PBL Evaluation */}
            <div className="auth-demo-hint">
              <div className="auth-demo-text">
                <strong>Tài khoản Demo (PBL):</strong> <code>admin@sentinelx.vn</code> / <code>Admin@123456</code>
              </div>
              <button
                type="button"
                className="btn btn-outline btn-sm auth-demo-btn"
                onClick={fillDemoAccount}
              >
                Điền nhanh tài khoản mẫu
              </button>
            </div>

            <div className="auth-footer-nav">
              <span>Chưa có tài khoản?</span>
              <button
                type="button"
                className="auth-link-bold"
                onClick={() => switchMode("register")}
              >
                Đăng ký tài khoản mới
              </button>
            </div>
          </form>
        )}

        {/* --- MODE: REGISTER --- */}
        {mode === "register" && (
          <form onSubmit={handleRegisterSubmit} className="auth-form">
            <div className="auth-title-group">
              <h1 className="auth-title">Đăng ký tài khoản</h1>
              <p className="auth-subtitle">
                Tạo tài khoản quản trị mới để bắt đầu giám sát hạ tầng của bạn.
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="register-username">Tên đăng nhập (ít nhất 3 ký tự) *</label>
              <input
                id="register-username"
                type="text"
                className="form-input"
                placeholder="VD: trungchau, lead_admin..."
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                minLength={3}
              />
              <span className="form-hint">
                Tên đăng nhập và email này sẽ hiển thị cùng nhau trong không gian làm việc.
              </span>
            </div>

            <div className="form-group">
              <label htmlFor="register-email">Địa chỉ Email *</label>
              <input
                id="register-email"
                type="email"
                className="form-input"
                placeholder="VD: user@sentinelx.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="register-password">Mật khẩu *</label>
              <div className="password-input-wrapper">
                <input
                  id="register-password"
                  type={showPassword ? "text" : "password"}
                  className="form-input"
                  placeholder="Tối thiểu 8 ký tự, có in hoa, số & ký tự đặc biệt"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  title={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Password Validation Checklist */}
            {password.length > 0 && (
              <div className="password-criteria-panel">
                <span className="criteria-heading">Tiêu chuẩn mật khẩu an toàn:</span>
                <ul className="criteria-list">
                  <li className={`criteria-item ${criteria.minLength ? "valid" : ""}`}>
                    {criteria.minLength ? <Check size={13} /> : <X size={13} />}
                    <span>Ít nhất 8 ký tự</span>
                  </li>
                  <li className={`criteria-item ${criteria.hasUppercase ? "valid" : ""}`}>
                    {criteria.hasUppercase ? <Check size={13} /> : <X size={13} />}
                    <span>Có ít nhất 1 chữ in hoa (A-Z)</span>
                  </li>
                  <li className={`criteria-item ${criteria.hasAlphaNumeric ? "valid" : ""}`}>
                    {criteria.hasAlphaNumeric ? <Check size={13} /> : <X size={13} />}
                    <span>Bao gồm cả chữ và số (a-z, 0-9)</span>
                  </li>
                  <li className={`criteria-item ${criteria.hasSpecialChar ? "valid" : ""}`}>
                    {criteria.hasSpecialChar ? <Check size={13} /> : <X size={13} />}
                    <span>Có ít nhất 1 ký tự đặc biệt (!@#$%...)</span>
                  </li>
                </ul>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="register-confirm">Xác nhận mật khẩu *</label>
              <div className="password-input-wrapper">
                <input
                  id="register-confirm"
                  type={showConfirmPassword ? "text" : "password"}
                  className="form-input"
                  placeholder="Nhập lại mật khẩu vừa tạo"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  title={showConfirmPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  tabIndex={-1}
                >
                  {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary auth-submit-btn"
              disabled={loading || username.trim().length < 3 || !email.trim() || !password || !confirmPassword}
            >
              {loading ? "Đang tạo tài khoản..." : "Đăng ký tài khoản"}
            </button>

            <div className="auth-footer-nav">
              <span>Đã có tài khoản?</span>
              <button
                type="button"
                className="auth-link-bold"
                onClick={() => switchMode("login")}
              >
                Đăng nhập ngay
              </button>
            </div>
          </form>
        )}

        {/* --- MODE: FORGOT PASSWORD --- */}
        {mode === "forgot" && (
          <form onSubmit={handleForgotSubmit} className="auth-form">
            <div className="auth-title-group">
              <h1 className="auth-title">Quên mật khẩu</h1>
              <p className="auth-subtitle">
                Đặt lại mật khẩu mới cho tài khoản quản trị của bạn bằng Email.
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="forgot-email">Địa chỉ Email đã đăng ký *</label>
              <input
                id="forgot-email"
                type="email"
                className="form-input"
                placeholder="VD: admin@sentinelx.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="forgot-new-password">Mật khẩu mới *</label>
              <div className="password-input-wrapper">
                <input
                  id="forgot-new-password"
                  type={showPassword ? "text" : "password"}
                  className="form-input"
                  placeholder="Tối thiểu 8 ký tự, có in hoa, số & ký tự đặc biệt"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  title={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Password Validation Checklist */}
            {password.length > 0 && (
              <div className="password-criteria-panel">
                <span className="criteria-heading">Tiêu chuẩn mật khẩu an toàn:</span>
                <ul className="criteria-list">
                  <li className={`criteria-item ${criteria.minLength ? "valid" : ""}`}>
                    {criteria.minLength ? <Check size={13} /> : <X size={13} />}
                    <span>Ít nhất 8 ký tự</span>
                  </li>
                  <li className={`criteria-item ${criteria.hasUppercase ? "valid" : ""}`}>
                    {criteria.hasUppercase ? <Check size={13} /> : <X size={13} />}
                    <span>Có ít nhất 1 chữ in hoa (A-Z)</span>
                  </li>
                  <li className={`criteria-item ${criteria.hasAlphaNumeric ? "valid" : ""}`}>
                    {criteria.hasAlphaNumeric ? <Check size={13} /> : <X size={13} />}
                    <span>Bao gồm cả chữ và số (a-z, 0-9)</span>
                  </li>
                  <li className={`criteria-item ${criteria.hasSpecialChar ? "valid" : ""}`}>
                    {criteria.hasSpecialChar ? <Check size={13} /> : <X size={13} />}
                    <span>Có ít nhất 1 ký tự đặc biệt (!@#$%...)</span>
                  </li>
                </ul>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="forgot-confirm">Xác nhận mật khẩu mới *</label>
              <div className="password-input-wrapper">
                <input
                  id="forgot-confirm"
                  type={showConfirmPassword ? "text" : "password"}
                  className="form-input"
                  placeholder="Nhập lại mật khẩu mới"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  title={showConfirmPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  tabIndex={-1}
                >
                  {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary auth-submit-btn"
              disabled={loading || !email.trim() || !password || !confirmPassword}
            >
              {loading ? "Đang cập nhật..." : "Lưu mật khẩu mới"}
            </button>

            <div className="auth-footer-nav">
              <button
                type="button"
                className="auth-link-bold"
                onClick={() => switchMode("login")}
              >
                ← Quay lại Đăng nhập
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

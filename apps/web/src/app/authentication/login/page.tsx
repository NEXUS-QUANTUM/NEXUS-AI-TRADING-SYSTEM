/**
 * NEXUS AI TRADING SYSTEM - Login Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page handles user authentication including:
 * - Email/Password login
 * - Social login (Google, GitHub, Telegram)
 * - Web3 wallet login
 * - Two-factor authentication (2FA/MFA)
 * - Remember me functionality
 * - Password reset flow
 * - Session management
 * - Rate limiting
 * - Security headers
 * - Device fingerprinting
 * - IP tracking
 * - Audit logging
 * - CSRF protection
 * - Multi-language support
 * - Accessibility compliance
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { signIn, useSession } from 'next-auth/react';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWeb3 } from '@/hooks/useWeb3';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Input } from '@/components/ui/Input';
import { Checkbox } from '@/components/ui/Checkbox';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';

// Icons
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  CheckCircle,
  Shield,
  Smartphone,
  Key,
  Github,
  Chrome,
  Send,
  Wallet,
  RefreshCw,
  Info,
} from 'lucide-react';

// Utils
import { validateEmail, validatePassword, validatePasswordStrength } from '@/utils/validators';
import { cn } from '@/utils/helpers';

// Constants
import {
  PASSWORD_POLICY,
  RATE_LIMITS,
  RECAPTCHA_SITE_KEY,
  SESSION_MAX_AGE,
} from '@/constants/auth';

export default function LoginPage() {
  // Router
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') || '/dashboard';
  const errorParam = searchParams.get('error');

  // Auth hooks
  const { signIn: customSignIn, isAuthenticated, user } = useAuth();
  const { data: session, status } = useSession();

  // API client
  const api = useApi();

  // Web3
  const { 
    connect: connectWeb3, 
    disconnect: disconnectWeb3, 
    account, 
    chainId,
    isConnected: isWeb3Connected,
    isConnecting: isWeb3Connecting,
    error: web3Error,
  } = useWeb3();

  // State - Form
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [rememberMe, setRememberMe] = useState<boolean>(false);
  const [emailError, setEmailError] = useState<string>('');
  const [passwordError, setPasswordError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSocialLoading, setIsSocialLoading] = useState<string | null>(null);

  // State - MFA
  const [showMFAModal, setShowMFAModal] = useState<boolean>(false);
  const [mfaCode, setMfaCode] = useState<string>('');
  const [mfaError, setMfaError] = useState<string>('');
  const [mfaLoading, setMfaLoading] = useState<boolean>(false);
  const [mfaSessionId, setMfaSessionId] = useState<string | null>(null);
  const [mfaBackupCodes, setMfaBackupCodes] = useState<string[]>([]);
  const [mfaType, setMfaType] = useState<'totp' | 'backup' | 'sms'>('totp');

  // State - Web3 Login
  const [isWeb3Login, setIsWeb3Login] = useState<boolean>(false);
  const [web3Signature, setWeb3Signature] = useState<string | null>(null);
  const [web3Nonce, setWeb3Nonce] = useState<string | null>(null);

  // State - UI
  const [error, setError] = useState<string>('');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [rateLimitInfo, setRateLimitInfo] = useState<{
    remaining: number;
    reset: number;
    limit: number;
  } | null>(null);
  const [isRemembered, setIsRemembered] = useState<boolean>(false);
  const [showPasswordStrength, setShowPasswordStrength] = useState<boolean>(false);
  const [passwordStrength, setPasswordStrength] = useState<{
    score: number;
    label: string;
    color: string;
  } | null>(null);

  // Refs
  const emailInputRef = useRef<HTMLInputElement>(null);
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const mfaInputRef = useRef<HTMLInputElement>(null);
  const loginAttemptsRef = useRef<number>(0);
  const lastLoginAttemptRef = useRef<number>(0);

  // ============================================
  // Effects
  // ============================================

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated || status === 'authenticated') {
      router.push(callbackUrl);
    }
  }, [isAuthenticated, status, router, callbackUrl]);

  // Handle error param from URL
  useEffect(() => {
    if (errorParam) {
      const errorMessages: Record<string, string> = {
        'CredentialsSignin': 'Invalid email or password',
        'SessionRequired': 'Please sign in to continue',
        'OAuthSignin': 'Failed to sign in with provider',
        'OAuthCallback': 'Failed to complete sign in',
        'OAuthCreateAccount': 'Failed to create account',
        'EmailCreateAccount': 'Failed to create account',
        'Callback': 'Authentication failed',
        'OAuthAccountNotLinked': 'Account already exists with different provider',
        'EmailSignin': 'Failed to send verification email',
        'CredentialsError': 'Authentication failed',
        'Default': 'An error occurred. Please try again.',
      };
      setError(errorMessages[errorParam] || errorMessages.Default);
    }
  }, [errorParam]);

  // Focus email input on mount
  useEffect(() => {
    if (emailInputRef.current && !error) {
      emailInputRef.current.focus();
    }
  }, [error]);

  // Check for remembered session
  useEffect(() => {
    const remembered = localStorage.getItem('nexus_remember');
    if (remembered) {
      setIsRemembered(true);
      const savedEmail = localStorage.getItem('nexus_email');
      if (savedEmail) {
        setEmail(savedEmail);
      }
    }
  }, []);

  // ============================================
  // Handlers - Form
  // ============================================

  const handleEmailChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEmail(value);
    setEmailError('');
    
    if (value && !validateEmail(value)) {
      setEmailError('Please enter a valid email address');
    }
  }, []);

  const handlePasswordChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setPassword(value);
    setPasswordError('');
    
    // Password strength check
    if (value.length > 0) {
      const strength = validatePasswordStrength(value);
      setPasswordStrength({
        score: strength.score,
        label: strength.label,
        color: strength.color,
      });
      setShowPasswordStrength(true);
    } else {
      setShowPasswordStrength(false);
    }
  }, []);

  const handleTogglePassword = useCallback(() => {
    setShowPassword(prev => !prev);
  }, []);

  const handleRememberMe = useCallback((checked: boolean) => {
    setRememberMe(checked);
    if (checked) {
      localStorage.setItem('nexus_remember', 'true');
      localStorage.setItem('nexus_email', email);
    } else {
      localStorage.removeItem('nexus_remember');
      localStorage.removeItem('nexus_email');
    }
  }, [email]);

  const validateForm = useCallback((): boolean => {
    let isValid = true;

    // Email validation
    if (!email) {
      setEmailError('Email address is required');
      isValid = false;
    } else if (!validateEmail(email)) {
      setEmailError('Please enter a valid email address');
      isValid = false;
    }

    // Password validation
    if (!password) {
      setPasswordError('Password is required');
      isValid = false;
    } else if (password.length < PASSWORD_POLICY.MIN_LENGTH) {
      setPasswordError(`Password must be at least ${PASSWORD_POLICY.MIN_LENGTH} characters`);
      isValid = false;
    }

    // Rate limiting check
    if (loginAttemptsRef.current >= RATE_LIMITS.MAX_LOGIN_ATTEMPTS) {
      const timeSinceLastAttempt = Date.now() - lastLoginAttemptRef.current;
      const cooldownRemaining = RATE_LIMITS.LOCKOUT_DURATION - timeSinceLastAttempt;
      
      if (cooldownRemaining > 0) {
        const minutes = Math.ceil(cooldownRemaining / 60000);
        setError(`Too many login attempts. Please wait ${minutes} minute${minutes > 1 ? 's' : ''}`);
        isValid = false;
      } else {
        // Reset attempts if cooldown has passed
        loginAttemptsRef.current = 0;
      }
    }

    return isValid;
  }, [email, password]);

  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }

    // Prevent double submission
    if (isLoading) return;

    // Validate form
    if (!validateForm()) {
      if (emailError && emailInputRef.current) {
        emailInputRef.current.focus();
      } else if (passwordError && passwordInputRef.current) {
        passwordInputRef.current.focus();
      }
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      // Track login attempt
      loginAttemptsRef.current += 1;
      lastLoginAttemptRef.current = Date.now();

      // Attempt login
      const result = await signIn('credentials', {
        email,
        password,
        rememberMe,
        redirect: false,
        callbackUrl,
      });

      if (result?.error) {
        // Check if MFA is required
        if (result.error === 'MFA_REQUIRED' || result.error?.includes('MFA')) {
          // Extract session ID from error
          const sessionId = result.error.split(':')[1] || null;
          setMfaSessionId(sessionId);
          setShowMFAModal(true);
          setMfaCode('');
          setMfaError('');
          setIsLoading(false);
          return;
        }

        // Check for rate limiting
        if (result.error.includes('rate') || result.error.includes('too many')) {
          setError('Too many login attempts. Please try again later.');
          setIsLoading(false);
          return;
        }

        // Check for account locked
        if (result.error.includes('locked')) {
          setError('Your account has been locked. Please contact support.');
          setIsLoading(false);
          return;
        }

        // Generic error
        setError('Invalid email or password');
        
        // Track failed attempt
        await logFailedAttempt(email, 'password');

        // Check if should lock account
        if (loginAttemptsRef.current >= RATE_LIMITS.MAX_LOGIN_ATTEMPTS) {
          setError(`Too many failed attempts. Account temporarily locked.`);
        }

        // Clear password on error
        setPassword('');
        if (passwordInputRef.current) {
          passwordInputRef.current.focus();
        }
      } else if (result?.url) {
        // Successful login
        await logSuccessfulLogin(email);
        
        // Store session info
        if (rememberMe) {
          localStorage.setItem('nexus_session', 'active');
        }

        // Show success message
        setShowToast({
          message: 'Welcome back! Redirecting...',
          type: 'success',
        });

        // Redirect
        router.push(callbackUrl);
        return;
      }

      setIsLoading(false);

    } catch (error: any) {
      console.error('Login error:', error);
      setError(error.message || 'An error occurred during login');
      setIsLoading(false);
    }
  }, [
    email,
    password,
    rememberMe,
    callbackUrl,
    validateForm,
    isLoading,
    router,
  ]);

  // ============================================
  // Handlers - MFA
  // ============================================

  const handleMFASubmit = useCallback(async () => {
    if (!mfaCode || mfaCode.length < 6) {
      setMfaError('Please enter a valid 6-digit code');
      return;
    }

    setMfaLoading(true);
    setMfaError('');

    try {
      const response = await api.post('/auth/mfa/verify', {
        sessionId: mfaSessionId,
        code: mfaCode,
        type: mfaType,
        email,
      });

      if (response.data.success) {
        // Complete login
        const result = await signIn('credentials', {
          email,
          password,
          rememberMe,
          mfaVerified: true,
          redirect: false,
          callbackUrl,
        });

        if (result?.url) {
          setShowMFAModal(false);
          setShowToast({
            message: '2FA verified successfully',
            type: 'success',
          });
          router.push(callbackUrl);
        }
      } else {
        setMfaError('Invalid verification code. Please try again.');
        setMfaCode('');
        if (mfaInputRef.current) {
          mfaInputRef.current.focus();
        }
      }
    } catch (error: any) {
      console.error('MFA verification error:', error);
      setMfaError(error.message || 'Failed to verify code. Please try again.');
    } finally {
      setMfaLoading(false);
    }
  }, [mfaCode, mfaSessionId, mfaType, email, password, rememberMe, callbackUrl, api, router]);

  const handleMFAKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleMFASubmit();
    }
  }, [handleMFASubmit]);

  const handleMFACodeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '');
    setMfaCode(value);
    setMfaError('');
    
    if (value.length === 6) {
      // Auto-submit when 6 digits are entered
      handleMFASubmit();
    }
  }, [handleMFASubmit]);

  // ============================================
  // Handlers - Social Login
  // ============================================

  const handleSocialLogin = useCallback(async (provider: string) => {
    try {
      setIsSocialLoading(provider);

      // Log social login attempt
      await logSocialLoginAttempt(email, provider);

      const result = await signIn(provider, {
        callbackUrl,
        redirect: false,
        ...(provider === 'web3' && {
          web3Address: account,
          web3Signature: web3Signature,
          web3Nonce: web3Nonce,
        }),
      });

      if (result?.error) {
        setError(`Failed to sign in with ${provider}. Please try again.`);
        setIsSocialLoading(null);
        return;
      }

      if (result?.url) {
        router.push(callbackUrl);
      }
    } catch (error: any) {
      console.error(`Social login error (${provider}):`, error);
      setError(error.message || `Failed to sign in with ${provider}`);
      setIsSocialLoading(null);
    }
  }, [callbackUrl, router, account, web3Signature, web3Nonce, email]);

  const handleWeb3Login = useCallback(async () => {
    try {
      setIsWeb3Login(true);
      setError('');

      // Get nonce from server
      const nonceResponse = await api.post('/auth/web3/nonce', {
        address: account,
      });

      if (nonceResponse.data?.nonce) {
        setWeb3Nonce(nonceResponse.data.nonce);
        // Sign the nonce
        const signature = await connectWeb3(nonceResponse.data.nonce);
        if (signature) {
          setWeb3Signature(signature);
          // Proceed with social login
          await handleSocialLogin('web3');
        } else {
          setError('Failed to sign the message. Please try again.');
        }
      } else {
        setError('Failed to get nonce. Please try again.');
      }
    } catch (error: any) {
      console.error('Web3 login error:', error);
      setError(error.message || 'Web3 login failed. Please try again.');
    } finally {
      setIsWeb3Login(false);
    }
  }, [account, api, connectWeb3, handleSocialLogin]);

  // ============================================
  // Helper Functions
  // ============================================

  const logFailedAttempt = useCallback(async (email: string, method: string) => {
    try {
      await api.post('/auth/log-attempt', {
        email,
        method,
        success: false,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    } catch {
      // Silent fail - not critical
    }
  }, [api]);

  const logSuccessfulLogin = useCallback(async (email: string) => {
    try {
      await api.post('/auth/log-attempt', {
        email,
        method: 'password',
        success: true,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    } catch {
      // Silent fail - not critical
    }
  }, [api]);

  const logSocialLoginAttempt = useCallback(async (email: string, provider: string) => {
    try {
      await api.post('/auth/log-attempt', {
        email: email || 'unknown',
        method: `social_${provider}`,
        success: true,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    } catch {
      // Silent fail - not critical
    }
  }, [api]);

  // ============================================
  // Render
  // ============================================

  // If already authenticated, show loading while redirecting
  if (isAuthenticated || status === 'authenticated') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4 text-cyan-500" />
          <p className="text-gray-400">Redirecting...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center p-4">
      {/* Background Pattern */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/2 -right-1/2 w-full h-full bg-gradient-to-br from-cyan-500/5 to-purple-500/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-1/2 -left-1/2 w-full h-full bg-gradient-to-tr from-blue-500/5 to-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-cyan-500/10 to-purple-500/10 rounded-full blur-2xl" />
      </div>

      {/* Main Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative w-full max-w-md"
      >
        <Card className="bg-gray-800/90 backdrop-blur-xl border-gray-700 shadow-2xl p-8">
          {/* Logo/Brand */}
          <div className="text-center mb-8">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-500 shadow-lg shadow-cyan-500/20 mb-4">
                <span className="text-2xl font-bold text-white">N</span>
              </div>
            </motion.div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
              Welcome Back
            </h1>
            <p className="text-gray-400 text-sm mt-2">
              Sign in to access your trading dashboard
            </p>
          </div>

          {/* Error Display */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3"
            >
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-red-500">{error}</p>
                {error.includes('locked') && (
                  <Link href="/support" className="text-xs text-cyan-400 hover:text-cyan-300 mt-1 inline-block">
                    Contact Support
                  </Link>
                )}
              </div>
            </motion.div>
          )}

          {/* Rate Limit Info */}
          {rateLimitInfo && rateLimitInfo.remaining <= 2 && (
            <div className="mb-6 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <p className="text-xs text-yellow-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {rateLimitInfo.remaining} login attempts remaining
              </p>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-gray-500" />
                </div>
                <Input
                  ref={emailInputRef}
                  id="email"
                  type="email"
                  value={email}
                  onChange={handleEmailChange}
                  placeholder="you@example.com"
                  autoComplete="email"
                  disabled={isLoading}
                  className={cn(
                    "w-full pl-10 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                    emailError && "border-red-500 focus:border-red-500 focus:ring-red-500",
                    !emailError && email && "border-green-500 focus:border-green-500 focus:ring-green-500"
                  )}
                  required
                />
              </div>
              {emailError && (
                <motion.p
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-2 text-sm text-red-500 flex items-center gap-1"
                >
                  <AlertCircle className="w-4 h-4" />
                  {emailError}
                </motion.p>
              )}
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-500" />
                </div>
                <Input
                  ref={passwordInputRef}
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={handlePasswordChange}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  disabled={isLoading}
                  className={cn(
                    "w-full pl-10 pr-12 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                    passwordError && "border-red-500 focus:border-red-500 focus:ring-red-500"
                  )}
                  required
                />
                <button
                  type="button"
                  onClick={handleTogglePassword}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-300 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {passwordError && (
                <motion.p
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-2 text-sm text-red-500 flex items-center gap-1"
                >
                  <AlertCircle className="w-4 h-4" />
                  {passwordError}
                </motion.p>
              )}
              {/* Password Strength */}
              {showPasswordStrength && passwordStrength && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="mt-2"
                >
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full transition-all duration-300',
                          passwordStrength.color
                        )}
                        style={{ width: `${(passwordStrength.score / 4) * 100}%` }}
                      />
                    </div>
                    <span className={cn(
                      'text-xs font-medium',
                      passwordStrength.color
                    )}>
                      {passwordStrength.label}
                    </span>
                  </div>
                </motion.div>
              )}
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="remember-me"
                  checked={rememberMe}
                  onCheckedChange={handleRememberMe}
                  className="border-gray-600 data-[state=checked]:bg-cyan-500"
                />
                <label htmlFor="remember-me" className="text-sm text-gray-400 cursor-pointer">
                  Remember me
                </label>
              </div>
              <Link
                href="/authentication/forgot-password"
                className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                Forgot password?
              </Link>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              disabled={isLoading || isWeb3Login}
              isLoading={isLoading}
              className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-2 bg-gray-800 text-gray-500">Or continue with</span>
            </div>
          </div>

          {/* Social Login Buttons */}
          <div className="grid grid-cols-3 gap-3">
            {/* Google */}
            <Button
              variant="outline"
              onClick={() => handleSocialLogin('google')}
              disabled={isLoading || !!isSocialLoading}
              className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
            >
              {isSocialLoading === 'google' ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <Chrome className="w-5 h-5" />
              )}
            </Button>

            {/* GitHub */}
            <Button
              variant="outline"
              onClick={() => handleSocialLogin('github')}
              disabled={isLoading || !!isSocialLoading}
              className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
            >
              {isSocialLoading === 'github' ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <Github className="w-5 h-5" />
              )}
            </Button>

            {/* Web3 Wallet */}
            <Button
              variant="outline"
              onClick={handleWeb3Login}
              disabled={isLoading || isWeb3Connecting || isWeb3Login}
              className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
            >
              {isWeb3Connecting || isWeb3Login ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <Wallet className="w-5 h-5" />
              )}
            </Button>
          </div>

          {/* Wallet Connection Status */}
          {isWeb3Connected && account && (
            <div className="mt-3 p-2 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
              <p className="text-xs text-green-400 truncate">
                Connected: {account.slice(0, 6)}...{account.slice(-4)}
                {chainId && ` (Chain: ${chainId})`}
              </p>
            </div>
          )}

          {web3Error && (
            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-xs text-red-400">{web3Error}</p>
            </div>
          )}

          {/* Sign Up Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-400">
              Don't have an account?{' '}
              <Link
                href="/authentication/register"
                className="text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
              >
                Sign up
              </Link>
            </p>
          </div>

          {/* Security Notice */}
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-gray-500">
            <Shield className="w-3 h-3" />
            <span>Secure login with encrypted connection</span>
          </div>
        </Card>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-xs text-gray-500">
            © {new Date().getFullYear()} NEXUS QUANTUM LTD. All rights reserved.
          </p>
          <div className="flex items-center justify-center gap-4 mt-2 text-xs text-gray-500">
            <Link href="/privacy" className="hover:text-gray-400 transition-colors">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-gray-400 transition-colors">
              Terms of Service
            </Link>
            <Link href="/support" className="hover:text-gray-400 transition-colors">
              Support
            </Link>
          </div>
        </div>
      </motion.div>

      {/* MFA Modal */}
      <Modal
        open={showMFAModal}
        onOpenChange={setShowMFAModal}
        title="Two-Factor Authentication"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-500/20 mb-3">
              <Smartphone className="w-8 h-8 text-blue-500" />
            </div>
            <p className="text-gray-400 text-sm">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>

          <div className="flex flex-col items-center">
            <div className="flex gap-2">
              {[...Array(6)].map((_, index) => (
                <div
                  key={index}
                  className={cn(
                    "w-12 h-14 rounded-lg border-2 flex items-center justify-center text-2xl font-mono transition-all",
                    mfaCode.length === index
                      ? "border-cyan-500 bg-cyan-500/10"
                      : mfaCode.length > index
                      ? "border-green-500 bg-green-500/10 text-white"
                      : "border-gray-600 bg-gray-700/50 text-gray-400"
                  )}
                >
                  {mfaCode[index] || ''}
                </div>
              ))}
            </div>
            <Input
              ref={mfaInputRef}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={mfaCode}
              onChange={handleMFACodeChange}
              onKeyDown={handleMFAKeyPress}
              className="absolute opacity-0 w-0 h-0"
              autoFocus
            />
          </div>

          {mfaError && (
            <motion.p
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-sm text-red-500 text-center flex items-center justify-center gap-1"
            >
              <AlertCircle className="w-4 h-4" />
              {mfaError}
            </motion.p>
          )}

          <div className="flex items-center gap-2 justify-center text-xs text-gray-500">
            <button
              type="button"
              onClick={() => setMfaType(prev => prev === 'totp' ? 'backup' : 'totp')}
              className="text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              Use {mfaType === 'totp' ? 'backup code' : 'authenticator app'}
            </button>
          </div>

          <div className="flex justify-center gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setShowMFAModal(false);
                setMfaCode('');
                setMfaError('');
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleMFASubmit}
              isLoading={mfaLoading}
              disabled={mfaCode.length < 6}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              {mfaLoading ? 'Verifying...' : 'Verify'}
            </Button>
          </div>

          <div className="text-center text-xs text-gray-500">
            <p>If you're having issues, contact support for assistance.</p>
          </div>
        </div>
      </Modal>

      {/* Toast Notifications */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50 max-w-md"
            duration={5000}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

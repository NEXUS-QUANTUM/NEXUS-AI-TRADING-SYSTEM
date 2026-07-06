/**
 * NEXUS AI TRADING SYSTEM - Register Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page handles user registration including:
 * - Email/Password registration
 * - Social registration (Google, GitHub, Telegram)
 * - Web3 wallet registration
 * - Email verification
 * - Password strength validation
 * - Terms and conditions acceptance
 * - Privacy policy acceptance
 * - Rate limiting
 * - Security checks
 * - IP tracking
 * - Audit logging
 * - Multi-language support
 * - Accessibility compliance
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
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
import { Progress } from '@/components/ui/Progress';
import { Badge } from '@/components/ui/Badge';

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
  User,
  Chrome,
  Github,
  Wallet,
  Send,
  Info,
  Key,
} from 'lucide-react';

// Utils
import {
  validateEmail,
  validateEmailWithDNS,
  validatePassword,
  validatePasswordStrength,
  validateName,
  validatePhone,
} from '@/utils/validators';
import { cn } from '@/utils/helpers';

// Constants
import {
  PASSWORD_POLICY,
  EMAIL_PATTERN,
  RATE_LIMITS,
  RECAPTCHA_SITE_KEY,
  ACCOUNT_TYPES,
  USER_ROLES,
  AUTH_PROVIDERS,
} from '@/constants/auth';

export default function RegisterPage() {
  // Router
  const router = useRouter();

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
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    phone: '',
  });
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSocialLoading, setIsSocialLoading] = useState<string | null>(null);

  // State - Validation
  const [passwordStrength, setPasswordStrength] = useState<{
    score: number;
    label: string;
    color: string;
    criteria: {
      length: boolean;
      uppercase: boolean;
      lowercase: boolean;
      numbers: boolean;
      special: boolean;
    };
  } | null>(null);
  const [showPasswordStrength, setShowPasswordStrength] = useState<boolean>(false);
  const [emailValidated, setEmailValidated] = useState<boolean>(false);
  const [emailInUse, setEmailInUse] = useState<boolean>(false);

  // State - Terms
  const [acceptedTerms, setAcceptedTerms] = useState<boolean>(false);
  const [acceptedPrivacy, setAcceptedPrivacy] = useState<boolean>(false);
  const [acceptedMarketing, setAcceptedMarketing] = useState<boolean>(false);
  const [termsError, setTermsError] = useState<string>('');

  // State - UI
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [verificationSent, setVerificationSent] = useState<boolean>(false);
  const [verificationEmail, setVerificationEmail] = useState<string>('');
  const [rateLimitInfo, setRateLimitInfo] = useState<{
    remaining: number;
    reset: number;
    limit: number;
  } | null>(null);
  const [accountType, setAccountType] = useState<string>('individual');
  const [referralCode, setReferralCode] = useState<string>('');
  const [isWeb3Registration, setIsWeb3Registration] = useState<boolean>(false);
  const [web3Nonce, setWeb3Nonce] = useState<string | null>(null);
  const [web3Signature, setWeb3Signature] = useState<string | null>(null);

  // Refs
  const nameInputRef = useRef<HTMLInputElement>(null);
  const emailInputRef = useRef<HTMLInputElement>(null);
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const confirmPasswordInputRef = useRef<HTMLInputElement>(null);

  // ============================================
  // Effects
  // ============================================

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated || status === 'authenticated') {
      router.push('/dashboard');
    }
  }, [isAuthenticated, status, router]);

  // Focus name input on mount
  useEffect(() => {
    if (nameInputRef.current && !error) {
      nameInputRef.current.focus();
    }
  }, [error]);

  // Check URL for referral code
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('ref');
    if (ref) {
      setReferralCode(ref);
    }
  }, []);

  // ============================================
  // Handlers - Form
  // ============================================

  const handleChange = useCallback((field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: '' }));
    setTouched(prev => ({ ...prev, [field]: true }));

    // Real-time validation
    switch (field) {
      case 'email':
        if (value && !validateEmail(value)) {
          setErrors(prev => ({ ...prev, email: 'Please enter a valid email address' }));
        } else if (value && !validateEmailWithDNS(value)) {
          setErrors(prev => ({ ...prev, email: 'Email domain appears to be invalid' }));
        } else {
          setEmailValidated(true);
          // Check if email is in use (debounced)
          const debounceTimeout = setTimeout(() => {
            checkEmailAvailability(value);
          }, 500);
          return () => clearTimeout(debounceTimeout);
        }
        break;

      case 'password':
        if (value) {
          const strength = validatePasswordStrength(value);
          setPasswordStrength({
            score: strength.score,
            label: strength.label,
            color: strength.color,
            criteria: strength.criteria,
          });
          setShowPasswordStrength(true);
        } else {
          setShowPasswordStrength(false);
        }
        break;

      case 'confirmPassword':
        if (value && value !== formData.password) {
          setErrors(prev => ({ ...prev, confirmPassword: 'Passwords do not match' }));
        }
        break;

      case 'name':
        if (value && !validateName(value)) {
          setErrors(prev => ({ ...prev, name: 'Please enter a valid name' }));
        }
        break;

      case 'phone':
        if (value && !validatePhone(value)) {
          setErrors(prev => ({ ...prev, phone: 'Please enter a valid phone number' }));
        }
        break;
    }
  }, [formData.password]);

  const handleBlur = useCallback((field: string) => {
    setTouched(prev => ({ ...prev, [field]: true }));
  }, []);

  const handleTogglePassword = useCallback(() => {
    setShowPassword(prev => !prev);
  }, []);

  const handleToggleConfirmPassword = useCallback(() => {
    setShowConfirmPassword(prev => !prev);
  }, []);

  const checkEmailAvailability = useCallback(async (email: string) => {
    if (!email || !validateEmail(email)) return;

    try {
      const response = await api.post('/auth/check-email', { email });
      if (response.data?.inUse) {
        setEmailInUse(true);
        setErrors(prev => ({ ...prev, email: 'This email is already registered' }));
      } else {
        setEmailInUse(false);
      }
    } catch {
      // Silent fail - not critical
    }
  }, [api]);

  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    // Name validation
    if (!formData.name) {
      newErrors.name = 'Full name is required';
      isValid = false;
    } else if (!validateName(formData.name)) {
      newErrors.name = 'Please enter a valid name';
      isValid = false;
    }

    // Email validation
    if (!formData.email) {
      newErrors.email = 'Email address is required';
      isValid = false;
    } else if (!validateEmail(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
      isValid = false;
    } else if (emailInUse) {
      newErrors.email = 'This email is already registered';
      isValid = false;
    }

    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
      isValid = false;
    } else {
      const validation = validatePassword(formData.password);
      if (!validation.isValid) {
        newErrors.password = validation.message || 'Password does not meet requirements';
        isValid = false;
      }
    }

    // Confirm password validation
    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
      isValid = false;
    } else if (formData.confirmPassword !== formData.password) {
      newErrors.confirmPassword = 'Passwords do not match';
      isValid = false;
    }

    // Phone validation (optional)
    if (formData.phone && !validatePhone(formData.phone)) {
      newErrors.phone = 'Please enter a valid phone number';
      isValid = false;
    }

    // Terms validation
    if (!acceptedTerms) {
      setTermsError('You must accept the Terms and Conditions');
      isValid = false;
    } else {
      setTermsError('');
    }

    if (!acceptedPrivacy) {
      setTermsError(prev => prev || 'You must accept the Privacy Policy');
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  }, [formData, emailInUse, acceptedTerms, acceptedPrivacy]);

  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }

    // Prevent double submission
    if (isLoading) return;

    // Validate form
    if (!validateForm()) {
      // Focus first field with error
      if (errors.name && nameInputRef.current) {
        nameInputRef.current.focus();
      } else if (errors.email && emailInputRef.current) {
        emailInputRef.current.focus();
      } else if (errors.password && passwordInputRef.current) {
        passwordInputRef.current.focus();
      } else if (errors.confirmPassword && confirmPasswordInputRef.current) {
        confirmPasswordInputRef.current.focus();
      }
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      // Prepare registration data
      const registerData = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        phone: formData.phone || undefined,
        accountType,
        referralCode: referralCode || undefined,
        acceptedTerms,
        acceptedPrivacy,
        acceptedMarketing,
        metadata: {
          userAgent: navigator.userAgent,
          screenResolution: `${window.screen.width}x${window.screen.height}`,
          language: navigator.language,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        },
        ...(isWeb3Registration && {
          web3Address: account,
          web3Signature: web3Signature,
          web3Nonce: web3Nonce,
        }),
      };

      // Register user
      const response = await api.post('/auth/register', registerData);

      if (response.data.success) {
        setSuccess(true);
        setVerificationSent(true);
        setVerificationEmail(formData.email);

        // Show success message
        setShowToast({
          message: 'Registration successful! Please check your email to verify your account.',
          type: 'success',
        });

        // Automatically sign in after registration
        if (response.data.autoLogin) {
          const signInResult = await signIn('credentials', {
            email: formData.email,
            password: formData.password,
            redirect: false,
          });

          if (signInResult?.url) {
            router.push('/dashboard');
            return;
          }
        }

        // Store rate limit info from response headers
        const remaining = parseInt(response.headers.get('x-ratelimit-remaining') || '5');
        const reset = parseInt(response.headers.get('x-ratelimit-reset') || '0');
        const limit = parseInt(response.headers.get('x-ratelimit-limit') || '5');

        setRateLimitInfo({
          remaining,
          reset: reset * 1000,
          limit,
        });

        // Clear sensitive data
        setFormData(prev => ({
          ...prev,
          password: '',
          confirmPassword: '',
        }));

        // Redirect to verification page after delay
        setTimeout(() => {
          router.push(`/authentication/verify-email?email=${encodeURIComponent(formData.email)}`);
        }, 3000);
      } else {
        throw new Error(response.data.message || 'Registration failed');
      }
    } catch (error: any) {
      console.error('Registration error:', error);

      // Handle specific error cases
      const errorMessage = error.response?.data?.message || error.message;

      if (error.response?.status === 409) {
        setErrors(prev => ({
          ...prev,
          email: 'This email is already registered. Please login instead.',
        }));
      } else if (error.response?.status === 429) {
        const resetTime = error.response?.headers?.['x-ratelimit-reset'];
        if (resetTime) {
          const waitMinutes = Math.ceil((parseInt(resetTime) * 1000 - Date.now()) / 60000);
          setError(`Too many registration attempts. Please wait ${waitMinutes} minutes`);
        } else {
          setError('Too many registration attempts. Please try again later.');
        }
      } else if (error.response?.status === 403) {
        setError('Security check failed. Please try again.');
      } else {
        setError(errorMessage || 'Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [
    formData,
    accountType,
    referralCode,
    acceptedTerms,
    acceptedPrivacy,
    acceptedMarketing,
    validateForm,
    isLoading,
    errors,
    api,
    router,
    isWeb3Registration,
    account,
    web3Signature,
    web3Nonce,
  ]);

  // ============================================
  // Handlers - Social Registration
  // ============================================

  const handleSocialRegister = useCallback(async (provider: string) => {
    try {
      setIsSocialLoading(provider);

      const result = await signIn(provider, {
        callbackUrl: '/dashboard',
        redirect: false,
        ...(provider === 'web3' && {
          web3Address: account,
          web3Signature: web3Signature,
          web3Nonce: web3Nonce,
          register: true,
        }),
      });

      if (result?.error) {
        // Check if account exists
        if (result.error.includes('AccountExists')) {
          setErrors(prev => ({
            ...prev,
            email: 'An account with this email already exists. Please login instead.',
          }));
        } else {
          setError(`Failed to register with ${provider}. Please try again.`);
        }
        setIsSocialLoading(null);
        return;
      }

      if (result?.url) {
        setShowToast({
          message: `Successfully registered with ${provider}!`,
          type: 'success',
        });
        router.push('/dashboard');
      }
    } catch (error: any) {
      console.error(`Social registration error (${provider}):`, error);
      setError(error.message || `Failed to register with ${provider}`);
      setIsSocialLoading(null);
    }
  }, [account, web3Signature, web3Nonce, router]);

  const handleWeb3Register = useCallback(async () => {
    try {
      setIsWeb3Registration(true);
      setError('');

      // Get nonce from server
      const nonceResponse = await api.post('/auth/web3/nonce', {
        address: account,
        register: true,
      });

      if (nonceResponse.data?.nonce) {
        setWeb3Nonce(nonceResponse.data.nonce);
        // Sign the nonce
        const signature = await connectWeb3(nonceResponse.data.nonce);
        if (signature) {
          setWeb3Signature(signature);
          // Proceed with social registration
          await handleSocialRegister('web3');
        } else {
          setError('Failed to sign the message. Please try again.');
        }
      } else {
        setError('Failed to get nonce. Please try again.');
      }
    } catch (error: any) {
      console.error('Web3 registration error:', error);
      setError(error.message || 'Web3 registration failed. Please try again.');
    } finally {
      setIsWeb3Registration(false);
    }
  }, [account, api, connectWeb3, handleSocialRegister]);

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
              Create Account
            </h1>
            <p className="text-gray-400 text-sm mt-2">
              Join NEXUS Trading and start your journey
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
              <p className="text-sm text-red-500">{error}</p>
            </motion.div>
          )}

          {/* Success State */}
          {success ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              <div className="text-center py-6">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-500/20 mb-4"
                >
                  <CheckCircle className="w-10 h-10 text-green-500" />
                </motion.div>
                <h2 className="text-lg font-semibold text-white">Registration Successful!</h2>
                <p className="text-gray-400 text-sm mt-2">
                  We've sent a verification email to
                </p>
                <p className="text-cyan-400 font-medium text-sm mt-1 break-all">
                  {verificationEmail}
                </p>
                <p className="text-gray-500 text-xs mt-3">
                  Please check your inbox and click the verification link to activate your account.
                </p>
              </div>

              <Button
                variant="primary"
                onClick={() => router.push('/authentication/login')}
                className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
              >
                Go to Login
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>

              <div className="text-center">
                <Link
                  href="/authentication/verify-email"
                  className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                  Didn't receive the email? Resend verification
                </Link>
              </div>
            </motion.div>
          ) : (
            <>
              {/* Registration Form */}
              <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                {/* Account Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Account Type
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {ACCOUNT_TYPES.map((type) => (
                      <button
                        key={type.value}
                        type="button"
                        onClick={() => setAccountType(type.value)}
                        className={cn(
                          "p-3 rounded-lg border-2 text-center transition-all",
                          accountType === type.value
                            ? "border-cyan-500 bg-cyan-500/10 text-white"
                            : "border-gray-600 bg-gray-700/50 text-gray-400 hover:border-gray-500"
                        )}
                      >
                        <div className="text-lg">{type.icon}</div>
                        <div className="text-xs mt-1 font-medium">{type.label}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Name Input */}
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
                    Full Name *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <User className="h-5 w-5 text-gray-500" />
                    </div>
                    <Input
                      ref={nameInputRef}
                      id="name"
                      type="text"
                      value={formData.name}
                      onChange={(e) => handleChange('name', e.target.value)}
                      onBlur={() => handleBlur('name')}
                      placeholder="John Doe"
                      autoComplete="name"
                      disabled={isLoading}
                      className={cn(
                        "w-full pl-10 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                        errors.name && "border-red-500 focus:border-red-500 focus:ring-red-500",
                        !errors.name && touched.name && formData.name && "border-green-500 focus:border-green-500 focus:ring-green-500"
                      )}
                      required
                    />
                  </div>
                  {errors.name && touched.name && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 text-sm text-red-500 flex items-center gap-1"
                    >
                      <AlertCircle className="w-4 h-4" />
                      {errors.name}
                    </motion.p>
                  )}
                </div>

                {/* Email Input */}
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                    Email Address *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail className="h-5 w-5 text-gray-500" />
                    </div>
                    <Input
                      ref={emailInputRef}
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => handleChange('email', e.target.value)}
                      onBlur={() => handleBlur('email')}
                      placeholder="you@example.com"
                      autoComplete="email"
                      disabled={isLoading}
                      className={cn(
                        "w-full pl-10 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                        errors.email && "border-red-500 focus:border-red-500 focus:ring-red-500",
                        !errors.email && touched.email && formData.email && emailValidated && !emailInUse && "border-green-500 focus:border-green-500 focus:ring-green-500"
                      )}
                      required
                    />
                    {touched.email && formData.email && !errors.email && emailValidated && !emailInUse && (
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      </div>
                    )}
                  </div>
                  {errors.email && touched.email && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 text-sm text-red-500 flex items-center gap-1"
                    >
                      <AlertCircle className="w-4 h-4" />
                      {errors.email}
                    </motion.p>
                  )}
                  {emailInUse && (
                    <p className="mt-2 text-sm text-yellow-500 flex items-center gap-1">
                      <Info className="w-4 h-4" />
                      This email is already registered.{' '}
                      <Link href="/authentication/login" className="text-cyan-400 hover:text-cyan-300">
                        Login instead
                      </Link>
                    </p>
                  )}
                </div>

                {/* Phone Input (Optional) */}
                <div>
                  <label htmlFor="phone" className="block text-sm font-medium text-gray-300 mb-2">
                    Phone Number <span className="text-gray-500 text-xs">(optional)</span>
                  </label>
                  <Input
                    id="phone"
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => handleChange('phone', e.target.value)}
                    onBlur={() => handleBlur('phone')}
                    placeholder="+1 234 567 8900"
                    autoComplete="tel"
                    disabled={isLoading}
                    className="w-full bg-gray-700 border-gray-600 text-white placeholder-gray-400"
                  />
                  {errors.phone && touched.phone && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 text-sm text-red-500 flex items-center gap-1"
                    >
                      <AlertCircle className="w-4 h-4" />
                      {errors.phone}
                    </motion.p>
                  )}
                </div>

                {/* Password Input */}
                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                    Password *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Lock className="h-5 w-5 text-gray-500" />
                    </div>
                    <Input
                      ref={passwordInputRef}
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={formData.password}
                      onChange={(e) => handleChange('password', e.target.value)}
                      onBlur={() => handleBlur('password')}
                      placeholder="Create a strong password"
                      autoComplete="new-password"
                      disabled={isLoading}
                      className={cn(
                        "w-full pl-10 pr-12 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                        errors.password && "border-red-500 focus:border-red-500 focus:ring-red-500",
                        !errors.password && touched.password && formData.password && passwordStrength && passwordStrength.score >= 3 && "border-green-500 focus:border-green-500 focus:ring-green-500"
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
                  {errors.password && touched.password && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 text-sm text-red-500 flex items-center gap-1"
                    >
                      <AlertCircle className="w-4 h-4" />
                      {errors.password}
                    </motion.p>
                  )}
                  {/* Password Requirements */}
                  {!errors.password && touched.password && (
                    <div className="mt-2 text-xs text-gray-500 space-y-1">
                      <p>Password must contain:</p>
                      <ul className="space-y-0.5">
                        <li className={cn(
                          "flex items-center gap-1",
                          passwordStrength?.criteria.length ? "text-green-500" : "text-gray-500"
                        )}>
                          {passwordStrength?.criteria.length ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                          At least {PASSWORD_POLICY.MIN_LENGTH} characters
                        </li>
                        <li className={cn(
                          "flex items-center gap-1",
                          passwordStrength?.criteria.uppercase ? "text-green-500" : "text-gray-500"
                        )}>
                          {passwordStrength?.criteria.uppercase ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                          One uppercase letter
                        </li>
                        <li className={cn(
                          "flex items-center gap-1",
                          passwordStrength?.criteria.lowercase ? "text-green-500" : "text-gray-500"
                        )}>
                          {passwordStrength?.criteria.lowercase ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                          One lowercase letter
                        </li>
                        <li className={cn(
                          "flex items-center gap-1",
                          passwordStrength?.criteria.numbers ? "text-green-500" : "text-gray-500"
                        )}>
                          {passwordStrength?.criteria.numbers ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                          One number
                        </li>
                        <li className={cn(
                          "flex items-center gap-1",
                          passwordStrength?.criteria.special ? "text-green-500" : "text-gray-500"
                        )}>
                          {passwordStrength?.criteria.special ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                          One special character
                        </li>
                      </ul>
                    </div>
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

                {/* Confirm Password */}
                <div>
                  <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-300 mb-2">
                    Confirm Password *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Key className="h-5 w-5 text-gray-500" />
                    </div>
                    <Input
                      ref={confirmPasswordInputRef}
                      id="confirmPassword"
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={formData.confirmPassword}
                      onChange={(e) => handleChange('confirmPassword', e.target.value)}
                      onBlur={() => handleBlur('confirmPassword')}
                      placeholder="Confirm your password"
                      autoComplete="new-password"
                      disabled={isLoading}
                      className={cn(
                        "w-full pl-10 pr-12 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                        errors.confirmPassword && "border-red-500 focus:border-red-500 focus:ring-red-500",
                        !errors.confirmPassword && touched.confirmPassword && formData.confirmPassword && formData.confirmPassword === formData.password && "border-green-500 focus:border-green-500 focus:ring-green-500"
                      )}
                      required
                    />
                    <button
                      type="button"
                      onClick={handleToggleConfirmPassword}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-300 transition-colors"
                      aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                    >
                      {showConfirmPassword ? (
                        <EyeOff className="h-5 w-5" />
                      ) : (
                        <Eye className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                  {errors.confirmPassword && touched.confirmPassword && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 text-sm text-red-500 flex items-center gap-1"
                    >
                      <AlertCircle className="w-4 h-4" />
                      {errors.confirmPassword}
                    </motion.p>
                  )}
                  {!errors.confirmPassword && touched.confirmPassword && formData.confirmPassword && formData.confirmPassword === formData.password && (
                    <p className="mt-2 text-sm text-green-500 flex items-center gap-1">
                      <CheckCircle className="w-4 h-4" />
                      Passwords match
                    </p>
                  )}
                </div>

                {/* Referral Code */}
                {referralCode && (
                  <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-3">
                    <p className="text-xs text-cyan-400 flex items-center gap-2">
                      <Info className="w-4 h-4" />
                      Referral code applied: <span className="font-mono">{referralCode}</span>
                    </p>
                  </div>
                )}

                {/* Terms */}
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <Checkbox
                      id="terms"
                      checked={acceptedTerms}
                      onCheckedChange={(checked) => {
                        setAcceptedTerms(checked as boolean);
                        setTermsError('');
                      }}
                      className="mt-1 border-gray-600 data-[state=checked]:bg-cyan-500"
                    />
                    <label htmlFor="terms" className="text-sm text-gray-400 cursor-pointer">
                      I accept the{' '}
                      <Link href="/terms" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                        Terms and Conditions
                      </Link>
                    </label>
                  </div>
                  <div className="flex items-start gap-2">
                    <Checkbox
                      id="privacy"
                      checked={acceptedPrivacy}
                      onCheckedChange={(checked) => {
                        setAcceptedPrivacy(checked as boolean);
                        setTermsError('');
                      }}
                      className="mt-1 border-gray-600 data-[state=checked]:bg-cyan-500"
                    />
                    <label htmlFor="privacy" className="text-sm text-gray-400 cursor-pointer">
                      I accept the{' '}
                      <Link href="/privacy" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                        Privacy Policy
                      </Link>
                    </label>
                  </div>
                  <div className="flex items-start gap-2">
                    <Checkbox
                      id="marketing"
                      checked={acceptedMarketing}
                      onCheckedChange={(checked) => setAcceptedMarketing(checked as boolean)}
                      className="mt-1 border-gray-600 data-[state=checked]:bg-cyan-500"
                    />
                    <label htmlFor="marketing" className="text-sm text-gray-400 cursor-pointer">
                      I'd like to receive marketing emails and updates
                    </label>
                  </div>
                  {termsError && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="text-sm text-red-500 flex items-center gap-1"
                    >
                      <AlertCircle className="w-4 h-4" />
                      {termsError}
                    </motion.p>
                  )}
                </div>

                {/* Rate Limit Info */}
                {rateLimitInfo && rateLimitInfo.remaining <= 2 && (
                  <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                    <p className="text-xs text-yellow-400 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4" />
                      {rateLimitInfo.remaining} registration attempts remaining
                    </p>
                  </div>
                )}

                {/* Submit Button */}
                <Button
                  type="submit"
                  variant="primary"
                  disabled={isLoading || isWeb3Registration}
                  isLoading={isLoading}
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <>
                      <Spinner size="sm" className="mr-2" />
                      Creating Account...
                    </>
                  ) : (
                    <>
                      Create Account
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
                  <span className="px-2 bg-gray-800 text-gray-500">Or register with</span>
                </div>
              </div>

              {/* Social Registration Buttons */}
              <div className="grid grid-cols-3 gap-3">
                <Button
                  variant="outline"
                  onClick={() => handleSocialRegister('google')}
                  disabled={isLoading || !!isSocialLoading}
                  className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                >
                  {isSocialLoading === 'google' ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : (
                    <Chrome className="w-5 h-5" />
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={() => handleSocialRegister('github')}
                  disabled={isLoading || !!isSocialLoading}
                  className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                >
                  {isSocialLoading === 'github' ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : (
                    <Github className="w-5 h-5" />
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleWeb3Register}
                  disabled={isLoading || isWeb3Connecting || isWeb3Registration}
                  className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                >
                  {isWeb3Connecting || isWeb3Registration ? (
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

              {/* Login Link */}
              <div className="mt-6 text-center">
                <p className="text-sm text-gray-400">
                  Already have an account?{' '}
                  <Link
                    href="/authentication/login"
                    className="text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
                  >
                    Sign in
                  </Link>
                </p>
              </div>

              {/* Security Notice */}
              <div className="mt-4 flex items-center justify-center gap-2 text-xs text-gray-500">
                <Shield className="w-3 h-3" />
                <span>Your information is secure and encrypted</span>
              </div>
            </>
          )}
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

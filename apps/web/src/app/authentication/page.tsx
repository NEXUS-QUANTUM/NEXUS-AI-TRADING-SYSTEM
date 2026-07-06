/**
 * NEXUS AI TRADING SYSTEM - Authentication Landing Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page serves as the authentication entry point with:
 * - Unified login/register interface
 * - Role-based redirection
 * - Session management
 * - Social login options
 * - Web3 wallet integration
 * - Security features
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
import { Badge } from '@/components/ui/Badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';

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
  Sparkles,
  TrendingUp,
  Brain,
  BarChart3,
  Zap,
  Globe,
  Clock,
  Award,
  ShieldCheck,
  Rocket,
  Users,
  Check,
  X,
} from 'lucide-react';

// Utils
import { validateEmail, validatePassword } from '@/utils/validators';
import { cn } from '@/utils/helpers';

// Constants
import { PASSWORD_POLICY, RATE_LIMITS } from '@/constants/auth';

export default function AuthenticationPage() {
  // Router
  const router = useRouter();
  const searchParams = typeof window !== 'undefined' 
    ? new URLSearchParams(window.location.search)
    : new URLSearchParams();
  const mode = searchParams.get('mode') || 'login';
  const callbackUrl = searchParams.get('callbackUrl') || '/dashboard';

  // Auth hooks
  const { isAuthenticated, user } = useAuth();
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

  // State - Form (Login)
  const [loginEmail, setLoginEmail] = useState<string>('');
  const [loginPassword, setLoginPassword] = useState<string>('');
  const [showLoginPassword, setShowLoginPassword] = useState<boolean>(false);
  const [rememberMe, setRememberMe] = useState<boolean>(false);
  const [loginErrors, setLoginErrors] = useState<Record<string, string>>({});
  const [isLoginLoading, setIsLoginLoading] = useState<boolean>(false);

  // State - Form (Register)
  const [registerData, setRegisterData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showRegisterPassword, setShowRegisterPassword] = useState<boolean>(false);
  const [showRegisterConfirmPassword, setShowRegisterConfirmPassword] = useState<boolean>(false);
  const [registerErrors, setRegisterErrors] = useState<Record<string, string>>({});
  const [isRegisterLoading, setIsRegisterLoading] = useState<boolean>(false);
  const [acceptedTerms, setAcceptedTerms] = useState<boolean>(false);
  const [acceptedPrivacy, setAcceptedPrivacy] = useState<boolean>(false);

  // State - Social
  const [isSocialLoading, setIsSocialLoading] = useState<string | null>(null);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>(mode);
  const [error, setError] = useState<string>('');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isRedirecting, setIsRedirecting] = useState<boolean>(false);

  // Refs
  const loginEmailRef = useRef<HTMLInputElement>(null);
  const loginPasswordRef = useRef<HTMLInputElement>(null);
  const registerNameRef = useRef<HTMLInputElement>(null);
  const registerEmailRef = useRef<HTMLInputElement>(null);
  const registerPasswordRef = useRef<HTMLInputElement>(null);

  // ============================================
  // Effects
  // ============================================

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated || status === 'authenticated') {
      setIsRedirecting(true);
      // Check user role for appropriate redirect
      if (user?.roles?.includes('admin')) {
        router.push('/admin/dashboard');
      } else if (user?.roles?.includes('support')) {
        router.push('/support/dashboard');
      } else {
        router.push(callbackUrl);
      }
    }
  }, [isAuthenticated, status, router, callbackUrl, user]);

  // Sync active tab with URL mode
  useEffect(() => {
    setActiveTab(mode);
  }, [mode]);

  // Focus first input on tab change
  useEffect(() => {
    if (activeTab === 'login' && loginEmailRef.current) {
      loginEmailRef.current.focus();
    } else if (activeTab === 'register' && registerNameRef.current) {
      registerNameRef.current.focus();
    }
  }, [activeTab]);

  // ============================================
  // Handlers - Login
  // ============================================

  const handleLoginEmailChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLoginEmail(e.target.value);
    setLoginErrors(prev => ({ ...prev, email: '' }));
  }, []);

  const handleLoginPasswordChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLoginPassword(e.target.value);
    setLoginErrors(prev => ({ ...prev, password: '' }));
  }, []);

  const handleToggleLoginPassword = useCallback(() => {
    setShowLoginPassword(prev => !prev);
  }, []);

  const validateLoginForm = useCallback((): boolean => {
    const errors: Record<string, string> = {};
    let isValid = true;

    if (!loginEmail) {
      errors.email = 'Email address is required';
      isValid = false;
    } else if (!validateEmail(loginEmail)) {
      errors.email = 'Please enter a valid email address';
      isValid = false;
    }

    if (!loginPassword) {
      errors.password = 'Password is required';
      isValid = false;
    }

    setLoginErrors(errors);
    return isValid;
  }, [loginEmail, loginPassword]);

  const handleLoginSubmit = useCallback(async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }

    if (isLoginLoading) return;

    if (!validateLoginForm()) {
      if (loginErrors.email && loginEmailRef.current) {
        loginEmailRef.current.focus();
      } else if (loginErrors.password && loginPasswordRef.current) {
        loginPasswordRef.current.focus();
      }
      return;
    }

    setIsLoginLoading(true);
    setError('');

    try {
      const result = await signIn('credentials', {
        email: loginEmail,
        password: loginPassword,
        rememberMe,
        redirect: false,
        callbackUrl,
      });

      if (result?.error) {
        if (result.error.includes('rate') || result.error.includes('too many')) {
          setError('Too many login attempts. Please try again later.');
        } else if (result.error.includes('locked')) {
          setError('Your account has been locked. Please contact support.');
        } else {
          setError('Invalid email or password');
        }
        setLoginPassword('');
        if (loginPasswordRef.current) {
          loginPasswordRef.current.focus();
        }
      } else if (result?.url) {
        setShowToast({
          message: 'Welcome back!',
          type: 'success',
        });
        router.push(callbackUrl);
      }
    } catch (error: any) {
      console.error('Login error:', error);
      setError(error.message || 'An error occurred during login');
    } finally {
      setIsLoginLoading(false);
    }
  }, [loginEmail, loginPassword, rememberMe, callbackUrl, validateLoginForm, isLoginLoading, loginErrors, router]);

  // ============================================
  // Handlers - Register
  // ============================================

  const handleRegisterChange = useCallback((field: string, value: string) => {
    setRegisterData(prev => ({ ...prev, [field]: value }));
    setRegisterErrors(prev => ({ ...prev, [field]: '' }));
  }, []);

  const handleToggleRegisterPassword = useCallback(() => {
    setShowRegisterPassword(prev => !prev);
  }, []);

  const handleToggleRegisterConfirmPassword = useCallback(() => {
    setShowRegisterConfirmPassword(prev => !prev);
  }, []);

  const validateRegisterForm = useCallback((): boolean => {
    const errors: Record<string, string> = {};
    let isValid = true;

    if (!registerData.name) {
      errors.name = 'Full name is required';
      isValid = false;
    } else if (registerData.name.length < 2) {
      errors.name = 'Name must be at least 2 characters';
      isValid = false;
    }

    if (!registerData.email) {
      errors.email = 'Email address is required';
      isValid = false;
    } else if (!validateEmail(registerData.email)) {
      errors.email = 'Please enter a valid email address';
      isValid = false;
    }

    if (!registerData.password) {
      errors.password = 'Password is required';
      isValid = false;
    } else if (registerData.password.length < PASSWORD_POLICY.MIN_LENGTH) {
      errors.password = `Password must be at least ${PASSWORD_POLICY.MIN_LENGTH} characters`;
      isValid = false;
    }

    if (!registerData.confirmPassword) {
      errors.confirmPassword = 'Please confirm your password';
      isValid = false;
    } else if (registerData.confirmPassword !== registerData.password) {
      errors.confirmPassword = 'Passwords do not match';
      isValid = false;
    }

    if (!acceptedTerms) {
      errors.terms = 'You must accept the Terms and Conditions';
      isValid = false;
    }

    if (!acceptedPrivacy) {
      errors.privacy = 'You must accept the Privacy Policy';
      isValid = false;
    }

    setRegisterErrors(errors);
    return isValid;
  }, [registerData, acceptedTerms, acceptedPrivacy]);

  const handleRegisterSubmit = useCallback(async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }

    if (isRegisterLoading) return;

    if (!validateRegisterForm()) {
      if (registerErrors.name && registerNameRef.current) {
        registerNameRef.current.focus();
      } else if (registerErrors.email && registerEmailRef.current) {
        registerEmailRef.current.focus();
      } else if (registerErrors.password && registerPasswordRef.current) {
        registerPasswordRef.current.focus();
      }
      return;
    }

    setIsRegisterLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/register', {
        name: registerData.name,
        email: registerData.email,
        password: registerData.password,
        acceptedTerms,
        acceptedPrivacy,
        metadata: {
          userAgent: navigator.userAgent,
          screenResolution: `${window.screen.width}x${window.screen.height}`,
          language: navigator.language,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        },
      });

      if (response.data.success) {
        setShowToast({
          message: 'Registration successful! Please check your email to verify your account.',
          type: 'success',
        });

        // Clear form
        setRegisterData({
          name: '',
          email: '',
          password: '',
          confirmPassword: '',
        });

        // Auto-login if enabled
        if (response.data.autoLogin) {
          const signInResult = await signIn('credentials', {
            email: registerData.email,
            password: registerData.password,
            redirect: false,
          });

          if (signInResult?.url) {
            router.push('/dashboard');
            return;
          }
        }

        // Switch to login tab after delay
        setTimeout(() => {
          setActiveTab('login');
          setLoginEmail(registerData.email);
        }, 2000);
      }
    } catch (error: any) {
      console.error('Registration error:', error);
      
      if (error.response?.status === 409) {
        setRegisterErrors(prev => ({
          ...prev,
          email: 'This email is already registered. Please login instead.',
        }));
      } else if (error.response?.status === 429) {
        setError('Too many registration attempts. Please try again later.');
      } else {
        setError(error.response?.data?.message || 'Registration failed. Please try again.');
      }
    } finally {
      setIsRegisterLoading(false);
    }
  }, [
    registerData,
    acceptedTerms,
    acceptedPrivacy,
    isRegisterLoading,
    validateRegisterForm,
    registerErrors,
    api,
    router,
  ]);

  // ============================================
  // Handlers - Social
  // ============================================

  const handleSocialAuth = useCallback(async (provider: string, action: 'login' | 'register' = 'login') => {
    try {
      setIsSocialLoading(provider);

      const result = await signIn(provider, {
        callbackUrl,
        redirect: false,
        ...(provider === 'web3' && {
          web3Address: account,
          action,
        }),
      });

      if (result?.error) {
        if (action === 'register' && result.error.includes('AccountExists')) {
          setError('An account with this email already exists. Please login instead.');
          setActiveTab('login');
        } else {
          setError(`Failed to ${action} with ${provider}. Please try again.`);
        }
        setIsSocialLoading(null);
        return;
      }

      if (result?.url) {
        setShowToast({
          message: `Successfully ${action === 'login' ? 'signed in' : 'registered'} with ${provider}!`,
          type: 'success',
        });
        router.push(callbackUrl);
      }
    } catch (error: any) {
      console.error(`Social auth error (${provider}):`, error);
      setError(error.message || `Failed to ${action} with ${provider}`);
      setIsSocialLoading(null);
    }
  }, [callbackUrl, router, account]);

  const handleWeb3Auth = useCallback(async (action: 'login' | 'register' = 'login') => {
    try {
      if (!isWeb3Connected) {
        await connectWeb3();
        return;
      }
      await handleSocialAuth('web3', action);
    } catch (error: any) {
      console.error('Web3 auth error:', error);
      setError(error.message || 'Web3 authentication failed');
    }
  }, [isWeb3Connected, connectWeb3, handleSocialAuth]);

  // ============================================
  // Render
  // ============================================

  // If redirecting, show loading
  if (isRedirecting || isAuthenticated || status === 'authenticated') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
          >
            <Spinner size="lg" className="mx-auto mb-4 text-cyan-500" />
            <p className="text-gray-400">Redirecting to dashboard...</p>
          </motion.div>
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
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-r from-cyan-500/10 to-purple-500/10 rounded-full blur-2xl" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-transparent via-transparent to-gray-900/50" />
      </div>

      {/* Floating Particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 bg-cyan-500/20 rounded-full"
            initial={{
              x: Math.random() * window.innerWidth,
              y: Math.random() * window.innerHeight,
              opacity: 0,
            }}
            animate={{
              y: [null, Math.random() * -100],
              opacity: [0, 0.5, 0],
            }}
            transition={{
              duration: Math.random() * 10 + 10,
              repeat: Infinity,
              delay: Math.random() * 10,
            }}
          />
        ))}
      </div>

      {/* Main Card */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="relative w-full max-w-4xl"
      >
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-0">
          {/* Left Panel - Branding */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="lg:col-span-2 bg-gradient-to-br from-cyan-600 to-blue-700 rounded-t-2xl lg:rounded-l-2xl lg:rounded-r-none p-8 lg:p-10 flex flex-col justify-between min-h-[300px] lg:min-h-[600px]"
          >
            <div>
              <div className="flex items-center gap-3 mb-8">
                <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                  <span className="text-xl font-bold text-white">N</span>
                </div>
                <span className="text-white font-semibold text-lg">NEXUS</span>
              </div>

              <div className="space-y-6">
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold text-white">
                    Welcome to NEXUS Trading
                  </h2>
                  <p className="text-cyan-100 text-sm leading-relaxed">
                    Your AI-powered trading platform for the future of finance
                  </p>
                </div>

                {/* Feature List */}
                <div className="space-y-3">
                  <div className="flex items-center gap-3 text-sm text-white/90">
                    <div className="w-6 h-6 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Brain className="w-3.5 h-3.5" />
                    </div>
                    <span>AI-powered market predictions</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-white/90">
                    <div className="w-6 h-6 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Zap className="w-3.5 h-3.5" />
                    </div>
                    <span>Real-time automated trading</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-white/90">
                    <div className="w-6 h-6 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                      <ShieldCheck className="w-3.5 h-3.5" />
                    </div>
                    <span>Advanced risk management</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-white/90">
                    <div className="w-6 h-6 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Globe className="w-3.5 h-3.5" />
                    </div>
                    <span>Multi-market & multi-asset support</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Trust Badges */}
            <div className="mt-8 pt-6 border-t border-white/10">
              <div className="flex items-center gap-4 text-xs text-white/70">
                <span className="flex items-center gap-1">
                  <Shield className="w-3 h-3" />
                  Secure
                </span>
                <span className="flex items-center gap-1">
                  <Users className="w-3 h-3" />
                  10K+ Users
                </span>
                <span className="flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  95% Accuracy
                </span>
              </div>
            </div>
          </motion.div>

          {/* Right Panel - Auth Forms */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="lg:col-span-3 bg-gray-800/90 backdrop-blur-xl rounded-b-2xl lg:rounded-r-2xl lg:rounded-l-none border border-gray-700 p-6 lg:p-8"
          >
            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid grid-cols-2 bg-gray-700/50 rounded-lg p-1 mb-6">
                <TabsTrigger
                  value="login"
                  className="data-[state=active]:bg-cyan-500 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
                >
                  Sign In
                </TabsTrigger>
                <TabsTrigger
                  value="register"
                  className="data-[state=active]:bg-cyan-500 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
                >
                  Create Account
                </TabsTrigger>
              </TabsList>

              {/* Error Display */}
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3"
                >
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-500">{error}</p>
                </motion.div>
              )}

              {/* ========================================== */}
              {/* LOGIN TAB */}
              {/* ========================================== */}
              <TabsContent value="login" className="space-y-4">
                <form onSubmit={handleLoginSubmit} className="space-y-4" noValidate>
                  {/* Email */}
                  <div>
                    <label htmlFor="login-email" className="block text-sm font-medium text-gray-300 mb-2">
                      Email Address
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Mail className="h-5 w-5 text-gray-500" />
                      </div>
                      <Input
                        ref={loginEmailRef}
                        id="login-email"
                        type="email"
                        value={loginEmail}
                        onChange={handleLoginEmailChange}
                        placeholder="you@example.com"
                        autoComplete="email"
                        disabled={isLoginLoading}
                        className={cn(
                          "w-full pl-10 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                          loginErrors.email && "border-red-500 focus:border-red-500 focus:ring-red-500"
                        )}
                      />
                    </div>
                    {loginErrors.email && (
                      <p className="mt-2 text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {loginErrors.email}
                      </p>
                    )}
                  </div>

                  {/* Password */}
                  <div>
                    <label htmlFor="login-password" className="block text-sm font-medium text-gray-300 mb-2">
                      Password
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Lock className="h-5 w-5 text-gray-500" />
                      </div>
                      <Input
                        ref={loginPasswordRef}
                        id="login-password"
                        type={showLoginPassword ? 'text' : 'password'}
                        value={loginPassword}
                        onChange={handleLoginPasswordChange}
                        placeholder="Enter your password"
                        autoComplete="current-password"
                        disabled={isLoginLoading}
                        className={cn(
                          "w-full pl-10 pr-12 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                          loginErrors.password && "border-red-500 focus:border-red-500 focus:ring-red-500"
                        )}
                      />
                      <button
                        type="button"
                        onClick={handleToggleLoginPassword}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-300 transition-colors"
                      >
                        {showLoginPassword ? (
                          <EyeOff className="h-5 w-5" />
                        ) : (
                          <Eye className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    {loginErrors.password && (
                      <p className="mt-2 text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {loginErrors.password}
                      </p>
                    )}
                  </div>

                  {/* Remember Me & Forgot Password */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="remember-me"
                        checked={rememberMe}
                        onCheckedChange={(checked) => setRememberMe(checked as boolean)}
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

                  {/* Login Button */}
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={isLoginLoading}
                    isLoading={isLoginLoading}
                    className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 transition-all duration-200"
                  >
                    {isLoginLoading ? (
                      'Signing in...'
                    ) : (
                      <>
                        Sign In
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    )}
                  </Button>
                </form>

                {/* Social Login */}
                <div className="relative my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-700" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="px-2 bg-gray-800 text-gray-500">Or continue with</span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Button
                    variant="outline"
                    onClick={() => handleSocialAuth('google', 'login')}
                    disabled={isLoginLoading || !!isSocialLoading}
                    className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    {isSocialLoading === 'google' ? (
                      <Spinner size="sm" />
                    ) : (
                      <Chrome className="w-5 h-5" />
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleSocialAuth('github', 'login')}
                    disabled={isLoginLoading || !!isSocialLoading}
                    className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    {isSocialLoading === 'github' ? (
                      <Spinner size="sm" />
                    ) : (
                      <Github className="w-5 h-5" />
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleWeb3Auth('login')}
                    disabled={isLoginLoading || isWeb3Connecting}
                    className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    {isWeb3Connecting ? (
                      <Spinner size="sm" />
                    ) : (
                      <Wallet className="w-5 h-5" />
                    )}
                  </Button>
                </div>
              </TabsContent>

              {/* ========================================== */}
              {/* REGISTER TAB */}
              {/* ========================================== */}
              <TabsContent value="register" className="space-y-4">
                <form onSubmit={handleRegisterSubmit} className="space-y-4" noValidate>
                  {/* Name */}
                  <div>
                    <label htmlFor="register-name" className="block text-sm font-medium text-gray-300 mb-2">
                      Full Name
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <User className="h-5 w-5 text-gray-500" />
                      </div>
                      <Input
                        ref={registerNameRef}
                        id="register-name"
                        type="text"
                        value={registerData.name}
                        onChange={(e) => handleRegisterChange('name', e.target.value)}
                        placeholder="John Doe"
                        autoComplete="name"
                        disabled={isRegisterLoading}
                        className={cn(
                          "w-full pl-10 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                          registerErrors.name && "border-red-500 focus:border-red-500 focus:ring-red-500"
                        )}
                      />
                    </div>
                    {registerErrors.name && (
                      <p className="mt-2 text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {registerErrors.name}
                      </p>
                    )}
                  </div>

                  {/* Email */}
                  <div>
                    <label htmlFor="register-email" className="block text-sm font-medium text-gray-300 mb-2">
                      Email Address
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Mail className="h-5 w-5 text-gray-500" />
                      </div>
                      <Input
                        ref={registerEmailRef}
                        id="register-email"
                        type="email"
                        value={registerData.email}
                        onChange={(e) => handleRegisterChange('email', e.target.value)}
                        placeholder="you@example.com"
                        autoComplete="email"
                        disabled={isRegisterLoading}
                        className={cn(
                          "w-full pl-10 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                          registerErrors.email && "border-red-500 focus:border-red-500 focus:ring-red-500"
                        )}
                      />
                    </div>
                    {registerErrors.email && (
                      <p className="mt-2 text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {registerErrors.email}
                      </p>
                    )}
                  </div>

                  {/* Password */}
                  <div>
                    <label htmlFor="register-password" className="block text-sm font-medium text-gray-300 mb-2">
                      Password
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Lock className="h-5 w-5 text-gray-500" />
                      </div>
                      <Input
                        ref={registerPasswordRef}
                        id="register-password"
                        type={showRegisterPassword ? 'text' : 'password'}
                        value={registerData.password}
                        onChange={(e) => handleRegisterChange('password', e.target.value)}
                        placeholder="Create a strong password"
                        autoComplete="new-password"
                        disabled={isRegisterLoading}
                        className={cn(
                          "w-full pl-10 pr-12 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                          registerErrors.password && "border-red-500 focus:border-red-500 focus:ring-red-500"
                        )}
                      />
                      <button
                        type="button"
                        onClick={handleToggleRegisterPassword}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-300 transition-colors"
                      >
                        {showRegisterPassword ? (
                          <EyeOff className="h-5 w-5" />
                        ) : (
                          <Eye className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    {registerErrors.password && (
                      <p className="mt-2 text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {registerErrors.password}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-gray-500">
                      Must be at least {PASSWORD_POLICY.MIN_LENGTH} characters
                    </p>
                  </div>

                  {/* Confirm Password */}
                  <div>
                    <label htmlFor="register-confirm-password" className="block text-sm font-medium text-gray-300 mb-2">
                      Confirm Password
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Key className="h-5 w-5 text-gray-500" />
                      </div>
                      <Input
                        id="register-confirm-password"
                        type={showRegisterConfirmPassword ? 'text' : 'password'}
                        value={registerData.confirmPassword}
                        onChange={(e) => handleRegisterChange('confirmPassword', e.target.value)}
                        placeholder="Confirm your password"
                        autoComplete="new-password"
                        disabled={isRegisterLoading}
                        className={cn(
                          "w-full pl-10 pr-12 bg-gray-700 border-gray-600 text-white placeholder-gray-400",
                          registerErrors.confirmPassword && "border-red-500 focus:border-red-500 focus:ring-red-500"
                        )}
                      />
                      <button
                        type="button"
                        onClick={handleToggleRegisterConfirmPassword}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-300 transition-colors"
                      >
                        {showRegisterConfirmPassword ? (
                          <EyeOff className="h-5 w-5" />
                        ) : (
                          <Eye className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    {registerErrors.confirmPassword && (
                      <p className="mt-2 text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {registerErrors.confirmPassword}
                      </p>
                    )}
                  </div>

                  {/* Terms */}
                  <div className="space-y-2">
                    <div className="flex items-start gap-2">
                      <Checkbox
                        id="register-terms"
                        checked={acceptedTerms}
                        onCheckedChange={(checked) => setAcceptedTerms(checked as boolean)}
                        className="mt-1 border-gray-600 data-[state=checked]:bg-cyan-500"
                      />
                      <label htmlFor="register-terms" className="text-sm text-gray-400 cursor-pointer">
                        I accept the{' '}
                        <Link href="/terms" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                          Terms and Conditions
                        </Link>
                      </label>
                    </div>
                    <div className="flex items-start gap-2">
                      <Checkbox
                        id="register-privacy"
                        checked={acceptedPrivacy}
                        onCheckedChange={(checked) => setAcceptedPrivacy(checked as boolean)}
                        className="mt-1 border-gray-600 data-[state=checked]:bg-cyan-500"
                      />
                      <label htmlFor="register-privacy" className="text-sm text-gray-400 cursor-pointer">
                        I accept the{' '}
                        <Link href="/privacy" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                          Privacy Policy
                        </Link>
                      </label>
                    </div>
                    {(registerErrors.terms || registerErrors.privacy) && (
                      <p className="text-sm text-red-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {registerErrors.terms || registerErrors.privacy}
                      </p>
                    )}
                  </div>

                  {/* Register Button */}
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={isRegisterLoading}
                    isLoading={isRegisterLoading}
                    className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 transition-all duration-200"
                  >
                    {isRegisterLoading ? (
                      'Creating Account...'
                    ) : (
                      <>
                        Create Account
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    )}
                  </Button>
                </form>

                {/* Social Register */}
                <div className="relative my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-700" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="px-2 bg-gray-800 text-gray-500">Or register with</span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Button
                    variant="outline"
                    onClick={() => handleSocialAuth('google', 'register')}
                    disabled={isRegisterLoading || !!isSocialLoading}
                    className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    {isSocialLoading === 'google' ? (
                      <Spinner size="sm" />
                    ) : (
                      <Chrome className="w-5 h-5" />
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleSocialAuth('github', 'register')}
                    disabled={isRegisterLoading || !!isSocialLoading}
                    className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    {isSocialLoading === 'github' ? (
                      <Spinner size="sm" />
                    ) : (
                      <Github className="w-5 h-5" />
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleWeb3Auth('register')}
                    disabled={isRegisterLoading || isWeb3Connecting}
                    className="border-gray-600 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    {isWeb3Connecting ? (
                      <Spinner size="sm" />
                    ) : (
                      <Wallet className="w-5 h-5" />
                    )}
                  </Button>
                </div>
              </TabsContent>
            </Tabs>

            {/* Security Notice */}
            <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <Shield className="w-3 h-3" />
                Secure & Encrypted
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                24/7 Support
              </span>
              <Link href="/privacy" className="hover:text-gray-400 transition-colors">
                Privacy
              </Link>
              <Link href="/terms" className="hover:text-gray-400 transition-colors">
                Terms
              </Link>
            </div>
          </motion.div>
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

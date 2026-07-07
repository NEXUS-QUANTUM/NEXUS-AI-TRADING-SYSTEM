/**
 * NEXUS AI TRADING SYSTEM - Onboarding Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page handles user onboarding including:
 * - Welcome and introduction
 * - Account setup and preferences
 * - Trading profile configuration
 * - Risk tolerance assessment
 * - Market preferences selection
 * - Email verification
 * - Security setup (2FA)
 * - API key generation
 * - First deposit guidance
 * - Tutorial and guided tour
 * - Feature discovery
 * - Personalization
 * - Progress tracking
 * - Multi-step onboarding flow
 * - Responsive design for all devices
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Badge } from '@/components/ui/Badge';
import { Progress } from '@/components/ui/Progress';
import { Textarea } from '@/components/ui/Textarea';
import { Checkbox } from '@/components/ui/Checkbox';
import { Slider } from '@/components/ui/Slider';
import { Avatar } from '@/components/ui/Avatar';

// Icons
import {
  Rocket,
  Sparkles,
  Shield,
  Wallet,
  TrendingUp,
  Brain,
  Zap,
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  User,
  Mail,
  Phone,
  Globe,
  Lock,
  Key,
  Eye,
  EyeOff,
  AlertCircle,
  Info,
  HelpCircle,
  Star,
  Award,
  Crown,
  Users,
  BarChart3,
  PieChart,
  LineChart,
  Activity,
  Clock,
  Calendar,
  DollarSign,
  Briefcase,
  Building,
  MapPin,
  Gift,
  Rocket as LaunchIcon,
  Target,
  Compass,
  Flag,
  Medal,
  Trophy,
  BookOpen,
  GraduationCap,
  Lightbulb,
  ThumbsUp,
  ThumbsDown,
  Heart,
  Smile,
  Frown,
  Meh,
  Zap as Bolt,
  ShieldCheck,
  Fingerprint,
  Scan,
  QrCode,
  Smartphone,
  Tablet,
  Laptop,
  Monitor,
  Server,
  Cloud,
  Database,
  Network,
  Cpu,
  Memory,
  HardDrive,
} from 'lucide-react';

// Types
import type {
  OnboardingStep,
  OnboardingData,
  UserPreferences,
  TradingProfile,
  RiskProfile,
  MarketPreferences,
  SecuritySettings,
  OnboardingProgress,
} from '@/types/onboarding';

// Constants
import {
  ONBOARDING_STEPS,
  RISK_LEVELS,
  EXPERIENCE_LEVELS,
  TRADING_GOALS,
  MARKET_CATEGORIES,
  TIMEZONES,
  CURRENCIES,
} from '@/constants/onboarding';

// Utils
import { cn } from '@/utils/helpers';

export default function OnboardingPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // State - Current Step
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [progress, setProgress] = useState<number>(0);

  // State - User Data
  const [onboardingData, setOnboardingData] = useState<OnboardingData>({
    preferences: {
      theme: 'dark',
      language: 'en',
      timezone: 'UTC',
      currency: 'USD',
      notifications: {
        email: true,
        push: true,
        inApp: true,
        priceAlerts: true,
        tradeAlerts: true,
        newsAlerts: false,
      },
      chartPreferences: {
        timeframe: '1h',
        indicators: ['rsi', 'macd', 'moving_average'],
        chartType: 'candlestick',
      },
    },
    tradingProfile: {
      experienceLevel: 'intermediate',
      riskLevel: 'medium',
      tradingGoals: ['growth'],
      preferredMarkets: ['crypto'],
      instruments: ['spot'],
      tradingFrequency: 'weekly',
      capitalRange: '5000-25000',
      strategyTypes: ['trend_following', 'momentum'],
      timeCommitment: 'part-time',
    },
    securitySettings: {
      twoFactorEnabled: false,
      emailVerified: false,
      phoneVerified: false,
      backupCodes: [],
      devices: [],
      activeSessions: [],
    },
    completed: false,
  });

  // State - UI
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [selectedStep, setSelectedStep] = useState<number>(0);
  const [tourActive, setTourActive] = useState<boolean>(true);
  const [showWelcome, setShowWelcome] = useState<boolean>(true);

  // Refs
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/onboarding');
    } else {
      loadOnboardingData();
    }
  }, [isAuthenticated, router]);

  // ============================================
  // API Calls
  // ============================================

  const loadOnboardingData = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/onboarding/status');
      if (response.data) {
        if (response.data.completed) {
          router.push('/dashboard');
          return;
        }
        setOnboardingData(response.data);
        setProgress(response.data.progress || 0);
        setCompletedSteps(response.data.completedSteps || []);
        setCurrentStep(response.data.currentStep || 0);
      }
    } catch (error) {
      console.error('Failed to load onboarding data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [api, router]);

  const saveOnboardingData = useCallback(async () => {
    setIsSubmitting(true);
    try {
      const response = await api.post('/onboarding/save', {
        ...onboardingData,
        currentStep,
        completedSteps,
        progress,
        completed: progress === 100,
      });
      if (response.data) {
        setOnboardingData(response.data);
        if (response.data.completed) {
          setShowToast({
            message: '🎉 Onboarding completed! Welcome to NEXUS Trading!',
            type: 'success',
          });
          setTimeout(() => {
            router.push('/dashboard');
          }, 2000);
        }
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to save progress.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, onboardingData, currentStep, completedSteps, progress, router]);

  // ============================================
  // Handlers - Navigation
  // ============================================

  const handleNextStep = useCallback(async () => {
    const nextStep = currentStep + 1;
    if (nextStep < ONBOARDING_STEPS.length) {
      setCurrentStep(nextStep);
      setCompletedSteps(prev => [...prev, currentStep]);
      setProgress(((nextStep) / ONBOARDING_STEPS.length) * 100);
      await saveOnboardingData();
      // Scroll to top
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      // Complete onboarding
      setProgress(100);
      await saveOnboardingData();
    }
  }, [currentStep, saveOnboardingData]);

  const handlePreviousStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
      setCompletedSteps(prev => prev.filter(s => s !== currentStep - 1));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [currentStep]);

  const handleSkipStep = useCallback(() => {
    // Mark step as completed but skip to next
    setCompletedSteps(prev => [...prev, currentStep]);
    setProgress(((currentStep + 1) / ONBOARDING_STEPS.length) * 100);
    setCurrentStep(currentStep + 1);
  }, [currentStep]);

  // ============================================
  // Handlers - Data Updates
  // ============================================

  const updatePreferences = useCallback((field: string, value: any) => {
    setOnboardingData(prev => ({
      ...prev,
      preferences: {
        ...prev.preferences,
        [field]: value,
      },
    }));
  }, []);

  const updateTradingProfile = useCallback((field: string, value: any) => {
    setOnboardingData(prev => ({
      ...prev,
      tradingProfile: {
        ...prev.tradingProfile,
        [field]: value,
      },
    }));
  }, []);

  const updateSecuritySettings = useCallback((field: string, value: any) => {
    setOnboardingData(prev => ({
      ...prev,
      securitySettings: {
        ...prev.securitySettings,
        [field]: value,
      },
    }));
  }, []);

  const handleToggleNotification = useCallback((type: string) => {
    setOnboardingData(prev => ({
      ...prev,
      preferences: {
        ...prev.preferences,
        notifications: {
          ...prev.preferences.notifications,
          [type]: !prev.preferences.notifications[type],
        },
      },
    }));
  }, []);

  const handleSelectIndicator = useCallback((indicator: string) => {
    setOnboardingData(prev => ({
      ...prev,
      preferences: {
        ...prev.preferences,
        chartPreferences: {
          ...prev.preferences.chartPreferences,
          indicators: prev.preferences.chartPreferences.indicators.includes(indicator)
            ? prev.preferences.chartPreferences.indicators.filter(i => i !== indicator)
            : [...prev.preferences.chartPreferences.indicators, indicator],
        },
      },
    }));
  }, []);

  // ============================================
  // Step Renderers
  // ============================================

  const renderStep = useMemo(() => {
    const step = ONBOARDING_STEPS[currentStep];
    if (!step) return null;

    switch (step.id) {
      case 'welcome':
        return renderWelcomeStep();
      case 'preferences':
        return renderPreferencesStep();
      case 'trading_profile':
        return renderTradingProfileStep();
      case 'risk_assessment':
        return renderRiskAssessmentStep();
      case 'market_preferences':
        return renderMarketPreferencesStep();
      case 'security':
        return renderSecurityStep();
      case 'complete':
        return renderCompleteStep();
      default:
        return null;
    }
  }, [currentStep, onboardingData]);

  // ============================================
  // Step Components
  // ============================================

  const renderWelcomeStep = () => (
    <div className="space-y-6">
      <div className="text-center">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 shadow-lg shadow-cyan-500/20 mb-6"
        >
          <Rocket className="w-12 h-12 text-white" />
        </motion.div>
        <h2 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
          Welcome to NEXUS Trading!
        </h2>
        <p className="text-gray-400 mt-3 max-w-md mx-auto">
          Let's get you set up for success. This quick onboarding will help you customize your experience.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
        {[
          { icon: Brain, title: 'AI-Powered', desc: 'Smart predictions and insights' },
          { icon: Shield, title: 'Secure Trading', desc: 'Enterprise-grade security' },
          { icon: TrendingUp, title: 'Real-time Data', desc: 'Live market analysis' },
        ].map((feature, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + index * 0.1 }}
            className="p-4 bg-gray-800/50 rounded-lg border border-gray-700 text-center"
          >
            <feature.icon className="w-8 h-8 text-cyan-500 mx-auto mb-2" />
            <h4 className="text-white font-medium">{feature.title}</h4>
            <p className="text-sm text-gray-400 mt-1">{feature.desc}</p>
          </motion.div>
        ))}
      </div>

      <div className="flex flex-col items-center gap-4 mt-6">
        <Button
          variant="primary"
          size="lg"
          onClick={handleNextStep}
          className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 px-8"
        >
          Get Started
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
        <p className="text-xs text-gray-500">
          This will take about 5 minutes • You can skip any step
        </p>
      </div>
    </div>
  );

  const renderPreferencesStep = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Customize Your Experience</h2>
        <p className="text-gray-400 mt-1">Set your preferences to tailor the platform to your needs.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Theme</label>
          <Select
            value={onboardingData.preferences.theme}
            onValueChange={(value) => updatePreferences('theme', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="system">System</option>
          </Select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Language</label>
          <Select
            value={onboardingData.preferences.language}
            onValueChange={(value) => updatePreferences('language', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            <option value="en">English</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
            <option value="de">Deutsch</option>
            <option value="zh">中文</option>
          </Select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Timezone</label>
          <Select
            value={onboardingData.preferences.timezone}
            onValueChange={(value) => updatePreferences('timezone', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            {TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Currency</label>
          <Select
            value={onboardingData.preferences.currency}
            onValueChange={(value) => updatePreferences('currency', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            {CURRENCIES.map((curr) => (
              <option key={curr} value={curr}>
                {curr}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-3">Notification Preferences</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { id: 'email', label: 'Email Notifications' },
            { id: 'push', label: 'Push Notifications' },
            { id: 'inApp', label: 'In-App Notifications' },
            { id: 'priceAlerts', label: 'Price Alerts' },
            { id: 'tradeAlerts', label: 'Trade Alerts' },
            { id: 'newsAlerts', label: 'News Alerts' },
          ].map((notification) => (
            <div key={notification.id} className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
              <span className="text-sm text-gray-300">{notification.label}</span>
              <Switch
                checked={onboardingData.preferences.notifications[notification.id as keyof typeof onboardingData.preferences.notifications]}
                onCheckedChange={() => handleToggleNotification(notification.id)}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-3">Chart Preferences</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Timeframe</label>
            <Select
              value={onboardingData.preferences.chartPreferences.timeframe}
              onValueChange={(value) => updatePreferences('chartPreferences', {
                ...onboardingData.preferences.chartPreferences,
                timeframe: value,
              })}
              className="w-full bg-gray-700 border-gray-600 text-sm"
            >
              <option value="1m">1 Minute</option>
              <option value="5m">5 Minutes</option>
              <option value="15m">15 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="4h">4 Hours</option>
              <option value="1d">1 Day</option>
              <option value="1w">1 Week</option>
            </Select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Chart Type</label>
            <Select
              value={onboardingData.preferences.chartPreferences.chartType}
              onValueChange={(value) => updatePreferences('chartPreferences', {
                ...onboardingData.preferences.chartPreferences,
                chartType: value,
              })}
              className="w-full bg-gray-700 border-gray-600 text-sm"
            >
              <option value="line">Line</option>
              <option value="candlestick">Candlestick</option>
              <option value="bar">Bar</option>
              <option value="area">Area</option>
            </Select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Indicators</label>
            <div className="flex flex-wrap gap-1 mt-1">
              {['rsi', 'macd', 'moving_average', 'bollinger', 'stochastic'].map((ind) => (
                <button
                  key={ind}
                  onClick={() => handleSelectIndicator(ind)}
                  className={cn(
                    "px-2 py-1 rounded text-xs transition-colors",
                    onboardingData.preferences.chartPreferences.indicators.includes(ind)
                      ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                      : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                  )}
                >
                  {ind.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTradingProfileStep = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Your Trading Profile</h2>
        <p className="text-gray-400 mt-1">Tell us about your trading experience and preferences.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Experience Level</label>
          <Select
            value={onboardingData.tradingProfile.experienceLevel}
            onValueChange={(value) => updateTradingProfile('experienceLevel', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            {EXPERIENCE_LEVELS.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label}
              </option>
            ))}
          </Select>
          <p className="text-xs text-gray-500 mt-1">
            {EXPERIENCE_LEVELS.find(l => l.value === onboardingData.tradingProfile.experienceLevel)?.description}
          </p>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Trading Goals</label>
          <Select
            value={onboardingData.tradingProfile.tradingGoals?.[0] || 'growth'}
            onValueChange={(value) => updateTradingProfile('tradingGoals', [value])}
            className="w-full bg-gray-700 border-gray-600"
          >
            {TRADING_GOALS.map((goal) => (
              <option key={goal.value} value={goal.value}>
                {goal.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Trading Frequency</label>
          <Select
            value={onboardingData.tradingProfile.tradingFrequency}
            onValueChange={(value) => updateTradingProfile('tradingFrequency', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="occasionally">Occasionally</option>
          </Select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Capital Range</label>
          <Select
            value={onboardingData.tradingProfile.capitalRange}
            onValueChange={(value) => updateTradingProfile('capitalRange', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            <option value="0-1000">$0 - $1,000</option>
            <option value="1000-5000">$1,000 - $5,000</option>
            <option value="5000-25000">$5,000 - $25,000</option>
            <option value="25000-100000">$25,000 - $100,000</option>
            <option value="100000+">$100,000+</option>
          </Select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Strategy Types</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {['trend_following', 'momentum', 'mean_reversion', 'arbitrage', 'scalping'].map((strategy) => (
              <button
                key={strategy}
                onClick={() => {
                  const current = onboardingData.tradingProfile.strategyTypes || [];
                  const updated = current.includes(strategy)
                    ? current.filter(s => s !== strategy)
                    : [...current, strategy];
                  updateTradingProfile('strategyTypes', updated);
                }}
                className={cn(
                  "px-3 py-1 rounded-lg text-xs transition-colors",
                  (onboardingData.tradingProfile.strategyTypes || []).includes(strategy)
                    ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                    : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                )}
              >
                {strategy.replace('_', ' ').toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Time Commitment</label>
          <Select
            value={onboardingData.tradingProfile.timeCommitment}
            onValueChange={(value) => updateTradingProfile('timeCommitment', value)}
            className="w-full bg-gray-700 border-gray-600"
          >
            <option value="full-time">Full-time</option>
            <option value="part-time">Part-time</option>
            <option value="casual">Casual</option>
            <option value="investor">Investor</option>
          </Select>
        </div>
      </div>
    </div>
  );

  const renderRiskAssessmentStep = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Risk Assessment</h2>
        <p className="text-gray-400 mt-1">Help us understand your risk tolerance to provide personalized recommendations.</p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">Risk Tolerance</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {RISK_LEVELS.map((level) => (
              <button
                key={level.value}
                onClick={() => updateTradingProfile('riskLevel', level.value)}
                className={cn(
                  "p-4 rounded-lg border-2 text-center transition-all",
                  onboardingData.tradingProfile.riskLevel === level.value
                    ? "border-cyan-500 bg-cyan-500/10"
                    : "border-gray-700 bg-gray-700/30 hover:border-gray-500"
                )}
              >
                <div className="text-2xl mb-2">{level.icon}</div>
                <h4 className="text-white font-medium">{level.label}</h4>
                <p className="text-xs text-gray-400 mt-1">{level.description}</p>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">Investment Horizon</label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {['short', 'medium', 'long', 'very_long'].map((horizon) => (
              <button
                key={horizon}
                onClick={() => updateTradingProfile('investmentHorizon', horizon)}
                className={cn(
                  "p-3 rounded-lg border text-center transition-all text-sm",
                  onboardingData.tradingProfile.investmentHorizon === horizon
                    ? "border-cyan-500 bg-cyan-500/10 text-white"
                    : "border-gray-700 bg-gray-700/30 text-gray-400 hover:border-gray-500"
                )}
              >
                {horizon.replace('_', ' ').toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">How much loss can you tolerate?</label>
          <div className="space-y-2">
            <input
              type="range"
              min="0"
              max="100"
              value={onboardingData.tradingProfile.maxLossTolerance || 20}
              onChange={(e) => updateTradingProfile('maxLossTolerance', parseInt(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
            <div className="text-center text-sm text-cyan-400">
              {onboardingData.tradingProfile.maxLossTolerance || 20}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderMarketPreferencesStep = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Market Preferences</h2>
        <p className="text-gray-400 mt-1">Select the markets and instruments you're interested in.</p>
      </div>

      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-gray-300 mb-3">Preferred Markets</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {MARKET_CATEGORIES.map((market) => (
              <button
                key={market.value}
                onClick={() => {
                  const current = onboardingData.tradingProfile.preferredMarkets || [];
                  const updated = current.includes(market.value)
                    ? current.filter(m => m !== market.value)
                    : [...current, market.value];
                  updateTradingProfile('preferredMarkets', updated);
                }}
                className={cn(
                  "p-3 rounded-lg border text-center transition-all",
                  (onboardingData.tradingProfile.preferredMarkets || []).includes(market.value)
                    ? "border-cyan-500 bg-cyan-500/10 text-white"
                    : "border-gray-700 bg-gray-700/30 text-gray-400 hover:border-gray-500"
                )}
              >
                <div className="text-2xl mb-1">{market.icon}</div>
                <div className="text-sm">{market.label}</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-medium text-gray-300 mb-3">Trading Instruments</h3>
          <div className="flex flex-wrap gap-2">
            {['spot', 'futures', 'options', 'margin', 'etf', 'forex'].map((instrument) => (
              <button
                key={instrument}
                onClick={() => {
                  const current = onboardingData.tradingProfile.instruments || [];
                  const updated = current.includes(instrument)
                    ? current.filter(i => i !== instrument)
                    : [...current, instrument];
                  updateTradingProfile('instruments', updated);
                }}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm transition-colors",
                  (onboardingData.tradingProfile.instruments || []).includes(instrument)
                    ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                    : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                )}
              >
                {instrument.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderSecurityStep = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Security Setup</h2>
        <p className="text-gray-400 mt-1">Protect your account with additional security features.</p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-700/30 rounded-lg border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-cyan-500" />
            </div>
            <div>
              <h4 className="text-white font-medium">Two-Factor Authentication</h4>
              <p className="text-sm text-gray-400">Add an extra layer of security to your account</p>
            </div>
          </div>
          <Switch
            checked={onboardingData.securitySettings.twoFactorEnabled}
            onCheckedChange={(checked) => updateSecuritySettings('twoFactorEnabled', checked)}
            className="data-[state=checked]:bg-cyan-500"
          />
        </div>

        <div className="flex items-center justify-between p-4 bg-gray-700/30 rounded-lg border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              <Mail className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <h4 className="text-white font-medium">Email Verification</h4>
              <p className="text-sm text-gray-400">
                {onboardingData.securitySettings.emailVerified 
                  ? '✓ Verified' 
                  : 'Verify your email address'}
              </p>
            </div>
          </div>
          {!onboardingData.securitySettings.emailVerified && (
            <Button
              variant="outline"
              size="sm"
              className="border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
            >
              Verify
            </Button>
          )}
        </div>

        <div className="flex items-center justify-between p-4 bg-gray-700/30 rounded-lg border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <Smartphone className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <h4 className="text-white font-medium">Phone Verification</h4>
              <p className="text-sm text-gray-400">
                {onboardingData.securitySettings.phoneVerified 
                  ? '✓ Verified' 
                  : 'Verify your phone number'}
              </p>
            </div>
          </div>
          {!onboardingData.securitySettings.phoneVerified && (
            <Button
              variant="outline"
              size="sm"
              className="border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
            >
              Verify
            </Button>
          )}
        </div>

        <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-yellow-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm text-yellow-500 font-medium">Security Tip</p>
              <p className="text-xs text-gray-400 mt-1">
                Enable 2FA and verify your email to fully secure your account and unlock all features.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderCompleteStep = () => (
    <div className="space-y-6 text-center">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 shadow-lg shadow-green-500/20 mx-auto"
      >
        <CheckCircle className="w-12 h-12 text-white" />
      </motion.div>

      <div>
        <h2 className="text-3xl font-bold bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">
          You're All Set!
        </h2>
        <p className="text-gray-400 mt-3 max-w-md mx-auto">
          Your onboarding is complete. You're now ready to start trading with NEXUS AI.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto">
        {[
          { icon: Wallet, title: 'Fund Your Account', desc: 'Deposit funds to start trading' },
          { icon: Brain, title: 'Explore AI Features', desc: 'Discover smart predictions' },
          { icon: Rocket, title: 'Start Trading', desc: 'Execute your first trade' },
        ].map((item, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + index * 0.1 }}
            className="p-4 bg-gray-800/50 rounded-lg border border-gray-700"
          >
            <item.icon className="w-8 h-8 text-cyan-500 mx-auto mb-2" />
            <h4 className="text-white font-medium">{item.title}</h4>
            <p className="text-sm text-gray-400 mt-1">{item.desc}</p>
          </motion.div>
        ))}
      </div>

      <div className="flex justify-center gap-4 mt-6">
        <Button
          variant="outline"
          onClick={() => router.push('/trading')}
          className="border-gray-600 hover:border-cyan-500"
        >
          Explore Platform
        </Button>
        <Button
          variant="primary"
          onClick={() => router.push('/dashboard')}
          className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
        >
          Go to Dashboard
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );

  // ============================================
  // Render
  // ============================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Setting up your account...</p>
          <p className="text-gray-500 text-sm mt-2">Please wait</p>
        </div>
      </div>
    );
  }

  const step = ONBOARDING_STEPS[currentStep];

  return (
    <div className="min-h-screen bg-gray-900 text-white py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Progress Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="text-2xl">🚀</div>
              <div>
                <h1 className="text-xl font-bold text-white">Onboarding</h1>
                <p className="text-sm text-gray-400">Step {currentStep + 1} of {ONBOARDING_STEPS.length}</p>
              </div>
            </div>
            <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30">
              {Math.round(progress)}% Complete
            </Badge>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Main Content */}
        <Card className="p-6 md:p-8 bg-gray-800 border-gray-700">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
            >
              {renderStep}
            </motion.div>
          </AnimatePresence>

          {/* Navigation */}
          {step?.id !== 'welcome' && step?.id !== 'complete' && (
            <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-700">
              <Button
                variant="outline"
                onClick={handlePreviousStep}
                className="border-gray-600 hover:border-cyan-500"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  onClick={handleSkipStep}
                  className="text-gray-400 hover:text-white"
                >
                  Skip
                </Button>
                <Button
                  variant="primary"
                  onClick={handleNextStep}
                  isLoading={isSubmitting}
                  className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                >
                  {currentStep === ONBOARDING_STEPS.length - 1 ? 'Complete' : 'Continue'}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </div>
          )}

          {/* Step Indicators */}
          {step?.id !== 'welcome' && step?.id !== 'complete' && (
            <div className="flex justify-center gap-2 mt-6">
              {ONBOARDING_STEPS.map((s, index) => (
                <button
                  key={s.id}
                  onClick={() => {
                    if (completedSteps.includes(index) || index <= currentStep) {
                      setCurrentStep(index);
                    }
                  }}
                  className={cn(
                    "w-2.5 h-2.5 rounded-full transition-all",
                    index === currentStep
                      ? "w-8 bg-cyan-500"
                      : completedSteps.includes(index)
                      ? "bg-cyan-500/50"
                      : "bg-gray-600"
                  )}
                />
              ))}
            </div>
          )}
        </Card>
      </div>

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

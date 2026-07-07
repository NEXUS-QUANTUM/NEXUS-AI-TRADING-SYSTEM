/**
 * NEXUS AI TRADING SYSTEM - Landing Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page serves as the main landing page for the application including:
 * - Hero section with value proposition
 * - Features showcase
 * - AI-powered trading highlights
 * - Market data overview
 * - Testimonials and social proof
 * - Pricing plans
 * - CTA sections
 * - Newsletter signup
 * - Blog/News section
 * - Partner/Integration logos
 * - FAQ section
 * - Footer with links
 * - Interactive animations
 * - Responsive design for all devices
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Toast } from '@/components/ui/Toast';

// Icons
import {
  TrendingUp,
  TrendingDown,
  Zap,
  Brain,
  Shield,
  Rocket,
  BarChart3,
  Wallet,
  Signal,
  Bot,
  Users,
  Award,
  Star,
  Check,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Play,
  Pause,
  RefreshCw,
  Download,
  Upload,
  Globe,
  Clock,
  Calendar,
  Mail,
  Phone,
  MapPin,
  Github,
  Twitter,
  Linkedin,
  Youtube,
  Instagram,
  MessageSquare,
  Bell,
  Settings,
  User,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Sun,
  Moon,
  Monitor,
  Layout,
  Columns,
  Rows,
  PanelTop,
  PanelBottom,
  PanelLeft,
  PanelRight,
  Square,
  Circle,
  Triangle,
  Hexagon,
  Octagon,
  Pentagon,
  Sparkles,
  Crown,
  Star as StarIcon,
  Award as AwardIcon,
  Trophy,
  Medal,
  Gift,
  Rocket as RocketIcon,
  Zap as ZapIcon,
  Shield as ShieldIcon,
  Brain as BrainIcon,
  TrendingUp as TrendingUpIcon,
  BarChart3 as BarChartIcon,
  Wallet as WalletIcon,
  Signal as SignalIcon,
  Bot as BotIcon,
  Users as UsersIcon,
  Check as CheckIcon,
  ArrowRight as ArrowRightIcon,
} from 'lucide-react';

// Utils
import { cn } from '@/utils/helpers';

// Constants
import { FEATURES, TESTIMONIALS, PRICING_PLANS, FAQS, PARTNERS, STATS } from '@/constants/landing';

export default function LandingPage() {
  // Router
  const router = useRouter();

  // Auth
  const { isAuthenticated } = useAuth();

  // State
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [email, setEmail] = useState<string>('');
  const [emailError, setEmailError] = useState<string>('');
  const [isSubscribed, setIsSubscribed] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [activeTestimonial, setActiveTestimonial] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Refs for scroll animations
  const heroRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const statsRef = useRef<HTMLDivElement>(null);
  const testimonialsRef = useRef<HTMLDivElement>(null);
  const pricingRef = useRef<HTMLDivElement>(null);
  const faqRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);

  // Scroll animations
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.3], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.3], [1, 0.95]);
  const y = useTransform(scrollYProgress, [0, 0.3], [0, 50]);

  // ============================================
  // Auto-play testimonials
  // ============================================

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveTestimonial(prev => (prev + 1) % TESTIMONIALS.length);
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // ============================================
  // Handlers
  // ============================================

  const handleSubscribe = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email) {
      setEmailError('Email is required');
      return;
    }

    if (!email.includes('@') || !email.includes('.')) {
      setEmailError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);
    setEmailError('');

    try {
      // In production, call API to subscribe
      await new Promise(resolve => setTimeout(resolve, 1000));
      setIsSubscribed(true);
      setEmail('');
      setShowToast({
        message: 'Successfully subscribed to newsletter!',
        type: 'success',
      });
    } catch (error) {
      setShowToast({
        message: 'Failed to subscribe. Please try again.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [email]);

  const handleScrollTo = useCallback((ref: React.RefObject<HTMLDivElement>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const handleGetStarted = useCallback(() => {
    if (isAuthenticated) {
      router.push('/dashboard');
    } else {
      router.push('/authentication/register');
    }
  }, [isAuthenticated, router]);

  const handleWatchDemo = useCallback(() => {
    setIsPlaying(true);
    // In production, open video modal or navigate to demo
    setTimeout(() => setIsPlaying(false), 3000);
  }, []);

  const toggleFaq = useCallback((index: number) => {
    setActiveFaq(prev => prev === index ? null : index);
  }, []);

  // ============================================
  // Render
  // ============================================

  return (
    <div className="min-h-screen bg-gray-900">
      {/* ============================================ */}
      {/* HERO SECTION */}
      {/* ============================================ */}
      <section
        ref={heroRef}
        className="relative overflow-hidden min-h-screen flex items-center justify-center pt-16"
      >
        {/* Background Gradients */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-1/2 -right-1/2 w-full h-full bg-gradient-to-br from-cyan-500/10 to-purple-500/10 rounded-full blur-3xl" />
          <div className="absolute -bottom-1/2 -left-1/2 w-full h-full bg-gradient-to-tr from-blue-500/10 to-cyan-500/10 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-r from-cyan-500/5 to-purple-500/5 rounded-full blur-2xl" />
          
          {/* Animated Grid */}
          <div className="absolute inset-0 bg-[url('/grid.svg')] bg-center opacity-10" />
          
          {/* Floating Particles */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {[...Array(30)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute w-1 h-1 bg-cyan-500/30 rounded-full"
                initial={{
                  x: Math.random() * window.innerWidth,
                  y: Math.random() * window.innerHeight,
                  opacity: 0,
                }}
                animate={{
                  y: [null, Math.random() * -200],
                  opacity: [0, 0.5, 0],
                }}
                transition={{
                  duration: Math.random() * 15 + 10,
                  repeat: Infinity,
                  delay: Math.random() * 10,
                }}
              />
            ))}
          </div>
        </div>

        {/* Hero Content */}
        <motion.div
          style={{ opacity, scale, y }}
          className="relative container mx-auto px-4 py-20 z-10"
        >
          <div className="max-w-5xl mx-auto text-center">
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-500/10 border border-cyan-500/20 rounded-full mb-6"
            >
              <Badge className="bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs">
                🚀 AI-Powered
              </Badge>
              <span className="text-sm text-gray-400">Next-generation trading platform</span>
            </motion.div>

            {/* Title */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-4xl md:text-6xl lg:text-7xl font-bold text-white leading-tight mb-6"
            >
              Trade Smarter with{' '}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                AI Intelligence
              </span>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="text-xl text-gray-400 max-w-3xl mx-auto mb-10"
            >
              NEXUS AI Trading System combines cutting-edge artificial intelligence with advanced algorithmic trading to help you make smarter, faster, and more profitable trades across multiple markets.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="flex flex-wrap items-center justify-center gap-4 mb-12"
            >
              <Button
                onClick={handleGetStarted}
                className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white px-8 py-6 text-lg"
              >
                Get Started Free
                <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
              <Button
                variant="outline"
                onClick={handleWatchDemo}
                className="border-gray-600 hover:border-cyan-500 text-white px-8 py-6 text-lg"
              >
                <Play className="mr-2 w-5 h-5" />
                Watch Demo
              </Button>
            </motion.div>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto"
            >
              {STATS.map((stat, index) => (
                <div key={index} className="text-center">
                  <div className="text-3xl font-bold text-white">{stat.value}</div>
                  <div className="text-sm text-gray-400">{stat.label}</div>
                </div>
              ))}
            </motion.div>
          </div>
        </motion.div>

        {/* Scroll Indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-gray-500"
        >
          <span className="text-sm">Scroll to explore</span>
          <motion.div
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <ChevronDown className="w-5 h-5" />
          </motion.div>
        </motion.div>
      </section>

      {/* ============================================ */}
      {/* FEATURES SECTION */}
      {/* ============================================ */}
      <section ref={featuresRef} className="py-20 bg-gray-800/50">
        <div className="container mx-auto px-4">
          {/* Section Header */}
          <div className="text-center max-w-3xl mx-auto mb-16">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
            >
              <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30 mb-4">
                Features
              </Badge>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                Everything You Need to Trade Like a Pro
              </h2>
              <p className="text-gray-400 text-lg">
                NEXUS combines advanced AI, real-time data, and sophisticated trading tools to give you the edge in today's markets.
              </p>
            </motion.div>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {FEATURES.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                viewport={{ once: true }}
              >
                <Card className="p-6 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all group h-full">
                  <div className="w-12 h-12 rounded-lg bg-cyan-500/20 flex items-center justify-center mb-4 group-hover:bg-cyan-500/30 transition-colors">
                    <feature.icon className="w-6 h-6 text-cyan-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">{feature.title}</h3>
                  <p className="text-gray-400">{feature.description}</p>
                  {feature.link && (
                    <Link
                      href={feature.link}
                      className="inline-flex items-center text-cyan-400 hover:text-cyan-300 mt-4 text-sm font-medium"
                    >
                      Learn More
                      <ArrowRight className="ml-1 w-4 h-4" />
                    </Link>
                  )}
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* STATS SECTION */}
      {/* ============================================ */}
      <section ref={statsRef} className="py-20 bg-gray-900">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {STATS.map((stat, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                viewport={{ once: true }}
                className="text-center"
              >
                <div className="text-4xl md:text-5xl font-bold text-cyan-400">{stat.value}</div>
                <div className="text-gray-400 mt-2">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* TESTIMONIALS SECTION */}
      {/* ============================================ */}
      <section ref={testimonialsRef} className="py-20 bg-gray-800/30">
        <div className="container mx-auto px-4">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
            >
              <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30 mb-4">
                Testimonials
              </Badge>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                What Our Users Say
              </h2>
              <p className="text-gray-400 text-lg">
                Join thousands of traders who have transformed their trading with NEXUS AI.
              </p>
            </motion.div>
          </div>

          <div className="relative max-w-4xl mx-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTestimonial}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.5 }}
                className="bg-gray-800 rounded-2xl p-8 border border-gray-700"
              >
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 flex items-center justify-center text-white font-bold text-xl">
                    {TESTIMONIALS[activeTestimonial].name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-semibold text-white">
                      {TESTIMONIALS[activeTestimonial].name}
                    </div>
                    <div className="text-sm text-gray-400">
                      {TESTIMONIALS[activeTestimonial].role}
                    </div>
                  </div>
                </div>
                <p className="text-gray-300 text-lg italic">
                  "{TESTIMONIALS[activeTestimonial].content}"
                </p>
                <div className="flex gap-1 mt-4">
                  {[...Array(5)].map((_, i) => (
                    <StarIcon
                      key={i}
                      className={cn(
                        "w-5 h-5",
                        i < TESTIMONIALS[activeTestimonial].rating
                          ? 'text-yellow-500 fill-yellow-500'
                          : 'text-gray-600'
                      )}
                    />
                  ))}
                </div>
              </motion.div>
            </AnimatePresence>

            {/* Dots */}
            <div className="flex justify-center gap-2 mt-6">
              {TESTIMONIALS.map((_, index) => (
                <button
                  key={index}
                  onClick={() => setActiveTestimonial(index)}
                  className={cn(
                    "w-2.5 h-2.5 rounded-full transition-colors",
                    index === activeTestimonial
                      ? 'bg-cyan-500'
                      : 'bg-gray-600 hover:bg-gray-500'
                  )}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* PRICING SECTION */}
      {/* ============================================ */}
      <section ref={pricingRef} className="py-20 bg-gray-900">
        <div className="container mx-auto px-4">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
            >
              <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30 mb-4">
                Pricing
              </Badge>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                Choose Your Plan
              </h2>
              <p className="text-gray-400 text-lg">
                Start free and upgrade as you grow. All plans include AI-powered trading features.
              </p>
            </motion.div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {PRICING_PLANS.map((plan, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                viewport={{ once: true }}
                className="relative"
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                    <Badge className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white text-xs px-4 py-1">
                      ⭐ Most Popular
                    </Badge>
                  </div>
                )}
                <Card className={cn(
                  "p-6 bg-gray-800 border-gray-700 h-full flex flex-col transition-all",
                  plan.popular && "border-yellow-500/30 ring-2 ring-yellow-500/20"
                )}>
                  <h3 className="text-xl font-bold text-white">{plan.name}</h3>
                  <div className="mt-2 mb-4">
                    <span className="text-4xl font-bold text-white">{plan.price}</span>
                    {plan.price !== 'Free' && (
                      <span className="text-gray-400 ml-1">/month</span>
                    )}
                  </div>
                  <p className="text-gray-400 text-sm mb-6">{plan.description}</p>

                  <ul className="space-y-3 flex-1 mb-6">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm">
                        <Check className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
                        <span className="text-gray-300">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    onClick={handleGetStarted}
                    className={cn(
                      "w-full",
                      plan.popular
                        ? "bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600"
                        : "border-gray-600 hover:border-cyan-500 text-white"
                    )}
                    variant={plan.popular ? 'primary' : 'outline'}
                  >
                    {plan.cta}
                    <ArrowRight className="ml-2 w-4 h-4" />
                  </Button>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* FAQ SECTION */}
      {/* ============================================ */}
      <section ref={faqRef} className="py-20 bg-gray-800/30">
        <div className="container mx-auto px-4">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
            >
              <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 mb-4">
                FAQ
              </Badge>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                Frequently Asked Questions
              </h2>
              <p className="text-gray-400 text-lg">
                Find answers to common questions about NEXUS AI Trading System.
              </p>
            </motion.div>
          </div>

          <div className="max-w-3xl mx-auto space-y-4">
            {FAQS.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                viewport={{ once: true }}
                className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden"
              >
                <button
                  onClick={() => toggleFaq(index)}
                  className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-700/50 transition-colors"
                >
                  <span className="text-white font-medium">{faq.question}</span>
                  <motion.div
                    animate={{ rotate: activeFaq === index ? 180 : 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  </motion.div>
                </button>
                <AnimatePresence>
                  {activeFaq === index && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="px-6 pb-4"
                    >
                      <p className="text-gray-400">{faq.answer}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* CTA SECTION */}
      {/* ============================================ */}
      <section ref={ctaRef} className="py-20 bg-gradient-to-br from-cyan-500/10 to-blue-500/10">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="max-w-4xl mx-auto text-center"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Ready to Start Trading Smarter?
            </h2>
            <p className="text-gray-400 text-lg mb-8">
              Join thousands of traders using NEXUS AI to make better trading decisions.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Button
                onClick={handleGetStarted}
                className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white px-8 py-6 text-lg"
              >
                Start Your Free Trial
                <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
              <Button
                variant="outline"
                className="border-gray-600 hover:border-cyan-500 text-white px-8 py-6 text-lg"
              >
                Contact Sales
              </Button>
            </div>

            {/* Newsletter */}
            <div className="mt-12 max-w-md mx-auto">
              <p className="text-sm text-gray-400 mb-3">
                Subscribe to get trading insights and updates
              </p>
              <form onSubmit={handleSubscribe} className="flex flex-col sm:flex-row gap-3">
                <Input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="flex-1 bg-gray-700 border-gray-600 text-white"
                  disabled={isLoading || isSubscribed}
                />
                <Button
                  type="submit"
                  isLoading={isLoading}
                  disabled={isSubscribed}
                  className="bg-gradient-to-r from-cyan-500 to-blue-500 whitespace-nowrap"
                >
                  {isSubscribed ? (
                    <>
                      <Check className="w-4 h-4 mr-2" />
                      Subscribed
                    </>
                  ) : (
                    'Subscribe'
                  )}
                </Button>
              </form>
              {emailError && (
                <p className="text-red-500 text-sm mt-2">{emailError}</p>
              )}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ============================================ */}
      {/* TOAST NOTIFICATIONS */}
      {/* ============================================ */}
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

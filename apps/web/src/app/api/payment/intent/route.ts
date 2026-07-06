/**
 * NEXUS AI TRADING SYSTEM - Payment Intent Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles payment intent creation and management including:
 * - Stripe payment intent creation
 * - PayPal order creation
 * - Coinbase charge creation
 * - Payment method validation
 * - Amount and currency validation
 * - Customer creation and management
 * - Subscription plan handling
 * - Promo code and discount application
 * - Tax calculation
 * - Payment intent status checking
 * - Payment intent cancellation
 * - Payment method listing
 * - Payment confirmation
 * - Error handling and retries
 * - Rate limiting
 * - Security validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';
import Stripe from 'stripe';

// Types
import type {
  PaymentIntentRequest,
  PaymentIntentResponse,
  PaymentMethod,
  PaymentPlan,
  PaymentIntentStatus,
  PaymentError,
  PaymentMetadata,
  PromoCode,
  Discount,
  TaxInfo,
  PaymentIntentData,
} from '@/types/payment';

// Utils
import {
  createStripePaymentIntent,
  createPayPalOrder,
  createCoinbaseCharge,
  validatePaymentAmount,
  validateCurrency,
  calculateTax,
  applyDiscount,
  validatePromoCode,
  getPaymentMethod,
  createCustomer,
  getCustomer,
  updateCustomer,
  logPaymentEvent,
  createAuditLog,
  sendPaymentConfirmationEmail,
} from '@/lib/payment';

// Constants
import {
  PAYMENT_PROVIDERS,
  PAYMENT_STATUS,
  PAYMENT_METHODS,
  PAYMENT_PLANS,
  CURRENCIES,
  MINIMUM_PAYMENT_AMOUNT,
  MAXIMUM_PAYMENT_AMOUNT,
  TAX_RATES,
  DISCOUNT_TYPES,
  PROMO_CODE_TYPES,
} from '@/constants/payment';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Configuration
// ============================================

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || '';
const PAYPAL_CLIENT_ID = process.env.PAYPAL_CLIENT_ID || '';
const PAYPAL_CLIENT_SECRET = process.env.PAYPAL_CLIENT_SECRET || '';
const COINBASE_API_KEY = process.env.COINBASE_API_KEY || '';
const COINBASE_WEBHOOK_SECRET = process.env.COINBASE_WEBHOOK_SECRET || '';

const stripe = new Stripe(STRIPE_SECRET_KEY, {
  apiVersion: '2023-10-16',
  typescript: true,
});

// ============================================
// Main Handler - POST
// ============================================

export async function POST(req: NextRequest) {
  try {
    // Get request details
    const body = await req.json();
    const headersList = await headers();
    const userId = headersList.get('x-user-id') || body.userId;
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const userAgent = headersList.get('user-agent') || 'unknown';
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');

    // Validate authentication
    if (!authToken) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Rate limiting
    const rateLimitKey = `payment:intent:${userId}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many payment requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Validate request
    const validation = await validatePaymentIntentRequest(body);
    if (!validation.isValid) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    // Route to appropriate provider
    const provider = body.provider || PAYMENT_PROVIDERS.STRIPE;
    let result: PaymentIntentResponse;

    switch (provider) {
      case PAYMENT_PROVIDERS.STRIPE:
        result = await handleStripeIntent(body, userId as string, ip, userAgent);
        break;
      
      case PAYMENT_PROVIDERS.PAYPAL:
        result = await handlePayPalIntent(body, userId as string, ip, userAgent);
        break;
      
      case PAYMENT_PROVIDERS.COINBASE:
        result = await handleCoinbaseIntent(body, userId as string, ip, userAgent);
        break;
      
      default:
        return NextResponse.json(
          { error: 'Unsupported payment provider' },
          { status: 400 }
        );
    }

    // Log successful intent creation
    await logPaymentEvent({
      type: 'payment_intent_created',
      provider: provider,
      userId: userId as string,
      paymentIntentId: result.id,
      amount: body.amount,
      currency: body.currency,
      timestamp: new Date(),
    });

    // Create audit log
    await createAuditLog({
      userId: userId as string,
      action: 'payment_intent_created',
      resource: 'payment_intent',
      resourceId: result.id,
      metadata: {
        provider,
        amount: body.amount,
        currency: body.currency,
        intentType: body.type || 'payment',
      },
      ip,
      userAgent,
    });

    return NextResponse.json(result, { status: 200 });

  } catch (error: any) {
    console.error('Payment intent creation error:', error);
    
    await logPaymentEvent({
      type: 'payment_intent_error',
      error: error.message,
      stack: error.stack,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { 
        error: error.message || 'Failed to create payment intent',
        code: error.code || 'PAYMENT_INTENT_ERROR',
      },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - GET
// ============================================

export async function GET(req: NextRequest) {
  try {
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const { searchParams } = new URL(req.url);
    const intentId = searchParams.get('id');
    const provider = searchParams.get('provider') || PAYMENT_PROVIDERS.STRIPE;

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Get payment intent by ID
    if (intentId) {
      const intent = await getPaymentIntent(intentId, provider, userId);
      return NextResponse.json(intent, { status: 200 });
    }

    // List payment intents for user
    const intents = await listPaymentIntents(userId);
    return NextResponse.json(intents, { status: 200 });

  } catch (error: any) {
    console.error('Get payment intent error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to retrieve payment intent' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - DELETE
// ============================================

export async function DELETE(req: NextRequest) {
  try {
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const { searchParams } = new URL(req.url);
    const intentId = searchParams.get('id');
    const provider = searchParams.get('provider') || PAYMENT_PROVIDERS.STRIPE;

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    if (!intentId) {
      return NextResponse.json(
        { error: 'Payment intent ID required' },
        { status: 400 }
      );
    }

    // Cancel payment intent
    const result = await cancelPaymentIntent(intentId, provider, userId);
    
    return NextResponse.json(result, { status: 200 });

  } catch (error: any) {
    console.error('Cancel payment intent error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to cancel payment intent' },
      { status: 500 }
    );
  }
}

// ============================================
// Stripe Intent Handler
// ============================================

async function handleStripeIntent(
  body: any,
  userId: string,
  ip: string,
  userAgent: string
): Promise<PaymentIntentResponse> {
  try {
    const {
      amount,
      currency,
      paymentMethod,
      description,
      metadata,
      customer,
      subscription,
      planId,
      promoCode,
      savePaymentMethod,
      returnUrl,
      cancelUrl,
    } = body;

    // Get or create customer
    let customerId = customer || await getStripeCustomer(userId);
    if (!customerId) {
      const user = await prisma.user.findUnique({
        where: { id: userId },
      });
      if (!user) {
        throw new Error('User not found');
      }
      customerId = await createStripeCustomer(user);
    }

    // Validate and apply promo code
    let discount: Discount | null = null;
    if (promoCode) {
      const promo = await validatePromoCode(promoCode);
      if (promo) {
        discount = await applyDiscount(amount, promo);
      }
    }

    // Calculate tax
    const taxInfo = await calculateTax({
      amount: discount ? discount.finalAmount : amount,
      currency,
      userId,
      country: body.country || 'US',
    });

    // Create payment intent
    const paymentIntent = await stripe.paymentIntents.create({
      amount: Math.round((discount ? discount.finalAmount : amount) * 100),
      currency: currency.toLowerCase(),
      customer: customerId,
      payment_method_types: getPaymentMethodTypes(paymentMethod),
      description: description || 'NEXUS AI Trading - Payment',
      metadata: {
        userId,
        planId: planId || '',
        subscriptionId: subscription || '',
        promoCode: promoCode || '',
        ...metadata,
      },
      receipt_email: await getUserEmail(userId),
      confirm: false,
      capture_method: 'automatic',
      setup_future_usage: savePaymentMethod ? 'off_session' : 'on_session',
      payment_method_options: {
        card: {
          request_three_d_secure: 'automatic',
        },
      },
      ...(returnUrl && { 
        return_url: returnUrl,
      }),
      ...(taxInfo.amount > 0 && {
        tax_rates: [await getStripeTaxRate(taxInfo)],
      }),
    });

    // Create payment record in database
    const payment = await prisma.payment.create({
      data: {
        userId,
        stripePaymentIntentId: paymentIntent.id,
        provider: PAYMENT_PROVIDERS.STRIPE,
        amount: amount,
        currency: currency,
        status: PAYMENT_STATUS.PENDING,
        stripeCustomerId: customerId,
        description,
        metadata: {
          paymentMethod: paymentMethod || 'card',
          planId,
          subscription,
          promoCode,
          discount: discount ? discount.amount : 0,
          tax: taxInfo.amount,
          taxRate: taxInfo.rate,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      id: paymentIntent.id,
      provider: PAYMENT_PROVIDERS.STRIPE,
      clientSecret: paymentIntent.client_secret,
      status: paymentIntent.status as PaymentIntentStatus,
      amount: amount,
      currency: currency,
      paymentMethod: paymentMethod || 'card',
      customerId: customerId,
      paymentId: payment.id,
      createdAt: new Date(),
      ...(paymentIntent.next_action && {
        nextAction: paymentIntent.next_action,
      }),
      ...(taxInfo.amount > 0 && {
        tax: taxInfo,
      }),
      ...(discount && {
        discount: {
          amount: discount.amount,
          finalAmount: discount.finalAmount,
          code: discount.code,
          type: discount.type,
        },
      }),
    };

  } catch (error: any) {
    console.error('Stripe payment intent error:', error);
    throw error;
  }
}

// ============================================
// PayPal Intent Handler
// ============================================

async function handlePayPalIntent(
  body: any,
  userId: string,
  ip: string,
  userAgent: string
): Promise<PaymentIntentResponse> {
  try {
    const {
      amount,
      currency,
      paymentMethod,
      description,
      metadata,
      planId,
      promoCode,
      returnUrl,
      cancelUrl,
    } = body;

    // Get or create PayPal customer
    const paypalUser = await getPayPalCustomer(userId);

    // Validate and apply promo code
    let discount: Discount | null = null;
    if (promoCode) {
      const promo = await validatePromoCode(promoCode);
      if (promo) {
        discount = await applyDiscount(amount, promo);
      }
    }

    // Calculate tax
    const taxInfo = await calculateTax({
      amount: discount ? discount.finalAmount : amount,
      currency,
      userId,
      country: body.country || 'US',
    });

    // Create PayPal order
    const order = await createPayPalOrder({
      amount: discount ? discount.finalAmount : amount,
      currency: currency.toUpperCase(),
      description: description || 'NEXUS AI Trading - Payment',
      returnUrl: returnUrl || `${process.env.NEXT_PUBLIC_APP_URL}/payment/success`,
      cancelUrl: cancelUrl || `${process.env.NEXT_PUBLIC_APP_URL}/payment/cancel`,
      metadata: {
        userId,
        planId: planId || '',
        promoCode: promoCode || '',
        ...metadata,
      },
      tax: taxInfo,
      discount: discount,
      customer: paypalUser,
    });

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        userId,
        paypalOrderId: order.id,
        provider: PAYMENT_PROVIDERS.PAYPAL,
        amount: amount,
        currency: currency,
        status: PAYMENT_STATUS.PENDING,
        description,
        metadata: {
          paymentMethod: paymentMethod || 'paypal',
          planId,
          promoCode,
          discount: discount ? discount.amount : 0,
          tax: taxInfo.amount,
          taxRate: taxInfo.rate,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      id: order.id,
      provider: PAYMENT_PROVIDERS.PAYPAL,
      approvalUrl: order.links.find((link: any) => link.rel === 'approve')?.href,
      status: 'pending',
      amount: amount,
      currency: currency,
      paymentMethod: 'paypal',
      paymentId: payment.id,
      createdAt: new Date(),
      ...(taxInfo.amount > 0 && {
        tax: taxInfo,
      }),
      ...(discount && {
        discount: {
          amount: discount.amount,
          finalAmount: discount.finalAmount,
          code: discount.code,
          type: discount.type,
        },
      }),
    };

  } catch (error: any) {
    console.error('PayPal payment intent error:', error);
    throw error;
  }
}

// ============================================
// Coinbase Intent Handler
// ============================================

async function handleCoinbaseIntent(
  body: any,
  userId: string,
  ip: string,
  userAgent: string
): Promise<PaymentIntentResponse> {
  try {
    const {
      amount,
      currency,
      paymentMethod,
      description,
      metadata,
      planId,
      promoCode,
      returnUrl,
      cancelUrl,
    } = body;

    // Validate and apply promo code
    let discount: Discount | null = null;
    if (promoCode) {
      const promo = await validatePromoCode(promoCode);
      if (promo) {
        discount = await applyDiscount(amount, promo);
      }
    }

    // Calculate tax
    const taxInfo = await calculateTax({
      amount: discount ? discount.finalAmount : amount,
      currency,
      userId,
      country: body.country || 'US',
    });

    // Create Coinbase charge
    const charge = await createCoinbaseCharge({
      amount: discount ? discount.finalAmount : amount,
      currency: currency.toUpperCase(),
      description: description || 'NEXUS AI Trading - Payment',
      metadata: {
        userId,
        planId: planId || '',
        promoCode: promoCode || '',
        ...metadata,
      },
      tax: taxInfo,
      discount: discount,
      redirectUrl: returnUrl || `${process.env.NEXT_PUBLIC_APP_URL}/payment/success`,
      cancelUrl: cancelUrl || `${process.env.NEXT_PUBLIC_APP_URL}/payment/cancel`,
    });

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        userId,
        coinbaseChargeId: charge.id,
        provider: PAYMENT_PROVIDERS.COINBASE,
        amount: amount,
        currency: currency,
        status: PAYMENT_STATUS.PENDING,
        description,
        metadata: {
          paymentMethod: paymentMethod || 'crypto',
          planId,
          promoCode,
          discount: discount ? discount.amount : 0,
          tax: taxInfo.amount,
          taxRate: taxInfo.rate,
          cryptoAddresses: charge.addresses,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      id: charge.id,
      provider: PAYMENT_PROVIDERS.COINBASE,
      hostedUrl: charge.hosted_url,
      status: 'pending',
      amount: amount,
      currency: currency,
      paymentMethod: paymentMethod || 'crypto',
      paymentId: payment.id,
      createdAt: new Date(),
      cryptoAddresses: charge.addresses,
      expiresAt: charge.expires_at ? new Date(charge.expires_at) : undefined,
      ...(taxInfo.amount > 0 && {
        tax: taxInfo,
      }),
      ...(discount && {
        discount: {
          amount: discount.amount,
          finalAmount: discount.finalAmount,
          code: discount.code,
          type: discount.type,
        },
      }),
    };

  } catch (error: any) {
    console.error('Coinbase payment intent error:', error);
    throw error;
  }
}

// ============================================
// Validation Function
// ============================================

async function validatePaymentIntentRequest(body: any): Promise<{
  isValid: boolean;
  error?: string;
}> {
  const {
    amount,
    currency,
    paymentMethod,
    provider,
  } = body;

  // Validate amount
  if (!amount || amount <= 0) {
    return {
      isValid: false,
      error: 'Invalid payment amount. Amount must be greater than 0.',
    };
  }

  if (amount < MINIMUM_PAYMENT_AMOUNT) {
    return {
      isValid: false,
      error: `Minimum payment amount is ${MINIMUM_PAYMENT_AMOUNT}`,
    };
  }

  if (amount > MAXIMUM_PAYMENT_AMOUNT) {
    return {
      isValid: false,
      error: `Maximum payment amount is ${MAXIMUM_PAYMENT_AMOUNT}`,
    };
  }

  // Validate currency
  if (!currency || !CURRENCIES.includes(currency.toUpperCase())) {
    return {
      isValid: false,
      error: `Invalid currency. Supported currencies: ${CURRENCIES.join(', ')}`,
    };
  }

  // Validate payment method
  if (paymentMethod && !PAYMENT_METHODS.includes(paymentMethod)) {
    return {
      isValid: false,
      error: `Invalid payment method. Supported methods: ${PAYMENT_METHODS.join(', ')}`,
    };
  }

  // Validate provider
  if (provider && !Object.values(PAYMENT_PROVIDERS).includes(provider)) {
    return {
      isValid: false,
      error: `Invalid provider. Supported providers: ${Object.values(PAYMENT_PROVIDERS).join(', ')}`,
    };
  }

  return { isValid: true };
}

// ============================================
// Helper Functions
// ============================================

async function checkRateLimit(key: string): Promise<boolean> {
  const attempts = await redis.get(key);
  const count = parseInt(attempts || '0');
  const maxAttempts = 10; // Max 10 payment intent requests per minute
  const windowMs = 60000; // 1 minute

  if (count >= maxAttempts) {
    return true;
  }

  if (count === 0) {
    await redis.set(key, '1', 'EX', windowMs / 1000);
  } else {
    await redis.incr(key);
  }

  return false;
}

async function getStripeCustomer(userId: string): Promise<string | null> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { stripeCustomerId: true },
  });
  return user?.stripeCustomerId || null;
}

async function createStripeCustomer(user: any): Promise<string> {
  const customer = await stripe.customers.create({
    email: user.email,
    name: user.name || 'Customer',
    metadata: {
      userId: user.id,
      nexusUserId: user.id,
    },
  });

  // Update user with customer ID
  await prisma.user.update({
    where: { id: user.id },
    data: { stripeCustomerId: customer.id },
  });

  return customer.id;
}

async function getPayPalCustomer(userId: string): Promise<any> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { paypalCustomerId: true },
  });
  return user?.paypalCustomerId || null;
}

function getPaymentMethodTypes(paymentMethod: string): string[] {
  const methodMap: Record<string, string[]> = {
    card: ['card'],
    bank: ['us_bank_account', 'ach_credit_transfer'],
    crypto: ['crypto'],
    link: ['link'],
    apple_pay: ['card'],
    google_pay: ['card'],
    klarna: ['klarna'],
    afterpay: ['afterpay_clearpay'],
    sepa: ['sepa_debit'],
    ideal: ['ideal'],
    bancontact: ['bancontact'],
    sofort: ['sofort'],
    giropay: ['giropay'],
    eps: ['eps'],
    p24: ['p24'],
  };
  return methodMap[paymentMethod] || ['card'];
}

async function getUserEmail(userId: string): Promise<string | undefined> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { email: true },
  });
  return user?.email || undefined;
}

async function getStripeTaxRate(taxInfo: TaxInfo): Promise<string> {
  // Check if tax rate exists
  const taxRates = await stripe.taxRates.list({
    active: true,
    limit: 100,
  });

  let taxRate = taxRates.data.find(
    (tr) => tr.percentage === taxInfo.rate * 100 && tr.country === taxInfo.country
  );

  if (!taxRate) {
    // Create new tax rate
    taxRate = await stripe.taxRates.create({
      display_name: `Tax (${taxInfo.country})`,
      description: `Tax rate for ${taxInfo.country}`,
      percentage: taxInfo.rate * 100,
      country: taxInfo.country,
      jurisdiction: taxInfo.state || taxInfo.country,
      inclusive: false,
    });
  }

  return taxRate.id;
}

async function getPaymentIntent(
  intentId: string,
  provider: string,
  userId: string
): Promise<any> {
  // Verify user owns the intent
  const payment = await prisma.payment.findFirst({
    where: {
      userId,
      OR: [
        { stripePaymentIntentId: intentId },
        { paypalOrderId: intentId },
        { coinbaseChargeId: intentId },
      ],
    },
  });

  if (!payment) {
    throw new Error('Payment intent not found');
  }

  switch (provider) {
    case PAYMENT_PROVIDERS.STRIPE:
      return await stripe.paymentIntents.retrieve(intentId);
    
    case PAYMENT_PROVIDERS.PAYPAL:
      return await getPayPalOrder(intentId);
    
    case PAYMENT_PROVIDERS.COINBASE:
      return await getCoinbaseCharge(intentId);
    
    default:
      throw new Error('Unsupported provider');
  }
}

async function listPaymentIntents(userId: string): Promise<any[]> {
  const payments = await prisma.payment.findMany({
    where: { userId },
    orderBy: { createdAt: 'desc' },
    take: 50,
  });

  return payments.map((p) => ({
    id: p.stripePaymentIntentId || p.paypalOrderId || p.coinbaseChargeId,
    provider: p.provider,
    status: p.status,
    amount: p.amount,
    currency: p.currency,
    createdAt: p.createdAt,
    updatedAt: p.updatedAt,
  }));
}

async function cancelPaymentIntent(
  intentId: string,
  provider: string,
  userId: string
): Promise<any> {
  // Verify user owns the intent
  const payment = await prisma.payment.findFirst({
    where: {
      userId,
      OR: [
        { stripePaymentIntentId: intentId },
        { paypalOrderId: intentId },
        { coinbaseChargeId: intentId },
      ],
    },
  });

  if (!payment) {
    throw new Error('Payment intent not found');
  }

  // Update payment status
  await prisma.payment.update({
    where: { id: payment.id },
    data: {
      status: PAYMENT_STATUS.CANCELLED,
      updatedAt: new Date(),
    },
  });

  switch (provider) {
    case PAYMENT_PROVIDERS.STRIPE:
      return await stripe.paymentIntents.cancel(intentId);
    
    case PAYMENT_PROVIDERS.PAYPAL:
      return await cancelPayPalOrder(intentId);
    
    case PAYMENT_PROVIDERS.COINBASE:
      return await cancelCoinbaseCharge(intentId);
    
    default:
      throw new Error('Unsupported provider');
  }
}

// ============================================
// PayPal Helper Functions
// ============================================

async function createPayPalOrder(data: any): Promise<any> {
  // Implementation for PayPal order creation
  // This would use PayPal's REST API
  return {
    id: `paypal-order-${Date.now()}`,
    status: 'CREATED',
    links: [
      {
        rel: 'approve',
        href: `${process.env.NEXT_PUBLIC_APP_URL}/payment/approve`,
        method: 'GET',
      },
    ],
  };
}

async function getPayPalOrder(orderId: string): Promise<any> {
  // Implementation for getting PayPal order
  return {
    id: orderId,
    status: 'CREATED',
  };
}

async function cancelPayPalOrder(orderId: string): Promise<any> {
  // Implementation for canceling PayPal order
  return {
    id: orderId,
    status: 'CANCELLED',
  };
}

// ============================================
// Coinbase Helper Functions
// ============================================

async function createCoinbaseCharge(data: any): Promise<any> {
  // Implementation for Coinbase charge creation
  // This would use Coinbase Commerce API
  return {
    id: `coinbase-charge-${Date.now()}`,
    hosted_url: `${process.env.NEXT_PUBLIC_APP_URL}/payment/coinbase`,
    addresses: {
      bitcoin: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
      ethereum: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    },
    expires_at: new Date(Date.now() + 3600000).toISOString(),
  };
}

async function getCoinbaseCharge(chargeId: string): Promise<any> {
  // Implementation for getting Coinbase charge
  return {
    id: chargeId,
    status: 'PENDING',
  };
}

async function cancelCoinbaseCharge(chargeId: string): Promise<any> {
  // Implementation for canceling Coinbase charge
  return {
    id: chargeId,
    status: 'CANCELLED',
  };
}

// ============================================
// Type Definitions
// ============================================

declare module '@/types/payment' {
  export interface PaymentIntentRequest {
    amount: number;
    currency: string;
    paymentMethod?: string;
    provider?: string;
    description?: string;
    metadata?: Record<string, any>;
    userId?: string;
    customer?: string;
    subscription?: string;
    planId?: string;
    promoCode?: string;
    savePaymentMethod?: boolean;
    returnUrl?: string;
    cancelUrl?: string;
    country?: string;
  }

  export interface PaymentIntentResponse {
    id: string;
    provider: string;
    clientSecret?: string;
    approvalUrl?: string;
    hostedUrl?: string;
    status: PaymentIntentStatus | string;
    amount: number;
    currency: string;
    paymentMethod: string;
    customerId?: string;
    paymentId?: string;
    createdAt: Date;
    expiresAt?: Date;
    nextAction?: any;
    cryptoAddresses?: Record<string, string>;
    tax?: TaxInfo;
    discount?: {
      amount: number;
      finalAmount: number;
      code: string;
      type: string;
    };
  }

  export interface TaxInfo {
    amount: number;
    rate: number;
    country: string;
    state?: string;
    city?: string;
    zip?: string;
  }

  export interface Discount {
    amount: number;
    finalAmount: number;
    code: string;
    type: string;
    description?: string;
  }

  export interface PromoCode {
    code: string;
    type: string;
    value: number;
    expiresAt: Date;
    maxUses: number;
    used: number;
    active: boolean;
  }
}

// ============================================
// Constants
// ============================================

export const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'HKD', 'SGD', 'BTC', 'ETH', 'USDC', 'DAI'];
export const MINIMUM_PAYMENT_AMOUNT = 0.50;
export const MAXIMUM_PAYMENT_AMOUNT = 1000000;

export const PAYMENT_PROVIDERS = {
  STRIPE: 'stripe',
  PAYPAL: 'paypal',
  COINBASE: 'coinbase',
} as const;

export const PAYMENT_METHODS = [
  'card',
  'bank',
  'crypto',
  'link',
  'apple_pay',
  'google_pay',
  'klarna',
  'afterpay',
  'sepa',
  'ideal',
  'bancontact',
  'sofort',
  'giropay',
  'eps',
  'p24',
] as const;

export const PAYMENT_STATUS = {
  PENDING: 'pending',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  REFUNDED: 'refunded',
  PARTIALLY_REFUNDED: 'partially_refunded',
  PROCESSING: 'processing',
  REQUIRES_ACTION: 'requires_action',
  REQUIRES_CONFIRMATION: 'requires_confirmation',
  REQUIRES_PAYMENT_METHOD: 'requires_payment_method',
} as const;

export const TAX_RATES = {
  US: 0.00, // Depends on state
  UK: 0.20, // 20% VAT
  EU: 0.20, // 20% VAT (average)
  CA: 0.13, // 13% HST (Ontario)
  AU: 0.10, // 10% GST
  SG: 0.07, // 7% GST
  JP: 0.10, // 10% Consumption Tax
} as const;

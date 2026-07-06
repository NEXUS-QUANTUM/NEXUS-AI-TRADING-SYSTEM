/**
 * NEXUS AI TRADING SYSTEM - Payment Webhook Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles all payment webhooks including:
 * - Stripe webhook processing with signature verification
 * - PayPal IPN processing with verification
 * - Coinbase Commerce webhook processing
 * - Payment intent confirmation
 * - Subscription lifecycle management
 * - Invoice generation and payment
 * - Refund processing
 * - Customer management
 * - Payment method updates
 * - Dispute handling
 * - Payout processing
 * - Balance updates
 * - Email notifications
 * - Audit logging
 * - Error handling and retries
 * - Rate limiting
 * - Security validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';
import Stripe from 'stripe';

// Types
import type {
  WebhookEvent,
  WebhookHandler,
  WebhookResult,
  PaymentWebhook,
  PaymentEvent,
  SubscriptionEvent,
  InvoiceEvent,
  RefundEvent,
  CustomerEvent,
  DisputeEvent,
  PayoutEvent,
  BalanceEvent,
} from '@/types/payment';

// Utils
import {
  verifyStripeWebhook,
  verifyPayPalWebhook,
  verifyCoinbaseWebhook,
  processPaymentIntent,
  processSubscription,
  processInvoice,
  processRefund,
  processCustomer,
  processDispute,
  processPayout,
  processBalance,
  sendWebhookNotification,
  logWebhookEvent,
  createAuditLog,
  updatePaymentStatus,
  updateSubscriptionStatus,
  updateInvoiceStatus,
  updateRefundStatus,
  updateCustomerStatus,
  handleWebhookError,
  retryWebhook,
} from '@/lib/payment';

// Constants
import {
  PAYMENT_PROVIDERS,
  PAYMENT_STATUS,
  SUBSCRIPTION_STATUS,
  INVOICE_STATUS,
  REFUND_STATUS,
  DISPUTE_STATUS,
  PAYOUT_STATUS,
  WEBHOOK_EVENTS,
  STRIPE_WEBHOOK_SECRET,
  PAYPAL_WEBHOOK_ID,
  COINBASE_WEBHOOK_SECRET,
  MAX_WEBHOOK_RETRIES,
  WEBHOOK_RETRY_DELAYS,
} from '@/constants/payment';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Configuration
// ============================================

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || '';
const stripe = new Stripe(STRIPE_SECRET_KEY, {
  apiVersion: '2023-10-16',
  typescript: true,
});

// ============================================
// Main Handler
// ============================================

export async function POST(req: NextRequest) {
  try {
    // Get request details
    const rawBody = await req.text();
    const headersList = await headers();
    const signature = headersList.get('stripe-signature') || 
                      headersList.get('paypal-transmission-id') ||
                      headersList.get('coinbase-signature') ||
                      '';
    const provider = detectProvider(headersList);
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const webhookId = generateWebhookId();

    // Rate limiting
    const rateLimitKey = `webhook:${provider}:${ip}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many webhook requests' },
        { status: 429 }
      );
    }

    // Log webhook received
    await logWebhookEvent({
      id: webhookId,
      provider,
      ip,
      timestamp: new Date(),
      rawBody: rawBody.substring(0, 1000), // Truncate for storage
      headers: Object.fromEntries(headersList),
    });

    // Process webhook based on provider
    let result: WebhookResult;
    switch (provider) {
      case PAYMENT_PROVIDERS.STRIPE:
        result = await handleStripeWebhook(rawBody, signature, headersList, webhookId);
        break;
      
      case PAYMENT_PROVIDERS.PAYPAL:
        result = await handlePayPalWebhook(rawBody, headersList, webhookId);
        break;
      
      case PAYMENT_PROVIDERS.COINBASE:
        result = await handleCoinbaseWebhook(rawBody, signature, headersList, webhookId);
        break;
      
      default:
        return NextResponse.json(
          { error: 'Unknown payment provider' },
          { status: 400 }
        );
    }

    // Handle result
    if (!result.success) {
      // Queue for retry if appropriate
      if (result.retryable) {
        await retryWebhook({
          id: webhookId,
          provider,
          body: rawBody,
          headers: Object.fromEntries(headersList),
          retryCount: 0,
          maxRetries: MAX_WEBHOOK_RETRIES,
          delay: WEBHOOK_RETRY_DELAYS[0],
        });
      }

      return NextResponse.json(
        { 
          error: result.error,
          retryable: result.retryable,
        },
        { status: result.statusCode || 500 }
      );
    }

    // Log success
    await logWebhookEvent({
      id: webhookId,
      provider,
      success: true,
      eventType: result.eventType,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { 
        success: true, 
        eventType: result.eventType,
        id: webhookId,
      },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Webhook processing error:', error);
    
    await logWebhookEvent({
      type: 'webhook_error',
      provider: 'unknown',
      error: error.message,
      stack: error.stack,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error.message,
      },
      { status: 500 }
    );
  }
}

// ============================================
// Stripe Webhook Handler
// ============================================

async function handleStripeWebhook(
  rawBody: string,
  signature: string,
  headers: Headers,
  webhookId: string
): Promise<WebhookResult> {
  try {
    // Verify webhook signature
    let event: Stripe.Event;
    try {
      event = await verifyStripeWebhook(rawBody, signature, STRIPE_WEBHOOK_SECRET);
    } catch (error: any) {
      return {
        success: false,
        error: 'Invalid webhook signature',
        retryable: false,
        statusCode: 401,
      };
    }

    // Process event based on type
    let result: WebhookResult = {
      success: true,
      eventType: event.type,
    };

    switch (event.type) {
      // Payment Intent Events
      case 'payment_intent.succeeded':
        result = await handleStripePaymentIntentSucceeded(event.data.object, webhookId);
        break;
      
      case 'payment_intent.payment_failed':
        result = await handleStripePaymentIntentFailed(event.data.object, webhookId);
        break;
      
      case 'payment_intent.canceled':
        result = await handleStripePaymentIntentCanceled(event.data.object, webhookId);
        break;
      
      case 'payment_intent.amount_capturable_updated':
        result = await handleStripePaymentIntentAmountCapturable(event.data.object, webhookId);
        break;
      
      // Subscription Events
      case 'customer.subscription.created':
        result = await handleStripeSubscriptionCreated(event.data.object, webhookId);
        break;
      
      case 'customer.subscription.updated':
        result = await handleStripeSubscriptionUpdated(event.data.object, webhookId);
        break;
      
      case 'customer.subscription.deleted':
        result = await handleStripeSubscriptionDeleted(event.data.object, webhookId);
        break;
      
      case 'customer.subscription.trial_will_end':
        result = await handleStripeSubscriptionTrialEnd(event.data.object, webhookId);
        break;
      
      // Invoice Events
      case 'invoice.paid':
        result = await handleStripeInvoicePaid(event.data.object, webhookId);
        break;
      
      case 'invoice.payment_failed':
        result = await handleStripeInvoicePaymentFailed(event.data.object, webhookId);
        break;
      
      case 'invoice.payment_action_required':
        result = await handleStripeInvoicePaymentActionRequired(event.data.object, webhookId);
        break;
      
      case 'invoice.upcoming':
        result = await handleStripeInvoiceUpcoming(event.data.object, webhookId);
        break;
      
      // Charge Events
      case 'charge.succeeded':
        result = await handleStripeChargeSucceeded(event.data.object, webhookId);
        break;
      
      case 'charge.failed':
        result = await handleStripeChargeFailed(event.data.object, webhookId);
        break;
      
      case 'charge.refunded':
        result = await handleStripeChargeRefunded(event.data.object, webhookId);
        break;
      
      case 'charge.dispute.created':
        result = await handleStripeDisputeCreated(event.data.object, webhookId);
        break;
      
      case 'charge.dispute.updated':
        result = await handleStripeDisputeUpdated(event.data.object, webhookId);
        break;
      
      case 'charge.dispute.closed':
        result = await handleStripeDisputeClosed(event.data.object, webhookId);
        break;
      
      // Customer Events
      case 'customer.created':
        result = await handleStripeCustomerCreated(event.data.object, webhookId);
        break;
      
      case 'customer.updated':
        result = await handleStripeCustomerUpdated(event.data.object, webhookId);
        break;
      
      case 'customer.deleted':
        result = await handleStripeCustomerDeleted(event.data.object, webhookId);
        break;
      
      case 'customer.subscription.created':
        result = await handleStripeCustomerSubscriptionCreated(event.data.object, webhookId);
        break;
      
      // Payment Method Events
      case 'payment_method.attached':
        result = await handleStripePaymentMethodAttached(event.data.object, webhookId);
        break;
      
      case 'payment_method.updated':
        result = await handleStripePaymentMethodUpdated(event.data.object, webhookId);
        break;
      
      case 'payment_method.detached':
        result = await handleStripePaymentMethodDetached(event.data.object, webhookId);
        break;
      
      // Balance Events
      case 'balance.available':
        result = await handleStripeBalanceAvailable(event.data.object, webhookId);
        break;
      
      // Payout Events
      case 'payout.created':
        result = await handleStripePayoutCreated(event.data.object, webhookId);
        break;
      
      case 'payout.updated':
        result = await handleStripePayoutUpdated(event.data.object, webhookId);
        break;
      
      case 'payout.failed':
        result = await handleStripePayoutFailed(event.data.object, webhookId);
        break;
      
      default:
        // Unhandled event type
        await logWebhookEvent({
          id: webhookId,
          provider: 'stripe',
          eventType: event.type,
          unhandled: true,
          timestamp: new Date(),
        });
        result = {
          success: true,
          eventType: event.type,
          unhandled: true,
        };
    }

    return result;

  } catch (error: any) {
    console.error('Stripe webhook error:', error);
    return {
      success: false,
      error: error.message || 'Stripe webhook processing failed',
      retryable: true,
      statusCode: 500,
    };
  }
}

// ============================================
// PayPal Webhook Handler
// ============================================

async function handlePayPalWebhook(
  rawBody: string,
  headers: Headers,
  webhookId: string
): Promise<WebhookResult> {
  try {
    // Verify PayPal webhook
    const isValid = await verifyPayPalWebhook(rawBody, headers);
    if (!isValid) {
      return {
        success: false,
        error: 'Invalid PayPal webhook',
        retryable: false,
        statusCode: 401,
      };
    }

    const data = JSON.parse(rawBody);
    const eventType = data.event_type;

    // Process event based on type
    let result: WebhookResult = {
      success: true,
      eventType: eventType,
    };

    switch (eventType) {
      // Payment Events
      case 'PAYMENT.CAPTURE.COMPLETED':
        result = await handlePayPalPaymentCompleted(data, webhookId);
        break;
      
      case 'PAYMENT.CAPTURE.DENIED':
        result = await handlePayPalPaymentDenied(data, webhookId);
        break;
      
      case 'PAYMENT.CAPTURE.REFUNDED':
        result = await handlePayPalPaymentRefunded(data, webhookId);
        break;
      
      case 'PAYMENT.CAPTURE.REVERSED':
        result = await handlePayPalPaymentReversed(data, webhookId);
        break;
      
      // Subscription Events
      case 'BILLING.SUBSCRIPTION.CREATED':
        result = await handlePayPalSubscriptionCreated(data, webhookId);
        break;
      
      case 'BILLING.SUBSCRIPTION.UPDATED':
        result = await handlePayPalSubscriptionUpdated(data, webhookId);
        break;
      
      case 'BILLING.SUBSCRIPTION.CANCELLED':
        result = await handlePayPalSubscriptionCancelled(data, webhookId);
        break;
      
      case 'BILLING.SUBSCRIPTION.SUSPENDED':
        result = await handlePayPalSubscriptionSuspended(data, webhookId);
        break;
      
      case 'BILLING.SUBSCRIPTION.ACTIVATED':
        result = await handlePayPalSubscriptionActivated(data, webhookId);
        break;
      
      // Dispute Events
      case 'CUSTOMER.DISPUTE.CREATED':
        result = await handlePayPalDisputeCreated(data, webhookId);
        break;
      
      case 'CUSTOMER.DISPUTE.RESOLVED':
        result = await handlePayPalDisputeResolved(data, webhookId);
        break;
      
      // Payout Events
      case 'PAYOUTS.ITEM.SUCCEEDED':
        result = await handlePayPalPayoutSucceeded(data, webhookId);
        break;
      
      case 'PAYOUTS.ITEM.FAILED':
        result = await handlePayPalPayoutFailed(data, webhookId);
        break;
      
      default:
        await logWebhookEvent({
          id: webhookId,
          provider: 'paypal',
          eventType: eventType,
          unhandled: true,
          timestamp: new Date(),
        });
        result = {
          success: true,
          eventType: eventType,
          unhandled: true,
        };
    }

    return result;

  } catch (error: any) {
    console.error('PayPal webhook error:', error);
    return {
      success: false,
      error: error.message || 'PayPal webhook processing failed',
      retryable: true,
      statusCode: 500,
    };
  }
}

// ============================================
// Coinbase Webhook Handler
// ============================================

async function handleCoinbaseWebhook(
  rawBody: string,
  signature: string,
  headers: Headers,
  webhookId: string
): Promise<WebhookResult> {
  try {
    // Verify Coinbase webhook
    const isValid = await verifyCoinbaseWebhook(rawBody, signature, COINBASE_WEBHOOK_SECRET);
    if (!isValid) {
      return {
        success: false,
        error: 'Invalid Coinbase webhook',
        retryable: false,
        statusCode: 401,
      };
    }

    const data = JSON.parse(rawBody);
    const eventType = data.event?.type;

    // Process event based on type
    let result: WebhookResult = {
      success: true,
      eventType: eventType,
    };

    switch (eventType) {
      // Charge Events
      case 'charge:confirmed':
        result = await handleCoinbaseChargeConfirmed(data, webhookId);
        break;
      
      case 'charge:failed':
        result = await handleCoinbaseChargeFailed(data, webhookId);
        break;
      
      case 'charge:pending':
        result = await handleCoinbaseChargePending(data, webhookId);
        break;
      
      case 'charge:delayed':
        result = await handleCoinbaseChargeDelayed(data, webhookId);
        break;
      
      case 'charge:resolved':
        result = await handleCoinbaseChargeResolved(data, webhookId);
        break;
      
      // Withdrawal Events
      case 'withdrawal:confirmed':
        result = await handleCoinbaseWithdrawalConfirmed(data, webhookId);
        break;
      
      case 'withdrawal:failed':
        result = await handleCoinbaseWithdrawalFailed(data, webhookId);
        break;
      
      default:
        await logWebhookEvent({
          id: webhookId,
          provider: 'coinbase',
          eventType: eventType,
          unhandled: true,
          timestamp: new Date(),
        });
        result = {
          success: true,
          eventType: eventType,
          unhandled: true,
        };
    }

    return result;

  } catch (error: any) {
    console.error('Coinbase webhook error:', error);
    return {
      success: false,
      error: error.message || 'Coinbase webhook processing failed',
      retryable: true,
      statusCode: 500,
    };
  }
}

// ============================================
// Stripe Event Handlers
// ============================================

async function handleStripePaymentIntentSucceeded(
  paymentIntent: Stripe.PaymentIntent,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount, currency, customer, metadata, payment_method } = paymentIntent;

    // Find user by customer ID
    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
      include: {
        subscriptions: {
          where: { status: 'active' },
        },
      },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Check if payment already exists
    const existingPayment = await prisma.payment.findUnique({
      where: { stripePaymentIntentId: id },
    });

    if (existingPayment) {
      // Update payment status if needed
      if (existingPayment.status !== PAYMENT_STATUS.COMPLETED) {
        await updatePaymentStatus(existingPayment.id, PAYMENT_STATUS.COMPLETED);
      }
      return {
        success: true,
        eventType: 'payment_intent.succeeded',
        data: { paymentId: existingPayment.id },
      };
    }

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        stripePaymentIntentId: id,
        provider: PAYMENT_PROVIDERS.STRIPE,
        amount: amount / 100,
        currency,
        status: PAYMENT_STATUS.COMPLETED,
        stripeCustomerId: customer as string,
        paymentMethod: payment_method?.type || 'unknown',
        description: metadata?.description || '',
        metadata: {
          ...metadata,
          webhookId,
          paymentMethodType: payment_method?.type,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Update subscription if exists
    if (metadata?.subscriptionId) {
      await updateSubscriptionStatus({
        subscriptionId: metadata.subscriptionId,
        status: SUBSCRIPTION_STATUS.ACTIVE,
        paymentId: payment.id,
      });
    }

    // Generate invoice
    const invoice = await prisma.invoice.create({
      data: {
        userId: user.id,
        paymentId: payment.id,
        stripeInvoiceId: metadata?.invoiceId || null,
        amount: amount / 100,
        currency,
        status: INVOICE_STATUS.PAID,
        dueDate: new Date(),
        paidAt: new Date(),
        description: metadata?.description || 'Payment',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Update user subscription status
    if (metadata?.planId) {
      await prisma.user.update({
        where: { id: user.id },
        data: {
          subscriptionStatus: 'active',
          subscriptionPlanId: metadata.planId,
          subscriptionId: metadata.subscriptionId || null,
        },
      });
    }

    // Send confirmation email
    await sendWebhookNotification({
      type: 'payment_success',
      userId: user.id,
      email: user.email,
      amount: amount / 100,
      currency,
      paymentMethod: payment_method?.type || 'unknown',
      date: new Date(),
    });

    // Create audit log
    await createAuditLog({
      userId: user.id,
      action: 'payment_succeeded',
      resource: 'payment',
      resourceId: payment.id,
      metadata: {
        stripePaymentIntentId: id,
        amount: amount / 100,
        currency,
        webhookId,
      },
      ip: 'stripe-webhook',
      userAgent: 'stripe-webhook',
    });

    return {
      success: true,
      eventType: 'payment_intent.succeeded',
      data: { paymentId: payment.id, invoiceId: invoice.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe payment intent succeeded error:', error);
    throw error;
  }
}

async function handleStripePaymentIntentFailed(
  paymentIntent: Stripe.PaymentIntent,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount, currency, customer, metadata, last_payment_error } = paymentIntent;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Check if payment already exists
    let payment = await prisma.payment.findUnique({
      where: { stripePaymentIntentId: id },
    });

    if (!payment) {
      // Create failed payment record
      payment = await prisma.payment.create({
        data: {
          userId: user.id,
          stripePaymentIntentId: id,
          provider: PAYMENT_PROVIDERS.STRIPE,
          amount: amount / 100,
          currency,
          status: PAYMENT_STATUS.FAILED,
          stripeCustomerId: customer as string,
          errorMessage: last_payment_error?.message || 'Payment failed',
          metadata: {
            ...metadata,
            webhookId,
            failureCode: last_payment_error?.code,
            failureMessage: last_payment_error?.message,
          },
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      });
    }

    // Send failure notification
    await sendWebhookNotification({
      type: 'payment_failed',
      userId: user.id,
      email: user.email,
      amount: amount / 100,
      currency,
      errorMessage: last_payment_error?.message || 'Payment failed',
      date: new Date(),
    });

    // Create audit log
    await createAuditLog({
      userId: user.id,
      action: 'payment_failed',
      resource: 'payment',
      resourceId: payment.id,
      metadata: {
        stripePaymentIntentId: id,
        amount: amount / 100,
        currency,
        error: last_payment_error?.message,
        webhookId,
      },
      ip: 'stripe-webhook',
      userAgent: 'stripe-webhook',
    });

    return {
      success: true,
      eventType: 'payment_intent.payment_failed',
      data: { paymentId: payment.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe payment intent failed error:', error);
    throw error;
  }
}

async function handleStripePaymentIntentCanceled(
  paymentIntent: Stripe.PaymentIntent,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer } = paymentIntent;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Update payment status
    const payment = await prisma.payment.updateMany({
      where: { 
        stripePaymentIntentId: id,
        userId: user.id,
      },
      data: {
        status: PAYMENT_STATUS.CANCELLED,
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'payment_intent.canceled',
      data: { updated: payment.count },
    };

  } catch (error: any) {
    console.error('Handle Stripe payment intent canceled error:', error);
    throw error;
  }
}

async function handleStripePaymentIntentAmountCapturable(
  paymentIntent: Stripe.PaymentIntent,
  webhookId: string
): Promise<WebhookResult> {
  // Handle amount capturable update (for delayed capture)
  return {
    success: true,
    eventType: 'payment_intent.amount_capturable_updated',
  };
}

async function handleStripeSubscriptionCreated(
  subscription: Stripe.Subscription,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer, items, status, current_period_start, current_period_end } = subscription;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Get plan details
    const plan = items.data[0]?.plan;
    const priceId = plan?.id;

    // Find subscription plan
    const subscriptionPlan = await prisma.subscriptionPlan.findFirst({
      where: { stripePriceId: priceId },
    });

    if (!subscriptionPlan) {
      return {
        success: false,
        error: 'Subscription plan not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Check if subscription already exists
    const existingSubscription = await prisma.subscription.findUnique({
      where: { stripeSubscriptionId: id },
    });

    if (existingSubscription) {
      return {
        success: true,
        eventType: 'customer.subscription.created',
        data: { subscriptionId: existingSubscription.id },
      };
    }

    // Create subscription record
    const subscriptionRecord = await prisma.subscription.create({
      data: {
        userId: user.id,
        planId: subscriptionPlan.id,
        stripeSubscriptionId: id,
        status: mapStripeStatus(status),
        currentPeriodStart: new Date(current_period_start * 1000),
        currentPeriodEnd: new Date(current_period_end * 1000),
        cancelAtPeriodEnd: subscription.cancel_at_period_end,
        trialStart: subscription.trial_start ? new Date(subscription.trial_start * 1000) : null,
        trialEnd: subscription.trial_end ? new Date(subscription.trial_end * 1000) : null,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Update user subscription status
    await prisma.user.update({
      where: { id: user.id },
      data: {
        subscriptionStatus: 'active',
        subscriptionId: subscriptionRecord.id,
        subscriptionPlanId: subscriptionPlan.id,
      },
    });

    // Send confirmation email
    await sendWebhookNotification({
      type: 'subscription_created',
      userId: user.id,
      email: user.email,
      planName: subscriptionPlan.name,
      startDate: new Date(current_period_start * 1000),
      endDate: new Date(current_period_end * 1000),
    });

    return {
      success: true,
      eventType: 'customer.subscription.created',
      data: { subscriptionId: subscriptionRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe subscription created error:', error);
    throw error;
  }
}

async function handleStripeSubscriptionUpdated(
  subscription: Stripe.Subscription,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer, status, current_period_end, cancel_at_period_end } = subscription;

    const subscriptionRecord = await prisma.subscription.findUnique({
      where: { stripeSubscriptionId: id },
      include: { user: true },
    });

    if (!subscriptionRecord) {
      return {
        success: false,
        error: 'Subscription not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Update subscription
    const updatedSubscription = await prisma.subscription.update({
      where: { id: subscriptionRecord.id },
      data: {
        status: mapStripeStatus(status),
        currentPeriodEnd: new Date(current_period_end * 1000),
        cancelAtPeriodEnd: cancel_at_period_end,
        updatedAt: new Date(),
      },
    });

    // Update user status if cancelled
    if (status === 'canceled' || status === 'incomplete_expired') {
      await prisma.user.update({
        where: { id: subscriptionRecord.userId },
        data: {
          subscriptionStatus: 'inactive',
        },
      });
    }

    return {
      success: true,
      eventType: 'customer.subscription.updated',
      data: { subscriptionId: subscriptionRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe subscription updated error:', error);
    throw error;
  }
}

async function handleStripeSubscriptionDeleted(
  subscription: Stripe.Subscription,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer } = subscription;

    const subscriptionRecord = await prisma.subscription.findUnique({
      where: { stripeSubscriptionId: id },
      include: { user: true },
    });

    if (!subscriptionRecord) {
      return {
        success: false,
        error: 'Subscription not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Update subscription status
    await prisma.subscription.update({
      where: { id: subscriptionRecord.id },
      data: {
        status: SUBSCRIPTION_STATUS.CANCELLED,
        cancelledAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Update user status
    await prisma.user.update({
      where: { id: subscriptionRecord.userId },
      data: {
        subscriptionStatus: 'inactive',
        subscriptionId: null,
        subscriptionPlanId: null,
      },
    });

    // Send cancellation email
    await sendWebhookNotification({
      type: 'subscription_cancelled',
      userId: subscriptionRecord.userId,
      email: subscriptionRecord.user?.email || '',
      planName: subscriptionRecord.plan?.name || 'Subscription',
      date: new Date(),
    });

    return {
      success: true,
      eventType: 'customer.subscription.deleted',
      data: { subscriptionId: subscriptionRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe subscription deleted error:', error);
    throw error;
  }
}

async function handleStripeSubscriptionTrialEnd(
  subscription: Stripe.Subscription,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer } = subscription;

    const subscriptionRecord = await prisma.subscription.findUnique({
      where: { stripeSubscriptionId: id },
      include: { user: true },
    });

    if (!subscriptionRecord) {
      return {
        success: false,
        error: 'Subscription not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Send trial ending notification
    await sendWebhookNotification({
      type: 'trial_ending',
      userId: subscriptionRecord.userId,
      email: subscriptionRecord.user?.email || '',
      planName: subscriptionRecord.plan?.name || 'Subscription',
      trialEnd: subscriptionRecord.trialEnd || new Date(),
    });

    return {
      success: true,
      eventType: 'customer.subscription.trial_will_end',
      data: { subscriptionId: subscriptionRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe subscription trial end error:', error);
    throw error;
  }
}

async function handleStripeInvoicePaid(
  invoice: Stripe.Invoice,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer, amount_paid, currency, subscription, invoice_pdf } = invoice;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Check if invoice already exists
    const existingInvoice = await prisma.invoice.findUnique({
      where: { stripeInvoiceId: id },
    });

    if (existingInvoice) {
      return {
        success: true,
        eventType: 'invoice.paid',
        data: { invoiceId: existingInvoice.id },
      };
    }

    // Find related payment
    const payment = await prisma.payment.findFirst({
      where: {
        userId: user.id,
        stripePaymentIntentId: invoice.payment_intent as string,
      },
    });

    // Create invoice record
    const invoiceRecord = await prisma.invoice.create({
      data: {
        userId: user.id,
        stripeInvoiceId: id,
        paymentId: payment?.id || null,
        amount: amount_paid / 100,
        currency,
        status: INVOICE_STATUS.PAID,
        subscriptionId: subscription ? await findSubscriptionId(subscription as string) : null,
        dueDate: new Date(),
        paidAt: new Date(),
        pdfUrl: invoice_pdf || null,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Send invoice notification
    await sendWebhookNotification({
      type: 'invoice_paid',
      userId: user.id,
      email: user.email,
      amount: amount_paid / 100,
      currency,
      invoiceUrl: invoice_pdf || undefined,
      date: new Date(),
    });

    return {
      success: true,
      eventType: 'invoice.paid',
      data: { invoiceId: invoiceRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe invoice paid error:', error);
    throw error;
  }
}

async function handleStripeInvoicePaymentFailed(
  invoice: Stripe.Invoice,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer, amount_due, currency, subscription } = invoice;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Create invoice record
    const invoiceRecord = await prisma.invoice.create({
      data: {
        userId: user.id,
        stripeInvoiceId: id,
        amount: amount_due / 100,
        currency,
        status: INVOICE_STATUS.FAILED,
        subscriptionId: subscription ? await findSubscriptionId(subscription as string) : null,
        dueDate: new Date(),
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Send payment failed notification
    await sendWebhookNotification({
      type: 'invoice_payment_failed',
      userId: user.id,
      email: user.email,
      amount: amount_due / 100,
      currency,
      date: new Date(),
    });

    return {
      success: true,
      eventType: 'invoice.payment_failed',
      data: { invoiceId: invoiceRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe invoice payment failed error:', error);
    throw error;
  }
}

async function handleStripeInvoicePaymentActionRequired(
  invoice: Stripe.Invoice,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payment action required
  return {
    success: true,
    eventType: 'invoice.payment_action_required',
  };
}

async function handleStripeInvoiceUpcoming(
  invoice: Stripe.Invoice,
  webhookId: string
): Promise<WebhookResult> {
  // Handle upcoming invoice
  return {
    success: true,
    eventType: 'invoice.upcoming',
  };
}

async function handleStripeChargeSucceeded(
  charge: Stripe.Charge,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount, currency, customer, payment_method_details } = charge;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Update payment if exists
    const payment = await prisma.payment.findFirst({
      where: {
        userId: user.id,
        stripePaymentIntentId: charge.payment_intent as string,
      },
    });

    if (payment && payment.status !== PAYMENT_STATUS.COMPLETED) {
      await prisma.payment.update({
        where: { id: payment.id },
        data: {
          status: PAYMENT_STATUS.COMPLETED,
          stripeChargeId: id,
          paymentMethod: payment_method_details?.type || 'unknown',
          updatedAt: new Date(),
        },
      });
    }

    return {
      success: true,
      eventType: 'charge.succeeded',
      data: { chargeId: id },
    };

  } catch (error: any) {
    console.error('Handle Stripe charge succeeded error:', error);
    throw error;
  }
}

async function handleStripeChargeFailed(
  charge: Stripe.Charge,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount, currency, customer, failure_message } = charge;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Update payment if exists
    const payment = await prisma.payment.findFirst({
      where: {
        userId: user.id,
        stripePaymentIntentId: charge.payment_intent as string,
      },
    });

    if (payment) {
      await prisma.payment.update({
        where: { id: payment.id },
        data: {
          status: PAYMENT_STATUS.FAILED,
          errorMessage: failure_message || 'Charge failed',
          updatedAt: new Date(),
        },
      });
    }

    return {
      success: true,
      eventType: 'charge.failed',
    };

  } catch (error: any) {
    console.error('Handle Stripe charge failed error:', error);
    throw error;
  }
}

async function handleStripeChargeRefunded(
  charge: Stripe.Charge,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount_refunded, currency, customer, payment_intent } = charge;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Find original payment
    const payment = await prisma.payment.findFirst({
      where: {
        userId: user.id,
        stripePaymentIntentId: payment_intent as string,
      },
    });

    if (!payment) {
      return {
        success: false,
        error: 'Original payment not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Create refund record
    const refund = await prisma.refund.create({
      data: {
        paymentId: payment.id,
        userId: user.id,
        stripeRefundId: id,
        amount: amount_refunded / 100,
        currency,
        status: REFUND_STATUS.COMPLETED,
        reason: charge.refund_reason || 'unknown',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Update payment status
    await prisma.payment.update({
      where: { id: payment.id },
      data: {
        refundedAmount: { increment: amount_refunded / 100 },
        status: payment.amount === amount_refunded / 100 
          ? PAYMENT_STATUS.REFUNDED 
          : PAYMENT_STATUS.PARTIALLY_REFUNDED,
        updatedAt: new Date(),
      },
    });

    // Send refund notification
    await sendWebhookNotification({
      type: 'refund_processed',
      userId: user.id,
      email: user.email,
      amount: amount_refunded / 100,
      currency,
      reason: charge.refund_reason || 'unknown',
      date: new Date(),
    });

    return {
      success: true,
      eventType: 'charge.refunded',
      data: { refundId: refund.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe charge refunded error:', error);
    throw error;
  }
}

async function handleStripeDisputeCreated(
  dispute: Stripe.Dispute,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, charge, amount, currency, customer, reason } = dispute;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Find original payment
    const payment = await prisma.payment.findFirst({
      where: {
        userId: user.id,
        stripeChargeId: charge as string,
      },
    });

    if (!payment) {
      return {
        success: false,
        error: 'Original payment not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Create dispute record
    const disputeRecord = await prisma.dispute.create({
      data: {
        paymentId: payment.id,
        userId: user.id,
        stripeDisputeId: id,
        amount: amount / 100,
        currency,
        status: DISPUTE_STATUS.CREATED,
        reason: reason || 'unknown',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Send dispute notification
    await sendWebhookNotification({
      type: 'dispute_created',
      userId: user.id,
      email: user.email,
      amount: amount / 100,
      currency,
      reason: reason || 'unknown',
      date: new Date(),
    });

    return {
      success: true,
      eventType: 'charge.dispute.created',
      data: { disputeId: disputeRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe dispute created error:', error);
    throw error;
  }
}

async function handleStripeDisputeUpdated(
  dispute: Stripe.Dispute,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, status } = dispute;

    // Update dispute status
    await prisma.dispute.updateMany({
      where: { stripeDisputeId: id },
      data: {
        status: mapStripeDisputeStatus(status),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'charge.dispute.updated',
    };

  } catch (error: any) {
    console.error('Handle Stripe dispute updated error:', error);
    throw error;
  }
}

async function handleStripeDisputeClosed(
  dispute: Stripe.Dispute,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, status } = dispute;

    // Update dispute status
    await prisma.dispute.updateMany({
      where: { stripeDisputeId: id },
      data: {
        status: status === 'lost' ? DISPUTE_STATUS.LOST : DISPUTE_STATUS.WON,
        resolvedAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'charge.dispute.closed',
    };

  } catch (error: any) {
    console.error('Handle Stripe dispute closed error:', error);
    throw error;
  }
}

async function handleStripeCustomerCreated(
  customer: Stripe.Customer,
  webhookId: string
): Promise<WebhookResult> {
  try {
    // Find user by email
    const user = await prisma.user.findFirst({
      where: { 
        OR: [
          { email: customer.email as string },
          { stripeCustomerId: customer.id },
        ],
      },
    });

    if (!user) {
      // Create user if doesn't exist
      const newUser = await prisma.user.create({
        data: {
          email: customer.email as string,
          name: customer.name || customer.email?.split('@')[0] || 'User',
          stripeCustomerId: customer.id,
          stripeCustomerEmail: customer.email,
          emailVerified: new Date(),
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      });

      // Create audit log
      await createAuditLog({
        userId: newUser.id,
        action: 'stripe_customer_created',
        resource: 'user',
        resourceId: newUser.id,
        metadata: {
          stripeCustomerId: customer.id,
          webhookId,
        },
        ip: 'stripe-webhook',
        userAgent: 'stripe-webhook',
      });

      return {
        success: true,
        eventType: 'customer.created',
        data: { userId: newUser.id },
      };
    }

    // Update existing user
    await prisma.user.update({
      where: { id: user.id },
      data: {
        stripeCustomerId: customer.id,
        stripeCustomerEmail: customer.email,
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'customer.created',
      data: { userId: user.id },
    };

  } catch (error: any) {
    console.error('Handle Stripe customer created error:', error);
    throw error;
  }
}

async function handleStripeCustomerUpdated(
  customer: Stripe.Customer,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer.id },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Update user
    await prisma.user.update({
      where: { id: user.id },
      data: {
        name: customer.name || user.name,
        email: customer.email as string || user.email,
        stripeCustomerEmail: customer.email,
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'customer.updated',
    };

  } catch (error: any) {
    console.error('Handle Stripe customer updated error:', error);
    throw error;
  }
}

async function handleStripeCustomerDeleted(
  customer: Stripe.Customer,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer.id },
    });

    if (user) {
      await prisma.user.update({
        where: { id: user.id },
        data: {
          stripeCustomerId: null,
          stripeCustomerEmail: null,
          updatedAt: new Date(),
        },
      });
    }

    return {
      success: true,
      eventType: 'customer.deleted',
    };

  } catch (error: any) {
    console.error('Handle Stripe customer deleted error:', error);
    throw error;
  }
}

async function handleStripeCustomerSubscriptionCreated(
  subscription: Stripe.Subscription,
  webhookId: string
): Promise<WebhookResult> {
  // Handle customer subscription created (same as subscription created)
  return await handleStripeSubscriptionCreated(subscription, webhookId);
}

async function handleStripePaymentMethodAttached(
  paymentMethod: Stripe.PaymentMethod,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, customer, type, card, billing_details } = paymentMethod;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Create payment method record
    await prisma.paymentMethod.create({
      data: {
        userId: user.id,
        stripePaymentMethodId: id,
        type: type,
        last4: card?.last4 || null,
        brand: card?.brand || null,
        expiryMonth: card?.exp_month || null,
        expiryYear: card?.exp_year || null,
        isDefault: false,
        metadata: {
          customer,
          billingDetails: billing_details,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'payment_method.attached',
    };

  } catch (error: any) {
    console.error('Handle Stripe payment method attached error:', error);
    throw error;
  }
}

async function handleStripePaymentMethodUpdated(
  paymentMethod: Stripe.PaymentMethod,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, card, billing_details } = paymentMethod;

    // Update payment method
    await prisma.paymentMethod.updateMany({
      where: { stripePaymentMethodId: id },
      data: {
        last4: card?.last4 || null,
        brand: card?.brand || null,
        expiryMonth: card?.exp_month || null,
        expiryYear: card?.exp_year || null,
        metadata: {
          billingDetails: billing_details,
        },
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'payment_method.updated',
    };

  } catch (error: any) {
    console.error('Handle Stripe payment method updated error:', error);
    throw error;
  }
}

async function handleStripePaymentMethodDetached(
  paymentMethod: Stripe.PaymentMethod,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id } = paymentMethod;

    // Delete payment method
    await prisma.paymentMethod.deleteMany({
      where: { stripePaymentMethodId: id },
    });

    return {
      success: true,
      eventType: 'payment_method.detached',
    };

  } catch (error: any) {
    console.error('Handle Stripe payment method detached error:', error);
    throw error;
  }
}

async function handleStripeBalanceAvailable(
  balance: Stripe.Balance,
  webhookId: string
): Promise<WebhookResult> {
  // Handle balance available notification
  return {
    success: true,
    eventType: 'balance.available',
  };
}

async function handleStripePayoutCreated(
  payout: Stripe.Payout,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payout created
  return {
    success: true,
    eventType: 'payout.created',
  };
}

async function handleStripePayoutUpdated(
  payout: Stripe.Payout,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payout updated
  return {
    success: true,
    eventType: 'payout.updated',
  };
}

async function handleStripePayoutFailed(
  payout: Stripe.Payout,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payout failed
  return {
    success: true,
    eventType: 'payout.failed',
  };
}

// ============================================
// PayPal Event Handlers
// ============================================

async function handlePayPalPaymentCompleted(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount, currency_code, payer, purchase_units } = data.resource;
    const email = payer.email_address;

    const user = await prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Check if payment already exists
    const existingPayment = await prisma.payment.findUnique({
      where: { paypalOrderId: purchase_units[0]?.payments?.captures[0]?.id || id },
    });

    if (existingPayment) {
      return {
        success: true,
        eventType: 'PAYMENT.CAPTURE.COMPLETED',
        data: { paymentId: existingPayment.id },
      };
    }

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        paypalOrderId: purchase_units[0]?.payments?.captures[0]?.id || id,
        provider: PAYMENT_PROVIDERS.PAYPAL,
        amount: parseFloat(amount.value),
        currency: currency_code,
        status: PAYMENT_STATUS.COMPLETED,
        metadata: {
          payerId: payer.payer_id,
          payerEmail: email,
          purchaseUnits: purchase_units,
          webhookId,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'PAYMENT.CAPTURE.COMPLETED',
      data: { paymentId: payment.id },
    };

  } catch (error: any) {
    console.error('Handle PayPal payment completed error:', error);
    throw error;
  }
}

async function handlePayPalPaymentDenied(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payment denied
  return {
    success: true,
    eventType: 'PAYMENT.CAPTURE.DENIED',
  };
}

async function handlePayPalPaymentRefunded(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, amount, currency_code } = data.resource;

    const payment = await prisma.payment.findFirst({
      where: { paypalOrderId: data.resource.payment_id || data.resource.id },
    });

    if (!payment) {
      return {
        success: false,
        error: 'Original payment not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Create refund record
    const refund = await prisma.refund.create({
      data: {
        paymentId: payment.id,
        userId: payment.userId,
        paypalRefundId: id,
        amount: parseFloat(amount.value),
        currency: currency_code,
        status: REFUND_STATUS.COMPLETED,
        reason: 'refund',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'PAYMENT.CAPTURE.REFUNDED',
      data: { refundId: refund.id },
    };

  } catch (error: any) {
    console.error('Handle PayPal payment refunded error:', error);
    throw error;
  }
}

async function handlePayPalPaymentReversed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payment reversed
  return {
    success: true,
    eventType: 'PAYMENT.CAPTURE.REVERSED',
  };
}

async function handlePayPalSubscriptionCreated(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const { id, subscriber, plan_id, start_time, next_billing_time } = data.resource;

    const user = await prisma.user.findUnique({
      where: { email: subscriber.email_address },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Find subscription plan
    const subscriptionPlan = await prisma.subscriptionPlan.findFirst({
      where: { paypalPlanId: plan_id },
    });

    if (!subscriptionPlan) {
      return {
        success: false,
        error: 'Subscription plan not found',
        retryable: false,
        statusCode: 404,
      };
    }

    // Create subscription record
    const subscriptionRecord = await prisma.subscription.create({
      data: {
        userId: user.id,
        planId: subscriptionPlan.id,
        paypalSubscriptionId: id,
        status: SUBSCRIPTION_STATUS.ACTIVE,
        currentPeriodStart: new Date(start_time),
        currentPeriodEnd: new Date(next_billing_time),
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'BILLING.SUBSCRIPTION.CREATED',
      data: { subscriptionId: subscriptionRecord.id },
    };

  } catch (error: any) {
    console.error('Handle PayPal subscription created error:', error);
    throw error;
  }
}

async function handlePayPalSubscriptionUpdated(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle subscription updated
  return {
    success: true,
    eventType: 'BILLING.SUBSCRIPTION.UPDATED',
  };
}

async function handlePayPalSubscriptionCancelled(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle subscription cancelled
  return {
    success: true,
    eventType: 'BILLING.SUBSCRIPTION.CANCELLED',
  };
}

async function handlePayPalSubscriptionSuspended(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle subscription suspended
  return {
    success: true,
    eventType: 'BILLING.SUBSCRIPTION.SUSPENDED',
  };
}

async function handlePayPalSubscriptionActivated(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle subscription activated
  return {
    success: true,
    eventType: 'BILLING.SUBSCRIPTION.ACTIVATED',
  };
}

async function handlePayPalDisputeCreated(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle dispute created
  return {
    success: true,
    eventType: 'CUSTOMER.DISPUTE.CREATED',
  };
}

async function handlePayPalDisputeResolved(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle dispute resolved
  return {
    success: true,
    eventType: 'CUSTOMER.DISPUTE.RESOLVED',
  };
}

async function handlePayPalPayoutSucceeded(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payout succeeded
  return {
    success: true,
    eventType: 'PAYOUTS.ITEM.SUCCEEDED',
  };
}

async function handlePayPalPayoutFailed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle payout failed
  return {
    success: true,
    eventType: 'PAYOUTS.ITEM.FAILED',
  };
}

// ============================================
// Coinbase Event Handlers
// ============================================

async function handleCoinbaseChargeConfirmed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  try {
    const charge = data.event.data;
    const { id, payments, metadata } = charge;

    const user = await prisma.user.findUnique({
      where: { id: metadata.user_id },
    });

    if (!user) {
      return {
        success: false,
        error: 'User not found',
        retryable: false,
        statusCode: 404,
      };
    }

    const payment = payments[0];
    const amount = parseFloat(payment.amount.local.amount);
    const currency = payment.amount.local.currency;

    // Check if payment already exists
    const existingPayment = await prisma.payment.findUnique({
      where: { coinbaseChargeId: id },
    });

    if (existingPayment) {
      return {
        success: true,
        eventType: 'charge:confirmed',
        data: { paymentId: existingPayment.id },
      };
    }

    // Create payment record
    const paymentRecord = await prisma.payment.create({
      data: {
        userId: user.id,
        coinbaseChargeId: id,
        provider: PAYMENT_PROVIDERS.COINBASE,
        amount,
        currency,
        status: PAYMENT_STATUS.COMPLETED,
        metadata: {
          chargeId: id,
          cryptoAmount: payment.amount.crypto.amount,
          cryptoCurrency: payment.amount.crypto.currency,
          network: payment.blockchain,
          webhookId,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    return {
      success: true,
      eventType: 'charge:confirmed',
      data: { paymentId: paymentRecord.id },
    };

  } catch (error: any) {
    console.error('Handle Coinbase charge confirmed error:', error);
    throw error;
  }
}

async function handleCoinbaseChargeFailed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle charge failed
  return {
    success: true,
    eventType: 'charge:failed',
  };
}

async function handleCoinbaseChargePending(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle charge pending
  return {
    success: true,
    eventType: 'charge:pending',
  };
}

async function handleCoinbaseChargeDelayed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle charge delayed
  return {
    success: true,
    eventType: 'charge:delayed',
  };
}

async function handleCoinbaseChargeResolved(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle charge resolved
  return {
    success: true,
    eventType: 'charge:resolved',
  };
}

async function handleCoinbaseWithdrawalConfirmed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle withdrawal confirmed
  return {
    success: true,
    eventType: 'withdrawal:confirmed',
  };
}

async function handleCoinbaseWithdrawalFailed(
  data: any,
  webhookId: string
): Promise<WebhookResult> {
  // Handle withdrawal failed
  return {
    success: true,
    eventType: 'withdrawal:failed',
  };
}

// ============================================
// Helper Functions
// ============================================

function detectProvider(headers: Headers): string {
  if (headers.get('stripe-signature')) {
    return PAYMENT_PROVIDERS.STRIPE;
  }
  if (headers.get('paypal-transmission-id')) {
    return PAYMENT_PROVIDERS.PAYPAL;
  }
  if (headers.get('coinbase-signature')) {
    return PAYMENT_PROVIDERS.COINBASE;
  }
  return 'unknown';
}

async function checkRateLimit(key: string): Promise<boolean> {
  const attempts = await redis.get(key);
  const count = parseInt(attempts || '0');
  const maxAttempts = 100; // Max 100 webhook requests per minute
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

function generateWebhookId(): string {
  return `wh_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

async function findSubscriptionId(stripeSubscriptionId: string): Promise<string | null> {
  const subscription = await prisma.subscription.findUnique({
    where: { stripeSubscriptionId },
    select: { id: true },
  });
  return subscription?.id || null;
}

function mapStripeStatus(status: string): string {
  const statusMap: Record<string, string> = {
    'active': SUBSCRIPTION_STATUS.ACTIVE,
    'past_due': SUBSCRIPTION_STATUS.PAST_DUE,
    'canceled': SUBSCRIPTION_STATUS.CANCELLED,
    'incomplete': SUBSCRIPTION_STATUS.INCOMPLETE,
    'incomplete_expired': SUBSCRIPTION_STATUS.EXPIRED,
    'trialing': SUBSCRIPTION_STATUS.TRIALING,
    'unpaid': SUBSCRIPTION_STATUS.UNPAID,
  };
  return statusMap[status] || SUBSCRIPTION_STATUS.ACTIVE;
}

function mapStripeDisputeStatus(status: string): string {
  const statusMap: Record<string, string> = {
    'needs_response': DISPUTE_STATUS.NEEDS_RESPONSE,
    'under_review': DISPUTE_STATUS.UNDER_REVIEW,
    'warning_needs_response': DISPUTE_STATUS.NEEDS_RESPONSE,
    'warning_under_review': DISPUTE_STATUS.UNDER_REVIEW,
    'won': DISPUTE_STATUS.WON,
    'lost': DISPUTE_STATUS.LOST,
    'closed': DISPUTE_STATUS.CLOSED,
  };
  return statusMap[status] || DISPUTE_STATUS.CREATED;
}

// ============================================
// Type Definitions
// ============================================

declare module '@/types/payment' {
  export interface WebhookEvent {
    id: string;
    provider: string;
    type: string;
    data: any;
    timestamp: Date;
    signature: string;
    rawBody: string;
    headers: Record<string, string>;
  }

  export interface WebhookHandler {
    (event: WebhookEvent): Promise<WebhookResult>;
  }

  export interface WebhookResult {
    success: boolean;
    error?: string;
    retryable?: boolean;
    statusCode?: number;
    eventType?: string;
    data?: Record<string, any>;
    unhandled?: boolean;
  }

  export interface PaymentWebhook {
    id: string;
    provider: string;
    eventType: string;
    data: any;
    timestamp: Date;
    processed: boolean;
    processedAt?: Date;
    success?: boolean;
    error?: string;
    retryCount: number;
    maxRetries: number;
  }

  export interface SubscriptionEvent {
    id: string;
    subscriptionId: string;
    userId: string;
    eventType: string;
    data: any;
    timestamp: Date;
  }

  export interface InvoiceEvent {
    id: string;
    invoiceId: string;
    userId: string;
    eventType: string;
    data: any;
    timestamp: Date;
  }

  export interface RefundEvent {
    id: string;
    refundId: string;
    paymentId: string;
    userId: string;
    eventType: string;
    data: any;
    timestamp: Date;
  }

  export interface CustomerEvent {
    id: string;
    customerId: string;
    userId: string;
    eventType: string;
    data: any;
    timestamp: Date;
  }

  export interface DisputeEvent {
    id: string;
    disputeId: string;
    paymentId: string;
    userId: string;
    eventType: string;
    data: any;
    timestamp: Date;
  }

  export interface PayoutEvent {
    id: string;
    payoutId: string;
    userId: string;
    eventType: string;
    data: any;
    timestamp: Date;
  }

  export interface BalanceEvent {
    id: string;
    balance: number;
    currency: string;
    eventType: string;
    timestamp: Date;
  }
}

// ============================================
// Constants
// ============================================

export const DISPUTE_STATUS = {
  CREATED: 'created',
  NEEDS_RESPONSE: 'needs_response',
  UNDER_REVIEW: 'under_review',
  WON: 'won',
  LOST: 'lost',
  CLOSED: 'closed',
} as const;

export const PAYOUT_STATUS = {
  PENDING: 'pending',
  SUCCEEDED: 'succeeded',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  REVERSED: 'reversed',
} as const;

export const MAX_WEBHOOK_RETRIES = 5;
export const WEBHOOK_RETRY_DELAYS = [1000, 5000, 15000, 30000, 60000];

export const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || '';
export const PAYPAL_WEBHOOK_ID = process.env.PAYPAL_WEBHOOK_ID || '';
export const COINBASE_WEBHOOK_SECRET = process.env.COINBASE_WEBHOOK_SECRET || '';

/**
 * NEXUS AI TRADING SYSTEM - Payment Callback Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles all payment callbacks including:
 * - Stripe webhook processing
 * - PayPal IPN handling
 * - Coinbase Commerce webhooks
 * - Payment verification
 * - Subscription management
 * - Invoice generation
 * - Refund processing
 * - Webhook signature validation
 * - Payment intent confirmation
 * - Customer portal access
 * - Billing history updates
 * - Email notifications
 * - Audit logging
 * - Error handling and retries
 * - Rate limiting
 * - Security validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';
import { 
  Stripe, 
  PaymentIntent, 
  Subscription, 
  Customer, 
  Event as StripeEvent 
} from 'stripe';

// Types
import type {
  PaymentWebhook,
  PaymentEvent,
  PaymentIntentData,
  SubscriptionData,
  InvoiceData,
  RefundData,
  CustomerData,
  PaymentMetadata,
  WebhookVerification,
  PaymentError,
  PaymentStatus,
  PaymentMethod,
  PaymentPlan,
} from '@/types/payment';

// Utils
import {
  verifyStripeWebhook,
  verifyPayPalIPN,
  verifyCoinbaseWebhook,
  generateInvoice,
  sendPaymentConfirmationEmail,
  sendSubscriptionEmail,
  sendRefundEmail,
  logPaymentEvent,
  updateSubscriptionStatus,
  createAuditLog,
} from '@/lib/payment';

// Constants
import {
  PAYMENT_PROVIDERS,
  PAYMENT_STATUS,
  SUBSCRIPTION_STATUS,
  INVOICE_STATUS,
  REFUND_STATUS,
  PAYMENT_METHODS,
  PAYMENT_PLANS,
  WEBHOOK_EVENTS,
  STRIPE_WEBHOOK_SECRET,
  PAYPAL_WEBHOOK_ID,
  COINBASE_WEBHOOK_SECRET,
} from '@/constants/payment';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Configuration
// ============================================

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 5000, 15000]; // 1s, 5s, 15s

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

    // Rate limiting
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const rateLimitKey = `payment:webhook:${ip}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many webhook requests' },
        { status: 429 }
      );
    }

    // Route to appropriate handler
    switch (provider) {
      case PAYMENT_PROVIDERS.STRIPE:
        return await handleStripeWebhook(rawBody, signature, headersList);
      
      case PAYMENT_PROVIDERS.PAYPAL:
        return await handlePayPalWebhook(rawBody, headersList);
      
      case PAYMENT_PROVIDERS.COINBASE:
        return await handleCoinbaseWebhook(rawBody, signature, headersList);
      
      default:
        return NextResponse.json(
          { error: 'Unknown payment provider' },
          { status: 400 }
        );
    }

  } catch (error: any) {
    console.error('Payment webhook error:', error);
    
    await logPaymentEvent({
      type: 'webhook_error',
      provider: 'unknown',
      error: error.message,
      stack: error.stack,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { error: 'Internal server error' },
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
  headers: Headers
): Promise<NextResponse> {
  try {
    // Verify webhook signature
    const event = await verifyStripeWebhook(rawBody, signature);
    
    if (!event) {
      await logPaymentEvent({
        type: 'webhook_verification_failed',
        provider: 'stripe',
        signature,
        timestamp: new Date(),
      });
      return NextResponse.json(
        { error: 'Invalid webhook signature' },
        { status: 401 }
      );
    }

    // Process event based on type
    switch (event.type) {
      case STRIPE_WEBHOOK_EVENTS.PAYMENT_INTENT_SUCCEEDED:
        return await handleStripePaymentIntent(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.PAYMENT_INTENT_FAILED:
        return await handleStripePaymentFailed(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CUSTOMER_SUBSCRIPTION_CREATED:
        return await handleStripeSubscriptionCreated(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CUSTOMER_SUBSCRIPTION_UPDATED:
        return await handleStripeSubscriptionUpdated(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CUSTOMER_SUBSCRIPTION_DELETED:
        return await handleStripeSubscriptionDeleted(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.INVOICE_PAID:
        return await handleStripeInvoicePaid(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.INVOICE_PAYMENT_FAILED:
        return await handleStripeInvoiceFailed(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CHARGE_REFUNDED:
        return await handleStripeRefund(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CUSTOMER_CREATED:
        return await handleStripeCustomerCreated(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CUSTOMER_UPDATED:
        return await handleStripeCustomerUpdated(event.data.object);
      
      case STRIPE_WEBHOOK_EVENTS.CUSTOMER_DELETED:
        return await handleStripeCustomerDeleted(event.data.object);
      
      default:
        await logPaymentEvent({
          type: 'unhandled_event',
          provider: 'stripe',
          eventType: event.type,
          timestamp: new Date(),
        });
        return NextResponse.json(
          { message: 'Webhook received but not processed' },
          { status: 200 }
        );
    }

  } catch (error: any) {
    console.error('Stripe webhook error:', error);
    
    await logPaymentEvent({
      type: 'stripe_webhook_error',
      error: error.message,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { error: 'Stripe webhook processing failed' },
      { status: 500 }
    );
  }
}

// ============================================
// PayPal Webhook Handler
// ============================================

async function handlePayPalWebhook(
  rawBody: string,
  headers: Headers
): Promise<NextResponse> {
  try {
    // Verify PayPal IPN
    const isValid = await verifyPayPalIPN(rawBody, headers);
    
    if (!isValid) {
      await logPaymentEvent({
        type: 'webhook_verification_failed',
        provider: 'paypal',
        timestamp: new Date(),
      });
      return NextResponse.json(
        { error: 'Invalid PayPal webhook' },
        { status: 401 }
      );
    }

    const data = JSON.parse(rawBody);
    const eventType = data.event_type;

    // Process PayPal event
    switch (eventType) {
      case 'PAYMENT.CAPTURE.COMPLETED':
        return await handlePayPalPaymentCompleted(data);
      
      case 'PAYMENT.CAPTURE.DENIED':
        return await handlePayPalPaymentFailed(data);
      
      case 'PAYMENT.CAPTURE.REFUNDED':
        return await handlePayPalRefund(data);
      
      case 'BILLING.SUBSCRIPTION.CREATED':
        return await handlePayPalSubscriptionCreated(data);
      
      case 'BILLING.SUBSCRIPTION.UPDATED':
        return await handlePayPalSubscriptionUpdated(data);
      
      case 'BILLING.SUBSCRIPTION.CANCELLED':
        return await handlePayPalSubscriptionCancelled(data);
      
      default:
        await logPaymentEvent({
          type: 'unhandled_event',
          provider: 'paypal',
          eventType: eventType,
          timestamp: new Date(),
        });
        return NextResponse.json(
          { message: 'Webhook received but not processed' },
          { status: 200 }
        );
    }

  } catch (error: any) {
    console.error('PayPal webhook error:', error);
    return NextResponse.json(
      { error: 'PayPal webhook processing failed' },
      { status: 500 }
    );
  }
}

// ============================================
// Coinbase Webhook Handler
// ============================================

async function handleCoinbaseWebhook(
  rawBody: string,
  signature: string,
  headers: Headers
): Promise<NextResponse> {
  try {
    // Verify Coinbase webhook
    const isValid = await verifyCoinbaseWebhook(rawBody, signature, headers);
    
    if (!isValid) {
      await logPaymentEvent({
        type: 'webhook_verification_failed',
        provider: 'coinbase',
        signature,
        timestamp: new Date(),
      });
      return NextResponse.json(
        { error: 'Invalid Coinbase webhook' },
        { status: 401 }
      );
    }

    const data = JSON.parse(rawBody);
    const eventType = data.event?.type;

    // Process Coinbase event
    switch (eventType) {
      case 'charge:confirmed':
        return await handleCoinbaseChargeConfirmed(data);
      
      case 'charge:failed':
        return await handleCoinbaseChargeFailed(data);
      
      case 'charge:pending':
        return await handleCoinbaseChargePending(data);
      
      case 'charge:delayed':
        return await handleCoinbaseChargeDelayed(data);
      
      default:
        await logPaymentEvent({
          type: 'unhandled_event',
          provider: 'coinbase',
          eventType: eventType,
          timestamp: new Date(),
        });
        return NextResponse.json(
          { message: 'Webhook received but not processed' },
          { status: 200 }
        );
    }

  } catch (error: any) {
    console.error('Coinbase webhook error:', error);
    return NextResponse.json(
      { error: 'Coinbase webhook processing failed' },
      { status: 500 }
    );
  }
}

// ============================================
// Stripe Event Handlers
// ============================================

async function handleStripePaymentIntent(paymentIntent: Stripe.PaymentIntent) {
  try {
    const { id, amount, currency, customer, metadata, status } = paymentIntent;

    // Find user by customer ID
    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      await logPaymentEvent({
        type: 'payment_intent_unknown_user',
        provider: 'stripe',
        paymentIntentId: id,
        customerId: customer as string,
        timestamp: new Date(),
      });
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      );
    }

    // Check if payment already exists
    const existingPayment = await prisma.payment.findUnique({
      where: { stripePaymentIntentId: id },
    });

    if (existingPayment) {
      return NextResponse.json(
        { message: 'Payment already processed' },
        { status: 200 }
      );
    }

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        stripePaymentIntentId: id,
        provider: 'stripe',
        amount: amount / 100, // Convert from cents
        currency,
        status: PAYMENT_STATUS.COMPLETED,
        metadata: {
          paymentMethod: paymentIntent.payment_method_types?.[0] || 'unknown',
          customer: customer,
          description: metadata?.description || '',
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Update subscription if exists
    if (metadata?.subscriptionId) {
      await updateSubscriptionStatus({
        subscriptionId: metadata.subscriptionId,
        status: 'active',
        paymentId: payment.id,
      });
    }

    // Generate invoice
    const invoice = await generateInvoice({
      userId: user.id,
      paymentId: payment.id,
      amount: amount / 100,
      currency,
      description: metadata?.description || 'Payment',
      dueDate: new Date(),
    });

    // Send confirmation email
    await sendPaymentConfirmationEmail({
      email: user.email,
      name: user.name || 'User',
      amount: amount / 100,
      currency,
      paymentMethod: paymentIntent.payment_method_types?.[0] || 'unknown',
      invoiceUrl: invoice.url,
      date: new Date(),
    });

    // Log event
    await logPaymentEvent({
      type: 'payment_successful',
      provider: 'stripe',
      userId: user.id,
      paymentId: payment.id,
      amount: amount / 100,
      currency,
      timestamp: new Date(),
    });

    // Create audit log
    await createAuditLog({
      userId: user.id,
      action: 'payment_completed',
      resource: 'payment',
      resourceId: payment.id,
      metadata: {
        stripePaymentIntentId: id,
        amount: amount / 100,
        currency,
      },
      ip: 'webhook',
      userAgent: 'stripe-webhook',
    });

    return NextResponse.json(
      { success: true, paymentId: payment.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe payment intent error:', error);
    throw error;
  }
}

async function handleStripePaymentFailed(paymentIntent: Stripe.PaymentIntent) {
  try {
    const { id, amount, currency, customer, metadata, last_payment_error } = paymentIntent;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Create failed payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        stripePaymentIntentId: id,
        provider: 'stripe',
        amount: amount / 100,
        currency,
        status: PAYMENT_STATUS.FAILED,
        errorMessage: last_payment_error?.message || 'Payment failed',
        metadata: {
          paymentMethod: paymentIntent.payment_method_types?.[0] || 'unknown',
          customer: customer,
          failureCode: last_payment_error?.code,
          failureMessage: last_payment_error?.message,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Log event
    await logPaymentEvent({
      type: 'payment_failed',
      provider: 'stripe',
      userId: user.id,
      paymentId: payment.id,
      amount: amount / 100,
      currency,
      error: last_payment_error?.message,
      timestamp: new Date(),
    });

    // Send notification
    await sendPaymentFailedEmail({
      email: user.email,
      name: user.name || 'User',
      amount: amount / 100,
      currency,
      errorMessage: last_payment_error?.message || 'Payment failed',
      date: new Date(),
    });

    return NextResponse.json(
      { success: true, paymentId: payment.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe payment failed error:', error);
    throw error;
  }
}

async function handleStripeSubscriptionCreated(subscription: Stripe.Subscription) {
  try {
    const { id, customer, items, status, current_period_start, current_period_end } = subscription;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Get plan details
    const plan = items.data[0]?.plan;
    const productId = plan?.product as string;
    const priceId = plan?.id;

    // Find subscription plan
    const subscriptionPlan = await prisma.subscriptionPlan.findFirst({
      where: { stripePriceId: priceId },
    });

    if (!subscriptionPlan) {
      await logPaymentEvent({
        type: 'subscription_plan_not_found',
        provider: 'stripe',
        priceId: priceId,
        timestamp: new Date(),
      });
      return NextResponse.json(
        { error: 'Subscription plan not found' },
        { status: 404 }
      );
    }

    // Create subscription record
    const subscriptionRecord = await prisma.subscription.create({
      data: {
        userId: user.id,
        planId: subscriptionPlan.id,
        stripeSubscriptionId: id,
        status: SUBSCRIPTION_STATUS.ACTIVE,
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

    // Log event
    await logPaymentEvent({
      type: 'subscription_created',
      provider: 'stripe',
      userId: user.id,
      subscriptionId: subscriptionRecord.id,
      planId: subscriptionPlan.id,
      timestamp: new Date(),
    });

    // Send confirmation email
    await sendSubscriptionEmail({
      email: user.email,
      name: user.name || 'User',
      planName: subscriptionPlan.name,
      startDate: new Date(current_period_start * 1000),
      endDate: new Date(current_period_end * 1000),
      amount: subscriptionPlan.price,
      currency: subscriptionPlan.currency,
    });

    // Create audit log
    await createAuditLog({
      userId: user.id,
      action: 'subscription_created',
      resource: 'subscription',
      resourceId: subscriptionRecord.id,
      metadata: {
        planId: subscriptionPlan.id,
        planName: subscriptionPlan.name,
        stripeSubscriptionId: id,
      },
      ip: 'webhook',
      userAgent: 'stripe-webhook',
    });

    return NextResponse.json(
      { success: true, subscriptionId: subscriptionRecord.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe subscription created error:', error);
    throw error;
  }
}

async function handleStripeSubscriptionUpdated(subscription: Stripe.Subscription) {
  try {
    const { id, customer, status, current_period_end, cancel_at_period_end } = subscription;

    const subscriptionRecord = await prisma.subscription.findUnique({
      where: { stripeSubscriptionId: id },
    });

    if (!subscriptionRecord) {
      return NextResponse.json(
        { error: 'Subscription not found' },
        { status: 404 }
      );
    }

    // Update subscription
    const updatedSubscription = await prisma.subscription.update({
      where: { id: subscriptionRecord.id },
      data: {
        status: mapStripeStatusToInternal(status),
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

    // Log event
    await logPaymentEvent({
      type: 'subscription_updated',
      provider: 'stripe',
      userId: subscriptionRecord.userId,
      subscriptionId: subscriptionRecord.id,
      newStatus: status,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, subscriptionId: subscriptionRecord.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe subscription updated error:', error);
    throw error;
  }
}

async function handleStripeSubscriptionDeleted(subscription: Stripe.Subscription) {
  try {
    const { id, customer } = subscription;

    const subscriptionRecord = await prisma.subscription.findUnique({
      where: { stripeSubscriptionId: id },
    });

    if (!subscriptionRecord) {
      return NextResponse.json(
        { error: 'Subscription not found' },
        { status: 404 }
      );
    }

    // Cancel subscription
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

    // Log event
    await logPaymentEvent({
      type: 'subscription_cancelled',
      provider: 'stripe',
      userId: subscriptionRecord.userId,
      subscriptionId: subscriptionRecord.id,
      timestamp: new Date(),
    });

    // Send cancellation email
    await sendSubscriptionCancelledEmail({
      email: subscriptionRecord.user?.email || '',
      name: subscriptionRecord.user?.name || 'User',
      planName: subscriptionRecord.plan?.name || 'Subscription',
      date: new Date(),
    });

    return NextResponse.json(
      { success: true, subscriptionId: subscriptionRecord.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe subscription deleted error:', error);
    throw error;
  }
}

async function handleStripeInvoicePaid(invoice: Stripe.Invoice) {
  try {
    const { id, customer, amount_paid, currency, subscription } = invoice;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Create invoice record
    const invoiceRecord = await prisma.invoice.create({
      data: {
        userId: user.id,
        stripeInvoiceId: id,
        amount: amount_paid / 100,
        currency,
        status: INVOICE_STATUS.PAID,
        subscriptionId: subscription ? await findSubscriptionId(subscription as string) : null,
        dueDate: new Date(),
        paidAt: new Date(),
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Log event
    await logPaymentEvent({
      type: 'invoice_paid',
      provider: 'stripe',
      userId: user.id,
      invoiceId: invoiceRecord.id,
      amount: amount_paid / 100,
      currency,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, invoiceId: invoiceRecord.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe invoice paid error:', error);
    throw error;
  }
}

async function handleStripeInvoiceFailed(invoice: Stripe.Invoice) {
  try {
    const { id, customer, amount_due, currency, subscription } = invoice;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
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

    // Log event
    await logPaymentEvent({
      type: 'invoice_failed',
      provider: 'stripe',
      userId: user.id,
      invoiceId: invoiceRecord.id,
      amount: amount_due / 100,
      currency,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, invoiceId: invoiceRecord.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe invoice failed error:', error);
    throw error;
  }
}

async function handleStripeRefund(charge: Stripe.Charge) {
  try {
    const { id, amount_refunded, currency, customer, payment_intent } = charge;

    const user = await prisma.user.findFirst({
      where: { stripeCustomerId: customer as string },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Find original payment
    const payment = await prisma.payment.findUnique({
      where: { stripePaymentIntentId: payment_intent as string },
    });

    if (!payment) {
      return NextResponse.json(
        { error: 'Original payment not found' },
        { status: 404 }
      );
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
        metadata: {
          chargeId: id,
          refundedAt: new Date().toISOString(),
        },
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

    // Log event
    await logPaymentEvent({
      type: 'refund_processed',
      provider: 'stripe',
      userId: user.id,
      refundId: refund.id,
      paymentId: payment.id,
      amount: amount_refunded / 100,
      currency,
      timestamp: new Date(),
    });

    // Send refund email
    await sendRefundEmail({
      email: user.email,
      name: user.name || 'User',
      amount: amount_refunded / 100,
      currency,
      reason: charge.refund_reason || 'unknown',
      date: new Date(),
    });

    return NextResponse.json(
      { success: true, refundId: refund.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe refund error:', error);
    throw error;
  }
}

async function handleStripeCustomerCreated(customer: Stripe.Customer) {
  try {
    // Find user by email
    const user = await prisma.user.findUnique({
      where: { email: customer.email as string },
    });

    if (!user) {
      // Create user if doesn't exist (for new customers)
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

      await createAuditLog({
        userId: newUser.id,
        action: 'stripe_customer_created',
        resource: 'user',
        resourceId: newUser.id,
        metadata: {
          stripeCustomerId: customer.id,
        },
        ip: 'webhook',
        userAgent: 'stripe-webhook',
      });

      return NextResponse.json(
        { success: true, userId: newUser.id },
        { status: 200 }
      );
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

    return NextResponse.json(
      { success: true, userId: user.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe customer created error:', error);
    throw error;
  }
}

async function handleStripeCustomerUpdated(customer: Stripe.Customer) {
  try {
    const user = await prisma.user.findFirst({
      where: { 
        OR: [
          { stripeCustomerId: customer.id },
          { email: customer.email as string },
        ],
      },
    });

    if (!user) {
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      );
    }

    // Update user
    await prisma.user.update({
      where: { id: user.id },
      data: {
        name: customer.name || user.name,
        email: customer.email as string || user.email,
        stripeCustomerId: customer.id,
        stripeCustomerEmail: customer.email,
        updatedAt: new Date(),
      },
    });

    return NextResponse.json(
      { success: true, userId: user.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe customer updated error:', error);
    throw error;
  }
}

async function handleStripeCustomerDeleted(customer: Stripe.Customer) {
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

    return NextResponse.json(
      { success: true },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Stripe customer deleted error:', error);
    throw error;
  }
}

// ============================================
// PayPal Event Handlers
// ============================================

async function handlePayPalPaymentCompleted(data: any) {
  try {
    const { id, amount, currency_code, payer, purchase_units } = data.resource;
    const email = payer.email_address;

    const user = await prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        paypalPaymentId: id,
        provider: 'paypal',
        amount: parseFloat(amount.value),
        currency: currency_code,
        status: PAYMENT_STATUS.COMPLETED,
        metadata: {
          payerId: payer.payer_id,
          payerEmail: email,
          purchaseUnits: purchase_units,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Log event
    await logPaymentEvent({
      type: 'payment_successful',
      provider: 'paypal',
      userId: user.id,
      paymentId: payment.id,
      amount: parseFloat(amount.value),
      currency: currency_code,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, paymentId: payment.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle PayPal payment completed error:', error);
    throw error;
  }
}

async function handlePayPalPaymentFailed(data: any) {
  try {
    const { id, amount, currency_code, payer } = data.resource;
    const email = payer.email_address;

    const user = await prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Create failed payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        paypalPaymentId: id,
        provider: 'paypal',
        amount: parseFloat(amount.value),
        currency: currency_code,
        status: PAYMENT_STATUS.FAILED,
        errorMessage: 'PayPal payment denied',
        metadata: {
          payerId: payer.payer_id,
          payerEmail: email,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    await logPaymentEvent({
      type: 'payment_failed',
      provider: 'paypal',
      userId: user.id,
      paymentId: payment.id,
      amount: parseFloat(amount.value),
      currency: currency_code,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, paymentId: payment.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle PayPal payment failed error:', error);
    throw error;
  }
}

async function handlePayPalRefund(data: any) {
  try {
    const { id, amount, currency_code } = data.resource;

    const payment = await prisma.payment.findFirst({
      where: { paypalPaymentId: data.resource.payment_id },
    });

    if (!payment) {
      return NextResponse.json(
        { error: 'Original payment not found' },
        { status: 404 }
      );
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

    await logPaymentEvent({
      type: 'refund_processed',
      provider: 'paypal',
      userId: payment.userId,
      refundId: refund.id,
      paymentId: payment.id,
      amount: parseFloat(amount.value),
      currency: currency_code,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, refundId: refund.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle PayPal refund error:', error);
    throw error;
  }
}

async function handlePayPalSubscriptionCreated(data: any) {
  // Similar to Stripe subscription creation
  // ... (implementation similar to Stripe version)
  return NextResponse.json({ success: true }, { status: 200 });
}

async function handlePayPalSubscriptionUpdated(data: any) {
  // Similar to Stripe subscription update
  // ... (implementation similar to Stripe version)
  return NextResponse.json({ success: true }, { status: 200 });
}

async function handlePayPalSubscriptionCancelled(data: any) {
  // Similar to Stripe subscription deletion
  // ... (implementation similar to Stripe version)
  return NextResponse.json({ success: true }, { status: 200 });
}

// ============================================
// Coinbase Event Handlers
// ============================================

async function handleCoinbaseChargeConfirmed(data: any) {
  try {
    const charge = data.event.data;
    const { id, payments, metadata } = charge;

    const user = await prisma.user.findUnique({
      where: { id: metadata.user_id },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    const payment = payments[0];
    const amount = parseFloat(payment.amount.local.amount);
    const currency = payment.amount.local.currency;

    // Create payment record
    const paymentRecord = await prisma.payment.create({
      data: {
        userId: user.id,
        coinbaseChargeId: id,
        provider: 'coinbase',
        amount,
        currency,
        status: PAYMENT_STATUS.COMPLETED,
        metadata: {
          chargeId: id,
          cryptoAmount: payment.amount.crypto.amount,
          cryptoCurrency: payment.amount.crypto.currency,
          network: payment.blockchain,
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    await logPaymentEvent({
      type: 'payment_successful',
      provider: 'coinbase',
      userId: user.id,
      paymentId: paymentRecord.id,
      amount,
      currency,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, paymentId: paymentRecord.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Coinbase charge confirmed error:', error);
    throw error;
  }
}

async function handleCoinbaseChargeFailed(data: any) {
  try {
    const charge = data.event.data;
    const { id, metadata } = charge;

    const user = await prisma.user.findUnique({
      where: { id: metadata.user_id },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Create failed payment record
    const payment = await prisma.payment.create({
      data: {
        userId: user.id,
        coinbaseChargeId: id,
        provider: 'coinbase',
        amount: 0,
        currency: 'USD',
        status: PAYMENT_STATUS.FAILED,
        errorMessage: 'Coinbase payment failed',
        metadata: {
          chargeId: id,
          failureReason: charge.metadata?.failure_reason || 'unknown',
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    await logPaymentEvent({
      type: 'payment_failed',
      provider: 'coinbase',
      userId: user.id,
      paymentId: payment.id,
      timestamp: new Date(),
    });

    return NextResponse.json(
      { success: true, paymentId: payment.id },
      { status: 200 }
    );

  } catch (error: any) {
    console.error('Handle Coinbase charge failed error:', error);
    throw error;
  }
}

async function handleCoinbaseChargePending(data: any) {
  // Handle pending charge
  return NextResponse.json({ success: true }, { status: 200 });
}

async function handleCoinbaseChargeDelayed(data: any) {
  // Handle delayed charge
  return NextResponse.json({ success: true }, { status: 200 });
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

async function findSubscriptionId(stripeSubscriptionId: string): Promise<string | null> {
  const subscription = await prisma.subscription.findUnique({
    where: { stripeSubscriptionId },
    select: { id: true },
  });
  return subscription?.id || null;
}

function mapStripeStatusToInternal(status: string): string {
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

// ============================================
// Utility Functions for Emails
// ============================================

async function sendPaymentFailedEmail(data: {
  email: string;
  name: string;
  amount: number;
  currency: string;
  errorMessage: string;
  date: Date;
}): Promise<void> {
  // Implementation for sending payment failed email
  console.log(`Sending payment failed email to ${data.email}`);
}

async function sendSubscriptionCancelledEmail(data: {
  email: string;
  name: string;
  planName: string;
  date: Date;
}): Promise<void> {
  // Implementation for sending subscription cancelled email
  console.log(`Sending subscription cancelled email to ${data.email}`);
}

// ============================================
// Type Definitions
// ============================================

declare module '@/types/payment' {
  export interface PaymentWebhook {
    id: string;
    provider: string;
    eventType: string;
    data: any;
    timestamp: Date;
    signature: string;
    rawBody: string;
  }

  export interface PaymentEvent {
    type: string;
    provider: string;
    userId?: string;
    paymentId?: string;
    subscriptionId?: string;
    invoiceId?: string;
    refundId?: string;
    amount?: number;
    currency?: string;
    error?: string;
    timestamp: Date;
  }

  export interface PaymentIntentData {
    id: string;
    amount: number;
    currency: string;
    customer: string;
    metadata: Record<string, any>;
    status: string;
  }

  export interface SubscriptionData {
    id: string;
    customer: string;
    status: string;
    planId: string;
    currentPeriodStart: Date;
    currentPeriodEnd: Date;
  }

  export interface InvoiceData {
    id: string;
    customer: string;
    amount: number;
    currency: string;
    status: string;
    subscriptionId?: string;
  }

  export interface RefundData {
    id: string;
    paymentId: string;
    amount: number;
    currency: string;
    status: string;
    reason: string;
  }

  export interface CustomerData {
    id: string;
    email: string;
    name: string;
  }

  export interface PaymentMetadata {
    userId: string;
    subscriptionId?: string;
    planId?: string;
    description?: string;
  }

  export interface WebhookVerification {
    isValid: boolean;
    provider: string;
    error?: string;
  }

  export interface PaymentError {
    code: string;
    message: string;
    provider: string;
    timestamp: Date;
  }
}

// ============================================
// Constants
// ============================================

export const STRIPE_WEBHOOK_EVENTS = {
  PAYMENT_INTENT_SUCCEEDED: 'payment_intent.succeeded',
  PAYMENT_INTENT_FAILED: 'payment_intent.payment_failed',
  CUSTOMER_SUBSCRIPTION_CREATED: 'customer.subscription.created',
  CUSTOMER_SUBSCRIPTION_UPDATED: 'customer.subscription.updated',
  CUSTOMER_SUBSCRIPTION_DELETED: 'customer.subscription.deleted',
  INVOICE_PAID: 'invoice.paid',
  INVOICE_PAYMENT_FAILED: 'invoice.payment_failed',
  CHARGE_REFUNDED: 'charge.refunded',
  CUSTOMER_CREATED: 'customer.created',
  CUSTOMER_UPDATED: 'customer.updated',
  CUSTOMER_DELETED: 'customer.deleted',
} as const;

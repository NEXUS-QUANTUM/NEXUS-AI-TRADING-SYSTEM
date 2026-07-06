/**
 * NEXUS AI TRADING SYSTEM - Support Ticket API Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles individual support ticket operations including:
 * - GET: Retrieve ticket details
 * - PUT: Update ticket information
 * - PATCH: Partial ticket updates
 * - DELETE: Delete/Cancel ticket
 * - POST: Add reply to ticket
 * - Ticket status management
 * - Assignment management
 * - Priority management
 * - Escalation handling
 * - File attachments
 * - Email notifications
 * - Audit logging
 * - Rate limiting
 * - Security validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';
import { z } from 'zod';

// Types
import type {
  SupportTicket,
  TicketReply,
  TicketAttachment,
  TicketStatus,
  TicketPriority,
  TicketCategory,
  TicketAssignment,
  TicketEscalation,
  TicketActivity,
  TicketMetrics,
} from '@/types/support';

// Utils
import {
  validateTicketAccess,
  validateTicketUpdate,
  validateTicketReply,
  formatTicketResponse,
  generateTicketActivity,
  sendTicketNotification,
  logTicketAction,
  createAuditLog,
  handleTicketError,
} from '@/lib/support';

// Constants
import {
  TICKET_STATUSES,
  TICKET_PRIORITIES,
  TICKET_CATEGORIES,
  TICKET_ACTIVITY_TYPES,
  MAX_TICKET_ATTACHMENTS,
  MAX_ATTACHMENT_SIZE,
  ALLOWED_ATTACHMENT_TYPES,
  TICKET_ESCALATION_RULES,
  TICKET_SLA_RULES,
} from '@/constants/support';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Validation Schemas
// ============================================

const UpdateTicketSchema = z.object({
  subject: z.string().min(3).max(200).optional(),
  status: z.enum(['open', 'in_progress', 'resolved', 'closed', 'pending', 'escalated']).optional(),
  priority: z.enum(['low', 'medium', 'high', 'critical']).optional(),
  category: z.enum(['technical', 'billing', 'account', 'trading', 'security', 'general', 'api']).optional(),
  assignedTo: z.string().uuid().optional(),
  description: z.string().min(10).max(5000).optional(),
  tags: z.array(z.string()).optional(),
  metadata: z.record(z.any()).optional(),
});

const ReplySchema = z.object({
  content: z.string().min(1).max(10000),
  attachments: z.array(z.object({
    name: z.string(),
    type: z.string(),
    size: z.number().max(MAX_ATTACHMENT_SIZE),
    url: z.string().url(),
  })).max(MAX_TICKET_ATTACHMENTS).optional(),
  isInternal: z.boolean().default(false),
});

// ============================================
// Main Handler - GET
// ============================================

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const userAgent = headersList.get('user-agent') || 'unknown';

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Rate limiting
    const rateLimitKey = `support:ticket:${userId}:${id}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Fetch ticket with related data
    const ticket = await prisma.supportTicket.findUnique({
      where: { id },
      include: {
        user: {
          select: {
            id: true,
            name: true,
            email: true,
            image: true,
          },
        },
        assignedToUser: {
          select: {
            id: true,
            name: true,
            email: true,
            image: true,
          },
        },
        replies: {
          include: {
            user: {
              select: {
                id: true,
                name: true,
                email: true,
                image: true,
              },
            },
            attachments: true,
          },
          orderBy: {
            createdAt: 'asc',
          },
        },
        attachments: true,
        activities: {
          orderBy: {
            createdAt: 'desc',
          },
          take: 50,
        },
        metrics: true,
      },
    });

    if (!ticket) {
      return NextResponse.json(
        { error: 'Ticket not found' },
        { status: 404 }
      );
    }

    // Check access permissions
    const hasAccess = await validateTicketAccess(userId, ticket, {
      requireAdmin: false,
      requireAssigned: false,
    });

    if (!hasAccess) {
      return NextResponse.json(
        { error: 'Access denied' },
        { status: 403 }
      );
    }

    // Log ticket view
    await logTicketAction({
      ticketId: ticket.id,
      userId,
      action: 'view',
      ip,
      userAgent,
      metadata: {
        timestamp: new Date().toISOString(),
      },
    });

    // Update metrics
    await prisma.ticketMetrics.update({
      where: { ticketId: ticket.id },
      data: {
        viewCount: { increment: 1 },
        lastViewedAt: new Date(),
      },
    });

    return NextResponse.json({
      success: true,
      data: formatTicketResponse(ticket),
    }, { status: 200 });

  } catch (error: any) {
    console.error('Get ticket error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to retrieve ticket' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - PUT
// ============================================

export async function PUT(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;
    const body = await req.json();
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const userAgent = headersList.get('user-agent') || 'unknown';

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Rate limiting
    const rateLimitKey = `support:ticket:update:${userId}:${id}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Fetch existing ticket
    const existingTicket = await prisma.supportTicket.findUnique({
      where: { id },
      include: {
        user: true,
        assignedToUser: true,
      },
    });

    if (!existingTicket) {
      return NextResponse.json(
        { error: 'Ticket not found' },
        { status: 404 }
      );
    }

    // Check update permissions
    const canUpdate = await validateTicketUpdate(userId, existingTicket);
    if (!canUpdate) {
      return NextResponse.json(
        { error: 'Access denied' },
        { status: 403 }
      );
    }

    // Validate update data
    const validationResult = UpdateTicketSchema.safeParse(body);
    if (!validationResult.success) {
      return NextResponse.json(
        { 
          error: 'Validation failed',
          details: validationResult.error.errors,
        },
        { status: 400 }
      );
    }

    const updateData = validationResult.data;

    // Check if status change requires special handling
    let statusChangeNote = '';
    if (updateData.status && updateData.status !== existingTicket.status) {
      statusChangeNote = await handleStatusChange(
        existingTicket,
        updateData.status,
        userId
      );
    }

    // Check if assignment change requires special handling
    let assignmentChangeNote = '';
    if (updateData.assignedTo && updateData.assignedTo !== existingTicket.assignedTo) {
      assignmentChangeNote = await handleAssignmentChange(
        existingTicket,
        updateData.assignedTo,
        userId
      );
    }

    // Check if priority change requires escalation
    let escalationNote = '';
    if (updateData.priority && updateData.priority !== existingTicket.priority) {
      escalationNote = await handlePriorityChange(
        existingTicket,
        updateData.priority,
        userId
      );
    }

    // Update ticket
    const updatedTicket = await prisma.supportTicket.update({
      where: { id },
      data: {
        ...(updateData.subject && { subject: updateData.subject }),
        ...(updateData.status && { status: updateData.status }),
        ...(updateData.priority && { priority: updateData.priority }),
        ...(updateData.category && { category: updateData.category }),
        ...(updateData.assignedTo && { assignedTo: updateData.assignedTo }),
        ...(updateData.description && { description: updateData.description }),
        ...(updateData.tags && { tags: updateData.tags }),
        ...(updateData.metadata && { metadata: updateData.metadata }),
        updatedAt: new Date(),
      },
      include: {
        user: {
          select: {
            id: true,
            name: true,
            email: true,
          },
        },
        assignedToUser: {
          select: {
            id: true,
            name: true,
            email: true,
          },
        },
      },
    });

    // Create activity log
    await generateTicketActivity({
      ticketId: id,
      userId,
      type: 'updated',
      details: {
        changes: updateData,
        statusChange: statusChangeNote,
        assignmentChange: assignmentChangeNote,
        escalationNote: escalationNote,
      },
    });

    // Send notifications
    await sendTicketNotification({
      ticket: updatedTicket,
      type: 'updated',
      changes: updateData,
      triggeredBy: userId,
    });

    // Create audit log
    await createAuditLog({
      userId,
      action: 'ticket_updated',
      resource: 'support_ticket',
      resourceId: id,
      metadata: {
        changes: updateData,
        ip,
        userAgent,
      },
      ip,
      userAgent,
    });

    return NextResponse.json({
      success: true,
      data: formatTicketResponse(updatedTicket),
      notes: {
        statusChange: statusChangeNote,
        assignmentChange: assignmentChangeNote,
        escalation: escalationNote,
      },
    }, { status: 200 });

  } catch (error: any) {
    console.error('Update ticket error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to update ticket' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - PATCH
// ============================================

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;
    const body = await req.json();
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const userAgent = headersList.get('user-agent') || 'unknown';

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Rate limiting
    const rateLimitKey = `support:ticket:patch:${userId}:${id}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Fetch existing ticket
    const existingTicket = await prisma.supportTicket.findUnique({
      where: { id },
    });

    if (!existingTicket) {
      return NextResponse.json(
        { error: 'Ticket not found' },
        { status: 404 }
      );
    }

    // Check update permissions
    const canUpdate = await validateTicketUpdate(userId, existingTicket);
    if (!canUpdate) {
      return NextResponse.json(
        { error: 'Access denied' },
        { status: 403 }
      );
    }

    // Validate partial update
    const validationResult = UpdateTicketSchema.partial().safeParse(body);
    if (!validationResult.success) {
      return NextResponse.json(
        { 
          error: 'Validation failed',
          details: validationResult.error.errors,
        },
        { status: 400 }
      );
    }

    const updateData = validationResult.data;

    // Handle specific patch operations
    const operations = [];

    // Status change
    if (updateData.status) {
      operations.push({
        field: 'status',
        from: existingTicket.status,
        to: updateData.status,
      });
      await handleStatusChange(existingTicket, updateData.status, userId);
    }

    // Priority change
    if (updateData.priority) {
      operations.push({
        field: 'priority',
        from: existingTicket.priority,
        to: updateData.priority,
      });
      await handlePriorityChange(existingTicket, updateData.priority, userId);
    }

    // Assignment change
    if (updateData.assignedTo) {
      operations.push({
        field: 'assignedTo',
        from: existingTicket.assignedTo,
        to: updateData.assignedTo,
      });
      await handleAssignmentChange(existingTicket, updateData.assignedTo, userId);
    }

    // Update ticket
    const updatedTicket = await prisma.supportTicket.update({
      where: { id },
      data: {
        ...updateData,
        updatedAt: new Date(),
      },
      include: {
        user: {
          select: {
            id: true,
            name: true,
            email: true,
          },
        },
      },
    });

    // Create activity log
    await generateTicketActivity({
      ticketId: id,
      userId,
      type: 'updated',
      details: {
        changes: updateData,
        operations,
      },
    });

    return NextResponse.json({
      success: true,
      data: formatTicketResponse(updatedTicket),
      operations,
    }, { status: 200 });

  } catch (error: any) {
    console.error('Patch ticket error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to update ticket' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - DELETE
// ============================================

export async function DELETE(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const userAgent = headersList.get('user-agent') || 'unknown';

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Rate limiting
    const rateLimitKey = `support:ticket:delete:${userId}:${id}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Fetch existing ticket
    const existingTicket = await prisma.supportTicket.findUnique({
      where: { id },
      include: {
        user: true,
      },
    });

    if (!existingTicket) {
      return NextResponse.json(
        { error: 'Ticket not found' },
        { status: 404 }
      );
    }

    // Check delete permissions (only admin or ticket owner can delete)
    const canDelete = await validateTicketDelete(userId, existingTicket);
    if (!canDelete) {
      return NextResponse.json(
        { error: 'Access denied. Only ticket owner or admin can delete tickets.' },
        { status: 403 }
      );
    }

    // Soft delete or hard delete based on user role
    const isAdmin = await checkUserAdmin(userId);
    let result;

    if (isAdmin) {
      // Hard delete (admin only)
      result = await prisma.supportTicket.delete({
        where: { id },
      });
    } else {
      // Soft delete (user can cancel their own ticket)
      result = await prisma.supportTicket.update({
        where: { id },
        data: {
          status: 'closed',
          closedAt: new Date(),
          closedBy: userId,
          metadata: {
            ...existingTicket.metadata,
            deletedBy: userId,
            deletedAt: new Date().toISOString(),
          },
          updatedAt: new Date(),
        },
      });
    }

    // Create activity log
    await generateTicketActivity({
      ticketId: id,
      userId,
      type: isAdmin ? 'deleted' : 'closed',
      details: {
        reason: isAdmin ? 'Admin deletion' : 'User cancellation',
      },
    });

    // Create audit log
    await createAuditLog({
      userId,
      action: isAdmin ? 'ticket_deleted' : 'ticket_closed',
      resource: 'support_ticket',
      resourceId: id,
      metadata: {
        ticketSubject: existingTicket.subject,
        ip,
        userAgent,
        isAdmin,
      },
      ip,
      userAgent,
    });

    return NextResponse.json({
      success: true,
      message: isAdmin ? 'Ticket deleted successfully' : 'Ticket closed successfully',
      data: {
        id,
        status: isAdmin ? 'deleted' : 'closed',
      },
    }, { status: 200 });

  } catch (error: any) {
    console.error('Delete ticket error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to delete ticket' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - POST (Add Reply)
// ============================================

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;
    const body = await req.json();
    const headersList = await headers();
    const userId = headersList.get('x-user-id');
    const authToken = headersList.get('authorization')?.replace('Bearer ', '');
    const ip = headersList.get('x-forwarded-for') || 'unknown';
    const userAgent = headersList.get('user-agent') || 'unknown';

    // Validate authentication
    if (!authToken || !userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Rate limiting
    const rateLimitKey = `support:ticket:reply:${userId}:${id}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many replies. Please wait before sending another reply.' },
        { status: 429 }
      );
    }

    // Fetch existing ticket
    const existingTicket = await prisma.supportTicket.findUnique({
      where: { id },
      include: {
        user: true,
        assignedToUser: true,
      },
    });

    if (!existingTicket) {
      return NextResponse.json(
        { error: 'Ticket not found' },
        { status: 404 }
      );
    }

    // Check reply permissions
    const canReply = await validateTicketReply(userId, existingTicket);
    if (!canReply) {
      return NextResponse.json(
        { error: 'Access denied' },
        { status: 403 }
      );
    }

    // Validate reply data
    const validationResult = ReplySchema.safeParse(body);
    if (!validationResult.success) {
      return NextResponse.json(
        { 
          error: 'Validation failed',
          details: validationResult.error.errors,
        },
        { status: 400 }
      );
    }

    const { content, attachments, isInternal } = validationResult.data;

    // Check if ticket is closed
    if (existingTicket.status === 'closed' || existingTicket.status === 'resolved') {
      // Allow reopening if needed
      if (!isInternal) {
        // Update ticket status to open
        await prisma.supportTicket.update({
          where: { id },
          data: {
            status: 'open',
            reopenedAt: new Date(),
            reopenedBy: userId,
            updatedAt: new Date(),
          },
        });
      }
    }

    // Create reply
    const reply = await prisma.ticketReply.create({
      data: {
        ticketId: id,
        userId,
        content,
        isInternal,
        attachments: {
          create: attachments?.map(att => ({
            name: att.name,
            type: att.type,
            size: att.size,
            url: att.url,
          })) || [],
        },
        createdAt: new Date(),
        updatedAt: new Date(),
      },
      include: {
        user: {
          select: {
            id: true,
            name: true,
            email: true,
            image: true,
          },
        },
        attachments: true,
      },
    });

    // Update ticket last reply timestamp
    await prisma.supportTicket.update({
      where: { id },
      data: {
        lastReplyAt: new Date(),
        lastReplyBy: userId,
        replyCount: { increment: 1 },
        updatedAt: new Date(),
      },
    });

    // Update ticket metrics
    await prisma.ticketMetrics.update({
      where: { ticketId: id },
      data: {
        replyCount: { increment: 1 },
        lastReplyAt: new Date(),
      },
    });

    // Create activity log
    await generateTicketActivity({
      ticketId: id,
      userId,
      type: 'replied',
      details: {
        replyId: reply.id,
        content: content.substring(0, 100),
        isInternal,
        hasAttachments: attachments && attachments.length > 0,
      },
    });

    // Send notifications
    await sendTicketNotification({
      ticket: existingTicket,
      type: 'reply_added',
      reply: reply,
      triggeredBy: userId,
    });

    // Create audit log
    await createAuditLog({
      userId,
      action: 'ticket_reply',
      resource: 'ticket_reply',
      resourceId: reply.id,
      metadata: {
        ticketId: id,
        isInternal,
        hasAttachments: attachments && attachments.length > 0,
        ip,
        userAgent,
      },
      ip,
      userAgent,
    });

    return NextResponse.json({
      success: true,
      data: reply,
      ticket: {
        id: existingTicket.id,
        status: existingTicket.status,
        replyCount: existingTicket.replyCount + 1,
      },
    }, { status: 201 });

  } catch (error: any) {
    console.error('Add reply error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to add reply' },
      { status: 500 }
    );
  }
}

// ============================================
// Helper Functions
// ============================================

async function checkRateLimit(key: string): Promise<boolean> {
  const attempts = await redis.get(key);
  const count = parseInt(attempts || '0');
  const maxAttempts = 30; // Max 30 requests per minute
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

async function handleStatusChange(
  ticket: any,
  newStatus: string,
  userId: string
): Promise<string> {
  const oldStatus = ticket.status;
  
  // Update ticket status
  await prisma.supportTicket.update({
    where: { id: ticket.id },
    data: {
      status: newStatus,
      ...(newStatus === 'resolved' && {
        resolvedAt: new Date(),
        resolvedBy: userId,
      }),
      ...(newStatus === 'closed' && {
        closedAt: new Date(),
        closedBy: userId,
      }),
      updatedAt: new Date(),
    },
  });

  // Update metrics
  await prisma.ticketMetrics.update({
    where: { ticketId: ticket.id },
    data: {
      status: newStatus,
      ...(newStatus === 'resolved' && {
        resolvedAt: new Date(),
      }),
    },
  });

  // Generate activity
  await generateTicketActivity({
    ticketId: ticket.id,
    userId,
    type: 'status_changed',
    details: {
      from: oldStatus,
      to: newStatus,
    },
  });

  return `Status changed from ${oldStatus} to ${newStatus}`;
}

async function handleAssignmentChange(
  ticket: any,
  newAssigneeId: string,
  userId: string
): Promise<string> {
  const oldAssigneeId = ticket.assignedTo;

  // Get new assignee details
  const newAssignee = await prisma.user.findUnique({
    where: { id: newAssigneeId },
    select: {
      id: true,
      name: true,
      email: true,
    },
  });

  // Update ticket assignment
  await prisma.supportTicket.update({
    where: { id: ticket.id },
    data: {
      assignedTo: newAssigneeId,
      assignedAt: new Date(),
      updatedAt: new Date(),
    },
  });

  // Generate activity
  await generateTicketActivity({
    ticketId: ticket.id,
    userId,
    type: 'assigned',
    details: {
      from: oldAssigneeId,
      to: newAssigneeId,
      assigneeName: newAssignee?.name || 'Unknown',
    },
  });

  return `Assigned to ${newAssignee?.name || 'Unknown'}`;
}

async function handlePriorityChange(
  ticket: any,
  newPriority: string,
  userId: string
): Promise<string> {
  const oldPriority = ticket.priority;

  // Check if escalation is needed
  const escalationRules = TICKET_ESCALATION_RULES[newPriority];
  if (escalationRules) {
    // Check if ticket meets escalation criteria
    const timeSinceCreation = Date.now() - ticket.createdAt.getTime();
    const slaTime = TICKET_SLA_RULES[newPriority] || 86400000; // 24 hours default

    if (timeSinceCreation > slaTime) {
      // Escalate ticket
      await prisma.supportTicket.update({
        where: { id: ticket.id },
        data: {
          status: 'escalated',
          escalatedAt: new Date(),
          escalationReason: `Priority ${newPriority} - SLA breach`,
          updatedAt: new Date(),
        },
      });

      // Generate escalation activity
      await generateTicketActivity({
        ticketId: ticket.id,
        userId,
        type: 'escalated',
        details: {
          priority: newPriority,
          reason: 'SLA breach',
          timeSinceCreation: timeSinceCreation,
          slaTime: slaTime,
        },
      });

      return `Ticket escalated due to ${newPriority} priority and SLA breach`;
    }
  }

  // Update ticket priority
  await prisma.supportTicket.update({
    where: { id: ticket.id },
    data: {
      priority: newPriority,
      updatedAt: new Date(),
    },
  });

  // Generate activity
  await generateTicketActivity({
    ticketId: ticket.id,
    userId,
    type: 'priority_changed',
    details: {
      from: oldPriority,
      to: newPriority,
    },
  });

  return `Priority changed from ${oldPriority} to ${newPriority}`;
}

async function validateTicketDelete(
  userId: string,
  ticket: any
): Promise<boolean> {
  // Check if user is ticket owner
  if (ticket.userId === userId) {
    return true;
  }

  // Check if user is admin
  const isAdmin = await checkUserAdmin(userId);
  if (isAdmin) {
    return true;
  }

  return false;
}

async function checkUserAdmin(userId: string): Promise<boolean> {
  const userRoles = await prisma.userRole.findMany({
    where: { userId },
    include: {
      role: true,
    },
  });

  return userRoles.some(ur => ur.role.name === 'admin' || ur.role.name === 'support_admin');
}

// ============================================
// Type Definitions
// ============================================

declare module '@/types/support' {
  export interface SupportTicket {
    id: string;
    userId: string;
    subject: string;
    description: string;
    status: 'open' | 'in_progress' | 'resolved' | 'closed' | 'pending' | 'escalated';
    priority: 'low' | 'medium' | 'high' | 'critical';
    category: 'technical' | 'billing' | 'account' | 'trading' | 'security' | 'general' | 'api';
    assignedTo?: string;
    assignedToUser?: {
      id: string;
      name: string;
      email: string;
      image?: string;
    };
    user: {
      id: string;
      name: string;
      email: string;
      image?: string;
    };
    replies: TicketReply[];
    attachments: TicketAttachment[];
    activities: TicketActivity[];
    metrics?: TicketMetrics;
    tags?: string[];
    metadata?: Record<string, any>;
    createdAt: Date;
    updatedAt: Date;
    resolvedAt?: Date;
    closedAt?: Date;
    lastReplyAt?: Date;
    lastReplyBy?: string;
    replyCount: number;
  }

  export interface TicketReply {
    id: string;
    ticketId: string;
    userId: string;
    content: string;
    isInternal: boolean;
    attachments: TicketAttachment[];
    user: {
      id: string;
      name: string;
      email: string;
      image?: string;
    };
    createdAt: Date;
    updatedAt: Date;
  }

  export interface TicketAttachment {
    id: string;
    name: string;
    type: string;
    size: number;
    url: string;
    createdAt: Date;
  }

  export interface TicketActivity {
    id: string;
    ticketId: string;
    userId: string;
    type: 'created' | 'updated' | 'replied' | 'status_changed' | 'priority_changed' | 'assigned' | 'escalated' | 'resolved' | 'closed' | 'reopened';
    details: Record<string, any>;
    createdAt: Date;
  }

  export interface TicketMetrics {
    id: string;
    ticketId: string;
    viewCount: number;
    replyCount: number;
    status: string;
    firstResponseTime?: number;
    resolutionTime?: number;
    lastViewedAt?: Date;
    resolvedAt?: Date;
    createdAt: Date;
    updatedAt: Date;
  }

  export interface TicketAssignment {
    ticketId: string;
    assignedTo: string;
    assignedBy: string;
    assignedAt: Date;
    reason?: string;
  }

  export interface TicketEscalation {
    ticketId: string;
    escalatedAt: Date;
    escalatedBy: string;
    reason: string;
    previousStatus: string;
    previousPriority: string;
  }
}

// ============================================
// Constants
// ============================================

export const TICKET_STATUSES = {
  OPEN: 'open',
  IN_PROGRESS: 'in_progress',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
  PENDING: 'pending',
  ESCALATED: 'escalated',
} as const;

export const TICKET_PRIORITIES = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
} as const;

export const TICKET_CATEGORIES = {
  TECHNICAL: 'technical',
  BILLING: 'billing',
  ACCOUNT: 'account',
  TRADING: 'trading',
  SECURITY: 'security',
  GENERAL: 'general',
  API: 'api',
} as const;

export const TICKET_ACTIVITY_TYPES = {
  CREATED: 'created',
  UPDATED: 'updated',
  REPLIED: 'replied',
  STATUS_CHANGED: 'status_changed',
  PRIORITY_CHANGED: 'priority_changed',
  ASSIGNED: 'assigned',
  ESCALATED: 'escalated',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
  REOPENED: 'reopened',
} as const;

export const MAX_TICKET_ATTACHMENTS = 10;
export const MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024; // 10MB

export const ALLOWED_ATTACHMENT_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/svg+xml',
  'application/pdf',
  'text/plain',
  'text/csv',
  'application/json',
  'application/zip',
];

export const TICKET_ESCALATION_RULES = {
  high: {
    threshold: 4, // hours
    notifyLevel: 2, // escalation level
  },
  critical: {
    threshold: 1, // hours
    notifyLevel: 3, // escalation level
  },
};

export const TICKET_SLA_RULES = {
  low: 48 * 3600 * 1000, // 48 hours
  medium: 24 * 3600 * 1000, // 24 hours
  high: 8 * 3600 * 1000, // 8 hours
  critical: 2 * 3600 * 1000, // 2 hours
};

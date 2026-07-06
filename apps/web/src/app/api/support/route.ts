/**
 * NEXUS AI TRADING SYSTEM - Support Tickets API Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles support ticket operations including:
 * - GET: List tickets with filtering and pagination
 * - POST: Create new support ticket
 * - Bulk operations
 * - Advanced filtering and search
 * - Sorting and pagination
 * - Statistics and metrics
 * - Export functionality
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
  TicketStatus,
  TicketPriority,
  TicketCategory,
  TicketFilter,
  TicketSort,
  TicketStats,
  TicketExport,
  BulkTicketOperation,
} from '@/types/support';

// Utils
import {
  validateTicketCreation,
  validateTicketListAccess,
  formatTicketListResponse,
  generateTicketActivity,
  sendTicketNotification,
  logTicketAction,
  createAuditLog,
  handleTicketError,
  generateTicketId,
} from '@/lib/support';

// Constants
import {
  TICKET_STATUSES,
  TICKET_PRIORITIES,
  TICKET_CATEGORIES,
  TICKET_ACTIVITY_TYPES,
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  TICKET_SORT_FIELDS,
  ALLOWED_ATTACHMENT_TYPES,
  MAX_ATTACHMENT_SIZE,
} from '@/constants/support';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Validation Schemas
// ============================================

const CreateTicketSchema = z.object({
  subject: z.string().min(3).max(200),
  description: z.string().min(10).max(5000),
  priority: z.enum(['low', 'medium', 'high', 'critical']).default('medium'),
  category: z.enum(['technical', 'billing', 'account', 'trading', 'security', 'general', 'api']).default('general'),
  tags: z.array(z.string()).optional(),
  attachments: z.array(z.object({
    name: z.string(),
    type: z.string(),
    size: z.number().max(MAX_ATTACHMENT_SIZE),
    url: z.string().url(),
  })).max(10).optional(),
  metadata: z.record(z.any()).optional(),
});

const ListFilterSchema = z.object({
  status: z.enum(['open', 'in_progress', 'resolved', 'closed', 'pending', 'escalated']).optional(),
  priority: z.enum(['low', 'medium', 'high', 'critical']).optional(),
  category: z.enum(['technical', 'billing', 'account', 'trading', 'security', 'general', 'api']).optional(),
  assignedTo: z.string().uuid().optional(),
  search: z.string().optional(),
  fromDate: z.string().datetime().optional(),
  toDate: z.string().datetime().optional(),
  tags: z.array(z.string()).optional(),
  hasAttachments: z.boolean().optional(),
  hasReplies: z.boolean().optional(),
  page: z.number().int().positive().default(1),
  limit: z.number().int().positive().max(MAX_PAGE_SIZE).default(DEFAULT_PAGE_SIZE),
  sortBy: z.enum(['createdAt', 'updatedAt', 'priority', 'status', 'replyCount']).default('createdAt'),
  sortOrder: z.enum(['asc', 'desc']).default('desc'),
});

const BulkOperationSchema = z.object({
  operation: z.enum(['assign', 'status', 'priority', 'delete', 'archive']),
  ticketIds: z.array(z.string().uuid()).min(1).max(100),
  data: z.record(z.any()).optional(),
});

// ============================================
// Main Handler - GET
// ============================================

export async function GET(req: NextRequest) {
  try {
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
    const rateLimitKey = `support:tickets:list:${userId}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Parse query parameters
    const { searchParams } = new URL(req.url);
    const rawParams = Object.fromEntries(searchParams);
    
    // Check if requesting stats
    if (rawParams.stats === 'true') {
      return await getTicketStats(userId);
    }

    // Check if requesting export
    if (rawParams.export === 'true') {
      return await exportTickets(userId, rawParams);
    }

    // Validate and parse filters
    const validationResult = ListFilterSchema.safeParse({
      status: rawParams.status,
      priority: rawParams.priority,
      category: rawParams.category,
      assignedTo: rawParams.assignedTo,
      search: rawParams.search,
      fromDate: rawParams.fromDate,
      toDate: rawParams.toDate,
      tags: rawParams.tags ? rawParams.tags.split(',') : undefined,
      hasAttachments: rawParams.hasAttachments === 'true',
      hasReplies: rawParams.hasReplies === 'true',
      page: parseInt(rawParams.page || '1'),
      limit: parseInt(rawParams.limit || DEFAULT_PAGE_SIZE.toString()),
      sortBy: rawParams.sortBy || 'createdAt',
      sortOrder: rawParams.sortOrder || 'desc',
    });

    if (!validationResult.success) {
      return NextResponse.json(
        { 
          error: 'Invalid filter parameters',
          details: validationResult.error.errors,
        },
        { status: 400 }
      );
    }

    const filters = validationResult.data;

    // Check access permissions
    const hasAccess = await validateTicketListAccess(userId);
    if (!hasAccess) {
      return NextResponse.json(
        { error: 'Access denied' },
        { status: 403 }
      );
    }

    // Build query
    const where = await buildTicketQuery(userId, filters);
    const skip = (filters.page - 1) * filters.limit;

    // Execute queries
    const [tickets, total] = await Promise.all([
      prisma.supportTicket.findMany({
        where,
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
          _count: {
            select: {
              replies: true,
              attachments: true,
            },
          },
        },
        orderBy: {
          [filters.sortBy]: filters.sortOrder,
        },
        skip,
        take: filters.limit,
      }),
      prisma.supportTicket.count({ where }),
    ]);

    // Get additional metrics for each ticket
    const ticketsWithMetrics = await Promise.all(
      tickets.map(async (ticket) => {
        const metrics = await prisma.ticketMetrics.findUnique({
          where: { ticketId: ticket.id },
        });
        return {
          ...ticket,
          metrics,
        };
      })
    );

    // Log list action
    await logTicketAction({
      userId,
      action: 'list_tickets',
      ip,
      userAgent,
      metadata: {
        filters,
        total,
        returned: tickets.length,
        timestamp: new Date().toISOString(),
      },
    });

    // Calculate pagination info
    const totalPages = Math.ceil(total / filters.limit);

    return NextResponse.json({
      success: true,
      data: {
        tickets: formatTicketListResponse(ticketsWithMetrics),
        pagination: {
          page: filters.page,
          limit: filters.limit,
          total,
          totalPages,
          hasNext: filters.page < totalPages,
          hasPrevious: filters.page > 1,
        },
        filters,
      },
    }, { status: 200 });

  } catch (error: any) {
    console.error('List tickets error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to retrieve tickets' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - POST
// ============================================

export async function POST(req: NextRequest) {
  try {
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
    const rateLimitKey = `support:tickets:create:${userId}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many ticket creation requests. Please try again later.' },
        { status: 429 }
      );
    }

    // Validate ticket data
    const validationResult = CreateTicketSchema.safeParse(body);
    if (!validationResult.success) {
      return NextResponse.json(
        { 
          error: 'Validation failed',
          details: validationResult.error.errors,
        },
        { status: 400 }
      );
    }

    const ticketData = validationResult.data;

    // Check if user exists
    const user = await prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      );
    }

    // Create ticket
    const ticket = await prisma.supportTicket.create({
      data: {
        id: generateTicketId(),
        userId,
        subject: ticketData.subject,
        description: ticketData.description,
        priority: ticketData.priority,
        category: ticketData.category,
        status: 'open',
        tags: ticketData.tags || [],
        metadata: ticketData.metadata || {},
        createdAt: new Date(),
        updatedAt: new Date(),
        replyCount: 0,
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
      },
    });

    // Create ticket metrics
    await prisma.ticketMetrics.create({
      data: {
        ticketId: ticket.id,
        viewCount: 0,
        replyCount: 0,
        status: 'open',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Handle attachments if any
    if (ticketData.attachments && ticketData.attachments.length > 0) {
      await prisma.ticketAttachment.createMany({
        data: ticketData.attachments.map(att => ({
          ticketId: ticket.id,
          name: att.name,
          type: att.type,
          size: att.size,
          url: att.url,
          createdAt: new Date(),
        })),
      });
    }

    // Generate activity
    await generateTicketActivity({
      ticketId: ticket.id,
      userId,
      type: 'created',
      details: {
        subject: ticketData.subject,
        priority: ticketData.priority,
        category: ticketData.category,
        hasAttachments: ticketData.attachments && ticketData.attachments.length > 0,
      },
    });

    // Send notifications
    await sendTicketNotification({
      ticket,
      type: 'created',
      triggeredBy: userId,
    });

    // Create audit log
    await createAuditLog({
      userId,
      action: 'ticket_created',
      resource: 'support_ticket',
      resourceId: ticket.id,
      metadata: {
        ticketId: ticket.id,
        subject: ticketData.subject,
        priority: ticketData.priority,
        category: ticketData.category,
        ip,
        userAgent,
      },
      ip,
      userAgent,
    });

    return NextResponse.json({
      success: true,
      data: {
        ticket: {
          ...ticket,
          attachments: ticketData.attachments || [],
        },
        message: 'Ticket created successfully',
      },
    }, { status: 201 });

  } catch (error: any) {
    console.error('Create ticket error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to create ticket' },
      { status: 500 }
    );
  }
}

// ============================================
// Main Handler - PUT (Bulk Operations)
// ============================================

export async function PUT(req: NextRequest) {
  try {
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

    // Check admin permissions for bulk operations
    const isAdmin = await checkUserAdmin(userId);
    if (!isAdmin) {
      return NextResponse.json(
        { error: 'Admin access required for bulk operations' },
        { status: 403 }
      );
    }

    // Rate limiting
    const rateLimitKey = `support:tickets:bulk:${userId}`;
    const isRateLimited = await checkRateLimit(rateLimitKey);
    if (isRateLimited) {
      return NextResponse.json(
        { error: 'Too many bulk operations. Please try again later.' },
        { status: 429 }
      );
    }

    // Validate bulk operation
    const validationResult = BulkOperationSchema.safeParse(body);
    if (!validationResult.success) {
      return NextResponse.json(
        { 
          error: 'Validation failed',
          details: validationResult.error.errors,
        },
        { status: 400 }
      );
    }

    const { operation, ticketIds, data } = validationResult.data;

    // Verify all tickets exist and user has access
    const tickets = await prisma.supportTicket.findMany({
      where: {
        id: { in: ticketIds },
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

    if (tickets.length !== ticketIds.length) {
      return NextResponse.json(
        { 
          error: 'Some tickets not found',
          found: tickets.length,
          requested: ticketIds.length,
        },
        { status: 404 }
      );
    }

    // Perform bulk operation
    let result;
    let updatedTickets = [];

    switch (operation) {
      case 'assign':
        result = await bulkAssign(tickets, data.assignedTo, userId);
        break;
      
      case 'status':
        result = await bulkStatusUpdate(tickets, data.status, userId);
        break;
      
      case 'priority':
        result = await bulkPriorityUpdate(tickets, data.priority, userId);
        break;
      
      case 'delete':
        result = await bulkDelete(tickets, userId);
        break;
      
      case 'archive':
        result = await bulkArchive(tickets, userId);
        break;
      
      default:
        return NextResponse.json(
          { error: 'Invalid bulk operation' },
          { status: 400 }
        );
    }

    // Create audit log
    await createAuditLog({
      userId,
      action: `bulk_${operation}`,
      resource: 'support_ticket',
      metadata: {
        ticketIds,
        count: ticketIds.length,
        operation,
        data,
        ip,
        userAgent,
      },
      ip,
      userAgent,
    });

    return NextResponse.json({
      success: true,
      data: {
        operation,
        affected: ticketIds.length,
        result,
        tickets: formatTicketListResponse(result),
      },
    }, { status: 200 });

  } catch (error: any) {
    console.error('Bulk operation error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to perform bulk operation' },
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
  const maxAttempts = 60; // Max 60 requests per minute
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

async function checkUserAdmin(userId: string): Promise<boolean> {
  const userRoles = await prisma.userRole.findMany({
    where: { userId },
    include: {
      role: true,
    },
  });

  return userRoles.some(ur => ur.role.name === 'admin' || ur.role.name === 'support_admin');
}

async function buildTicketQuery(userId: string, filters: any) {
  const where: any = {};

  // User can only see their own tickets unless admin
  const isAdmin = await checkUserAdmin(userId);
  if (!isAdmin) {
    where.userId = userId;
  }

  // Apply filters
  if (filters.status) {
    where.status = filters.status;
  }

  if (filters.priority) {
    where.priority = filters.priority;
  }

  if (filters.category) {
    where.category = filters.category;
  }

  if (filters.assignedTo) {
    where.assignedTo = filters.assignedTo;
  }

  if (filters.search) {
    where.OR = [
      { subject: { contains: filters.search, mode: 'insensitive' } },
      { description: { contains: filters.search, mode: 'insensitive' } },
    ];
  }

  if (filters.fromDate) {
    where.createdAt = {
      ...where.createdAt,
      gte: new Date(filters.fromDate),
    };
  }

  if (filters.toDate) {
    where.createdAt = {
      ...where.createdAt,
      lte: new Date(filters.toDate),
    };
  }

  if (filters.tags && filters.tags.length > 0) {
    where.tags = {
      hasSome: filters.tags,
    };
  }

  if (filters.hasAttachments !== undefined) {
    where.attachments = filters.hasAttachments 
      ? { some: {} } 
      : { none: {} };
  }

  if (filters.hasReplies !== undefined) {
    where.replies = filters.hasReplies 
      ? { some: {} } 
      : { none: {} };
  }

  return where;
}

async function getTicketStats(userId: string) {
  const isAdmin = await checkUserAdmin(userId);
  
  const where: any = {};
  if (!isAdmin) {
    where.userId = userId;
  }

  const [
    total,
    open,
    inProgress,
    resolved,
    closed,
    pending,
    escalated,
    byPriority,
    byCategory,
    averageResolutionTime,
  ] = await Promise.all([
    prisma.supportTicket.count({ where }),
    prisma.supportTicket.count({ where: { ...where, status: 'open' } }),
    prisma.supportTicket.count({ where: { ...where, status: 'in_progress' } }),
    prisma.supportTicket.count({ where: { ...where, status: 'resolved' } }),
    prisma.supportTicket.count({ where: { ...where, status: 'closed' } }),
    prisma.supportTicket.count({ where: { ...where, status: 'pending' } }),
    prisma.supportTicket.count({ where: { ...where, status: 'escalated' } }),
    prisma.$queryRaw`
      SELECT priority, COUNT(*) as count
      FROM "SupportTicket"
      WHERE ${where.userId ? `"userId" = '${where.userId}'` : '1=1'}
      GROUP BY priority
    `,
    prisma.$queryRaw`
      SELECT category, COUNT(*) as count
      FROM "SupportTicket"
      WHERE ${where.userId ? `"userId" = '${where.userId}'` : '1=1'}
      GROUP BY category
    `,
    prisma.$queryRaw`
      SELECT AVG(EXTRACT(EPOCH FROM ("resolvedAt" - "createdAt"))) as avg_seconds
      FROM "SupportTicket"
      WHERE status = 'resolved'
      AND "resolvedAt" IS NOT NULL
      ${where.userId ? `AND "userId" = '${where.userId}'` : ''}
    `,
  ]);

  const stats: TicketStats = {
    total,
    open,
    inProgress,
    resolved,
    closed,
    pending,
    escalated,
    byPriority: formatStatsResult(byPriority),
    byCategory: formatStatsResult(byCategory),
    averageResolutionTime: averageResolutionTime[0]?.avg_seconds 
      ? Math.round(averageResolutionTime[0].avg_seconds / 3600) // Convert to hours
      : 0,
  };

  return NextResponse.json({
    success: true,
    data: stats,
  }, { status: 200 });
}

function formatStatsResult(result: any[]): Record<string, number> {
  const formatted: Record<string, number> = {};
  result.forEach((item: any) => {
    formatted[item.priority || item.category] = parseInt(item.count);
  });
  return formatted;
}

async function exportTickets(userId: string, params: any) {
  // Build query from params
  const filters = {
    status: params.status,
    priority: params.priority,
    category: params.category,
    fromDate: params.fromDate,
    toDate: params.toDate,
  };

  const where = await buildTicketQuery(userId, filters);

  const tickets = await prisma.supportTicket.findMany({
    where,
    include: {
      user: {
        select: {
          name: true,
          email: true,
        },
      },
      assignedToUser: {
        select: {
          name: true,
          email: true,
        },
      },
      replies: {
        select: {
          content: true,
          createdAt: true,
          user: {
            select: {
              name: true,
              email: true,
            },
          },
        },
      },
    },
    orderBy: {
      createdAt: 'desc',
    },
  });

  // Format for export
  const exportData: TicketExport = {
    tickets: tickets.map(ticket => ({
      id: ticket.id,
      subject: ticket.subject,
      description: ticket.description,
      status: ticket.status,
      priority: ticket.priority,
      category: ticket.category,
      createdAt: ticket.createdAt,
      updatedAt: ticket.updatedAt,
      resolvedAt: ticket.resolvedAt,
      closedAt: ticket.closedAt,
      replyCount: ticket.replyCount,
      user: ticket.user,
      assignedTo: ticket.assignedToUser,
      replies: ticket.replies,
    })),
    exportedAt: new Date(),
    totalTickets: tickets.length,
  };

  return NextResponse.json({
    success: true,
    data: exportData,
  }, { status: 200 });
}

async function bulkAssign(tickets: any[], assignedTo: string, userId: string) {
  const ticketIds = tickets.map(t => t.id);
  
  const updated = await prisma.supportTicket.updateMany({
    where: { id: { in: ticketIds } },
    data: {
      assignedTo,
      assignedAt: new Date(),
      updatedAt: new Date(),
    },
  });

  // Generate activities for each ticket
  for (const ticket of tickets) {
    await generateTicketActivity({
      ticketId: ticket.id,
      userId,
      type: 'assigned',
      details: {
        assignedTo,
      },
    });
  }

  return { updated: updated.count };
}

async function bulkStatusUpdate(tickets: any[], status: string, userId: string) {
  const ticketIds = tickets.map(t => t.id);
  
  const updated = await prisma.supportTicket.updateMany({
    where: { id: { in: ticketIds } },
    data: {
      status,
      ...(status === 'resolved' && {
        resolvedAt: new Date(),
        resolvedBy: userId,
      }),
      ...(status === 'closed' && {
        closedAt: new Date(),
        closedBy: userId,
      }),
      updatedAt: new Date(),
    },
  });

  // Generate activities for each ticket
  for (const ticket of tickets) {
    await generateTicketActivity({
      ticketId: ticket.id,
      userId,
      type: 'status_changed',
      details: {
        from: ticket.status,
        to: status,
      },
    });
  }

  return { updated: updated.count };
}

async function bulkPriorityUpdate(tickets: any[], priority: string, userId: string) {
  const ticketIds = tickets.map(t => t.id);
  
  const updated = await prisma.supportTicket.updateMany({
    where: { id: { in: ticketIds } },
    data: {
      priority,
      updatedAt: new Date(),
    },
  });

  // Generate activities for each ticket
  for (const ticket of tickets) {
    await generateTicketActivity({
      ticketId: ticket.id,
      userId,
      type: 'priority_changed',
      details: {
        from: ticket.priority,
        to: priority,
      },
    });
  }

  return { updated: updated.count };
}

async function bulkDelete(tickets: any[], userId: string) {
  const ticketIds = tickets.map(t => t.id);
  
  // Delete related records first
  await prisma.ticketMetrics.deleteMany({
    where: { ticketId: { in: ticketIds } },
  });

  await prisma.ticketReply.deleteMany({
    where: { ticketId: { in: ticketIds } },
  });

  await prisma.ticketAttachment.deleteMany({
    where: { ticketId: { in: ticketIds } },
  });

  await prisma.ticketActivity.deleteMany({
    where: { ticketId: { in: ticketIds } },
  });

  // Delete tickets
  const deleted = await prisma.supportTicket.deleteMany({
    where: { id: { in: ticketIds } },
  });

  return { deleted: deleted.count };
}

async function bulkArchive(tickets: any[], userId: string) {
  const ticketIds = tickets.map(t => t.id);
  
  const archived = await prisma.supportTicket.updateMany({
    where: { id: { in: ticketIds } },
    data: {
      status: 'closed',
      closedAt: new Date(),
      closedBy: userId,
      metadata: {
        archived: true,
        archivedAt: new Date().toISOString(),
        archivedBy: userId,
      },
      updatedAt: new Date(),
    },
  });

  // Generate activities for each ticket
  for (const ticket of tickets) {
    await generateTicketActivity({
      ticketId: ticket.id,
      userId,
      type: 'closed',
      details: {
        reason: 'Archived',
      },
    });
  }

  return { archived: archived.count };
}

// ============================================
// Type Definitions
// ============================================

declare module '@/types/support' {
  export interface TicketFilter {
    status?: TicketStatus;
    priority?: TicketPriority;
    category?: TicketCategory;
    assignedTo?: string;
    search?: string;
    fromDate?: string;
    toDate?: string;
    tags?: string[];
    hasAttachments?: boolean;
    hasReplies?: boolean;
    page: number;
    limit: number;
    sortBy: 'createdAt' | 'updatedAt' | 'priority' | 'status' | 'replyCount';
    sortOrder: 'asc' | 'desc';
  }

  export interface TicketSort {
    field: 'createdAt' | 'updatedAt' | 'priority' | 'status' | 'replyCount';
    order: 'asc' | 'desc';
  }

  export interface TicketStats {
    total: number;
    open: number;
    inProgress: number;
    resolved: number;
    closed: number;
    pending: number;
    escalated: number;
    byPriority: Record<string, number>;
    byCategory: Record<string, number>;
    averageResolutionTime: number;
  }

  export interface TicketExport {
    tickets: any[];
    exportedAt: Date;
    totalTickets: number;
  }

  export interface BulkTicketOperation {
    operation: 'assign' | 'status' | 'priority' | 'delete' | 'archive';
    ticketIds: string[];
    data?: {
      assignedTo?: string;
      status?: string;
      priority?: string;
    };
  }
}

// ============================================
// Constants
// ============================================

export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

export const TICKET_SORT_FIELDS = {
  CREATED_AT: 'createdAt',
  UPDATED_AT: 'updatedAt',
  PRIORITY: 'priority',
  STATUS: 'status',
  REPLY_COUNT: 'replyCount',
} as const;

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

export const MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024; // 10MB

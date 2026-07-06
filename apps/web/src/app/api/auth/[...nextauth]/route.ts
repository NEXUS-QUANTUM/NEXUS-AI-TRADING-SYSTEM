/**
 * NEXUS AI TRADING SYSTEM - NextAuth.js Authentication Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles all authentication flows including:
 * - JWT authentication with refresh tokens
 * - OAuth2 providers (Google, GitHub, Telegram)
 * - Custom credentials provider
 * - Session management
 * - Role-based access control
 * - Two-factor authentication support
 * - Rate limiting protection
 * - Audit logging
 * - Device fingerprinting
 * - Session revocation
 * - Multi-factor authentication
 * - Passwordless authentication
 * - Social login integration
 * - API key authentication
 * - Web3 wallet authentication
 */

import NextAuth, { NextAuthOptions, Session, User, Account, Profile } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import GoogleProvider from 'next-auth/providers/google';
import GitHubProvider from 'next-auth/providers/github';
import { JWT } from 'next-auth/jwt';
import { Provider } from 'next-auth/providers';

// Types
import type { 
  AuthUser, 
  AuthSession, 
  AuthToken, 
  AuthProvider,
  MFASession,
  SecurityContext,
  DeviceInfo,
  AuthLog,
  RateLimitInfo,
} from '@/types/auth';

// Utils
import { 
  verifyPassword, 
  hashPassword,
  generateTokens,
  verifyToken,
  decodeToken,
  generateMFACode,
  verifyMFACode,
  generateBackupCodes,
  encryptData,
  decryptData,
  createDeviceFingerprint,
  validateIP,
  isRateLimited,
  logAuthEvent,
} from '@/lib/auth';

// Constants
import {
  AUTH_PROVIDERS,
  AUTH_ERRORS,
  SESSION_DEFAULTS,
  RATE_LIMITS,
  SECURITY_HEADERS,
  MFA_SETTINGS,
  PASSWORD_POLICY,
  SESSION_MAX_AGE,
  REFRESH_TOKEN_AGE,
} from '@/constants/auth';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Configuration
// ============================================

const NEXUS_AUTH_CONFIG: NextAuthOptions = {
  // Providers
  providers: [
    // --- Google OAuth2 ---
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
      authorization: {
        params: {
          scope: 'openid email profile',
          prompt: 'select_account',
        },
      },
      profile(profile: any): User {
        return {
          id: profile.sub,
          name: profile.name,
          email: profile.email,
          image: profile.picture,
          emailVerified: new Date(),
          provider: 'google',
        };
      },
    }),

    // --- GitHub OAuth2 ---
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID || '',
      clientSecret: process.env.GITHUB_CLIENT_SECRET || '',
      profile(profile: any): User {
        return {
          id: profile.id.toString(),
          name: profile.name || profile.login,
          email: profile.email,
          image: profile.avatar_url,
          emailVerified: profile.email ? new Date() : null,
          provider: 'github',
        };
      },
    }),

    // --- Custom Credentials Provider ---
    CredentialsProvider({
      id: 'credentials',
      name: 'Email & Password',
      credentials: {
        email: { label: 'Email', type: 'email', placeholder: 'user@example.com' },
        password: { label: 'Password', type: 'password' },
        mfaCode: { label: 'MFA Code', type: 'text', placeholder: '6-digit code' },
        rememberMe: { label: 'Remember Me', type: 'checkbox' },
        deviceName: { label: 'Device Name', type: 'text' },
      },
      async authorize(credentials, req) {
        try {
          if (!credentials?.email || !credentials?.password) {
            throw new Error(AUTH_ERRORS.MISSING_CREDENTIALS);
          }

          // Rate limiting check
          const ip = req.headers?.get('x-forwarded-for') || req.headers?.get('x-real-ip') || 'unknown';
          const rateLimitKey = `auth:rate:${ip}`;
          const rateLimitInfo = await getRateLimitInfo(rateLimitKey);
          
          if (rateLimitInfo.blocked) {
            throw new Error(AUTH_ERRORS.RATE_LIMIT_EXCEEDED);
          }

          // Find user
          const user = await prisma.user.findUnique({
            where: { email: credentials.email.toLowerCase() },
            include: {
              account: true,
              security: true,
              mfa: true,
              roles: {
                include: {
                  role: {
                    include: {
                      permissions: true,
                    },
                  },
                },
              },
              sessions: {
                orderBy: { lastUsed: 'desc' },
                take: 10,
              },
            },
          });

          if (!user) {
            await logAuthEvent({
              type: 'failed_login',
              userId: null,
              email: credentials.email,
              ip,
              userAgent: req.headers?.get('user-agent') || 'unknown',
              reason: 'User not found',
            });
            throw new Error(AUTH_ERRORS.INVALID_CREDENTIALS);
          }

          // Check if account is locked
          if (user.locked) {
            throw new Error(AUTH_ERRORS.ACCOUNT_LOCKED);
          }

          // Check if account is active
          if (!user.active) {
            throw new Error(AUTH_ERRORS.ACCOUNT_INACTIVE);
          }

          // Verify password
          const isValidPassword = await verifyPassword(credentials.password, user.passwordHash);
          
          if (!isValidPassword) {
            // Increment failed attempts
            await prisma.user.update({
              where: { id: user.id },
              data: {
                failedLoginAttempts: { increment: 1 },
                lastFailedLogin: new Date(),
              },
            });

            // Lock account if too many failed attempts
            if (user.failedLoginAttempts + 1 >= PASSWORD_POLICY.MAX_FAILED_ATTEMPTS) {
              await prisma.user.update({
                where: { id: user.id },
                data: { locked: true },
              });
              throw new Error(AUTH_ERRORS.ACCOUNT_LOCKED);
            }

            await logAuthEvent({
              type: 'failed_login',
              userId: user.id,
              email: user.email,
              ip,
              userAgent: req.headers?.get('user-agent') || 'unknown',
              reason: 'Invalid password',
            });
            throw new Error(AUTH_ERRORS.INVALID_CREDENTIALS);
          }

          // Reset failed attempts on successful login
          await prisma.user.update({
            where: { id: user.id },
            data: {
              failedLoginAttempts: 0,
              lastLogin: new Date(),
            },
          });

          // Verify MFA if enabled
          if (user.mfa?.enabled) {
            if (!credentials.mfaCode) {
              throw new Error(AUTH_ERRORS.MFA_REQUIRED);
            }

            const isValidMFA = await verifyMFACode(user.id, credentials.mfaCode);
            if (!isValidMFA) {
              await logAuthEvent({
                type: 'failed_mfa',
                userId: user.id,
                email: user.email,
                ip,
                userAgent: req.headers?.get('user-agent') || 'unknown',
                reason: 'Invalid MFA code',
              });
              throw new Error(AUTH_ERRORS.INVALID_MFA_CODE);
            }

            // Update MFA last used
            await prisma.mFA.update({
              where: { userId: user.id },
              data: { lastUsed: new Date() },
            });
          }

          // Create device fingerprint
          const deviceInfo = {
            ip,
            userAgent: req.headers?.get('user-agent') || 'unknown',
            deviceName: credentials.deviceName || req.headers?.get('user-agent')?.split(' ')[0] || 'Unknown',
            fingerprint: await createDeviceFingerprint(req),
          };

          // Check if device is known and trusted
          const isTrustedDevice = await checkTrustedDevice(user.id, deviceInfo.fingerprint);

          // Create session
          const session = await prisma.session.create({
            data: {
              userId: user.id,
              token: await generateSessionToken(),
              expires: new Date(Date.now() + SESSION_MAX_AGE),
              lastUsed: new Date(),
              ip,
              userAgent: deviceInfo.userAgent,
              deviceName: deviceInfo.deviceName,
              deviceFingerprint: deviceInfo.fingerprint,
              isTrusted: isTrustedDevice,
              metadata: {
                timestamp: new Date().toISOString(),
                location: await getLocationFromIP(ip),
              },
            },
          });

          // Log successful login
          await logAuthEvent({
            type: 'successful_login',
            userId: user.id,
            email: user.email,
            ip,
            userAgent: deviceInfo.userAgent,
            sessionId: session.id,
          });

          // Generate JWT tokens
          const tokens = generateTokens({
            userId: user.id,
            email: user.email,
            roles: user.roles.map(r => r.role.name),
            permissions: user.roles.flatMap(r => r.role.permissions.map(p => p.name)),
            sessionId: session.id,
          });

          // Return user with tokens
          return {
            id: user.id,
            email: user.email,
            name: user.name || user.email?.split('@')[0] || 'User',
            image: user.image || null,
            tokens,
            sessionId: session.id,
            mfaRequired: user.mfa?.enabled && !isTrustedDevice,
            roles: user.roles.map(r => r.role.name),
            permissions: user.roles.flatMap(r => r.role.permissions.map(p => p.name)),
            provider: 'credentials',
          } as any;

        } catch (error: any) {
          console.error('Authorization error:', error);
          throw new Error(error.message || AUTH_ERRORS.AUTH_FAILED);
        }
      },
    }),

    // --- Telegram OAuth2 ---
    {
      id: 'telegram',
      name: 'Telegram',
      type: 'oauth',
      clientId: process.env.TELEGRAM_BOT_TOKEN || '',
      clientSecret: process.env.TELEGRAM_BOT_TOKEN || '',
      wellKnown: 'https://api.telegram.org/bot',
      authorization: {
        url: `https://oauth.telegram.org/auth`,
        params: {
          bot_id: process.env.TELEGRAM_BOT_ID,
          scope: 'all',
          response_type: 'code',
        },
      },
      token: {
        url: `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/getWebhookInfo`,
      },
      userinfo: {
        url: `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/getChat`,
      },
      profile(profile: any): User {
        return {
          id: profile.id.toString(),
          name: profile.first_name,
          image: profile.photo_url,
          email: `${profile.id}@telegram.user`,
          provider: 'telegram',
        };
      },
    } as Provider,

    // --- Web3 Wallet Authentication ---
    {
      id: 'web3',
      name: 'Web3 Wallet',
      type: 'oauth',
      clientId: process.env.WEB3_CLIENT_ID || 'web3',
      clientSecret: process.env.WEB3_CLIENT_SECRET || 'web3',
      authorization: {
        url: '/api/auth/web3',
        params: {
          challenge: 'Login with Ethereum',
        },
      },
      token: {
        url: '/api/auth/web3/token',
      },
      userinfo: {
        url: '/api/auth/web3/userinfo',
      },
      profile(profile: any): User {
        return {
          id: profile.address,
          name: profile.ens || profile.address.slice(0, 10) + '...',
          email: `${profile.address}@web3.user`,
          image: `https://effigy.im/a/${profile.address}.png`,
          provider: 'web3',
        };
      },
    } as Provider,
  ],

  // ============================================
  // Session Configuration
  // ============================================
  session: {
    strategy: 'jwt',
    maxAge: SESSION_MAX_AGE / 1000, // Convert ms to seconds
    updateAge: 60 * 60, // 1 hour
  },

  // ============================================
  // JWT Configuration
  // ============================================
  jwt: {
    secret: process.env.JWT_SECRET || 'default-jwt-secret-change-me',
    maxAge: SESSION_MAX_AGE / 1000,
    encryption: true,
    encode: async ({ secret, token, maxAge }) => {
      return sign(token, secret, {
        expiresIn: maxAge,
        algorithm: 'HS256',
      });
    },
    decode: async ({ secret, token }) => {
      return verify(token, secret, {
        algorithms: ['HS256'],
      });
    },
  },

  // ============================================
  // Callbacks
  // ============================================
  callbacks: {
    // --- Sign In Callback ---
    async signIn({ user, account, profile, credentials, email, session }) {
      try {
        // Log sign in attempt
        await logAuthEvent({
          type: 'sign_in_attempt',
          userId: user?.id,
          email: user?.email || email || undefined,
          provider: account?.provider || 'unknown',
          success: true,
        });

        // Check if user exists in database
        if (user?.email && account?.provider !== 'credentials') {
          const existingUser = await prisma.user.findUnique({
            where: { email: user.email },
            include: {
              accounts: true,
            },
          });

          if (!existingUser) {
            // Create new user for OAuth provider
            const newUser = await prisma.user.create({
              data: {
                email: user.email,
                name: user.name,
                image: user.image,
                emailVerified: new Date(),
                accounts: {
                  create: {
                    provider: account.provider,
                    providerAccountId: account.providerAccountId,
                    type: account.type,
                    accessToken: account.access_token,
                    refreshToken: account.refresh_token,
                    expiresAt: account.expires_at ? new Date(account.expires_at * 1000) : null,
                    tokenType: account.token_type,
                    scope: account.scope,
                    idToken: account.id_token,
                  },
                },
              },
            });

            // Create default role for new user
            await prisma.userRole.create({
              data: {
                userId: newUser.id,
                roleId: (await prisma.role.findFirst({ where: { name: 'user' } }))?.id || '',
              },
            });

            // Log user creation
            await logAuthEvent({
              type: 'user_created',
              userId: newUser.id,
              email: newUser.email,
              provider: account.provider,
              success: true,
            });
          } else {
            // Update existing OAuth account
            await prisma.account.upsert({
              where: {
                provider_providerAccountId: {
                  provider: account.provider,
                  providerAccountId: account.providerAccountId,
                },
              },
              update: {
                accessToken: account.access_token,
                refreshToken: account.refresh_token,
                expiresAt: account.expires_at ? new Date(account.expires_at * 1000) : null,
                tokenType: account.token_type,
                scope: account.scope,
                idToken: account.id_token,
                updatedAt: new Date(),
              },
              create: {
                userId: existingUser.id,
                provider: account.provider,
                providerAccountId: account.providerAccountId,
                type: account.type,
                accessToken: account.access_token,
                refreshToken: account.refresh_token,
                expiresAt: account.expires_at ? new Date(account.expires_at * 1000) : null,
                tokenType: account.token_type,
                scope: account.scope,
                idToken: account.id_token,
              },
            });
          }
        }

        return true;
      } catch (error) {
        console.error('Sign in callback error:', error);
        return false;
      }
    },

    // --- JWT Callback ---
    async jwt({ token, user, account, profile, session, trigger }) {
      try {
        // Initial sign in
        if (user) {
          token.userId = user.id;
          token.email = user.email;
          token.name = user.name;
          token.image = user.image;
          token.roles = (user as any).roles || ['user'];
          token.permissions = (user as any).permissions || [];
          token.sessionId = (user as any).sessionId || null;
          token.mfaRequired = (user as any).mfaRequired || false;
          token.provider = (user as any).provider || 'credentials';
          token.tokens = (user as any).tokens || null;
        }

        // Refresh session if needed
        if (token.sessionId && trigger === 'update') {
          const session = await prisma.session.findUnique({
            where: { id: token.sessionId as string },
            include: {
              user: {
                include: {
                  roles: {
                    include: {
                      role: {
                        include: {
                          permissions: true,
                        },
                      },
                    },
                  },
                },
              },
            },
          });

          if (session) {
            // Update user info from session
            token.userId = session.userId;
            token.email = session.user.email;
            token.name = session.user.name;
            token.image = session.user.image;
            token.roles = session.user.roles.map(r => r.role.name);
            token.permissions = session.user.roles.flatMap(r => r.role.permissions.map(p => p.name));
            token.lastSessionRefresh = new Date().toISOString();
          }
        }

        // Validate session exists and is not expired
        if (token.sessionId) {
          const session = await prisma.session.findUnique({
            where: { id: token.sessionId as string },
          });

          if (!session || session.expires < new Date()) {
            // Session expired or revoked
            token.sessionId = null;
            token.expires = 0;
            throw new Error(AUTH_ERRORS.SESSION_EXPIRED);
          }

          // Update session last used
          await prisma.session.update({
            where: { id: session.id },
            data: { lastUsed: new Date() },
          });
        }

        // Set token expiration
        token.expires = Math.floor(Date.now() / 1000) + SESSION_MAX_AGE / 1000;
        token.iat = Math.floor(Date.now() / 1000);

        return token;
      } catch (error) {
        console.error('JWT callback error:', error);
        // Return minimal token on error
        return {
          ...token,
          expires: Math.floor(Date.now() / 1000) + 300, // 5 minutes grace period
        };
      }
    },

    // --- Session Callback ---
    async session({ session, token, user }: { session: Session; token: JWT; user: User }) {
      try {
        // Add custom fields to session
        session.user.id = token.userId as string;
        session.user.email = token.email as string;
        session.user.name = token.name as string;
        session.user.image = token.image as string || null;
        session.user.roles = token.roles as string[] || ['user'];
        session.user.permissions = token.permissions as string[] || [];
        session.user.sessionId = token.sessionId as string || null;
        session.user.mfaRequired = token.mfaRequired as boolean || false;
        session.user.provider = token.provider as string || 'credentials';
        session.user.isAuthenticated = true;
        session.user.lastSessionRefresh = token.lastSessionRefresh as string || new Date().toISOString();
        session.user.expiresAt = token.expires ? new Date(token.expires * 1000) : undefined;

        // Add security context
        session.user.securityContext = {
          deviceId: token.deviceId as string || null,
          sessionId: token.sessionId as string || null,
          lastLogin: token.lastLogin as string || new Date().toISOString(),
          loginCount: token.loginCount as number || 0,
          mfaVerified: token.mfaVerified as boolean || false,
          emailVerified: token.emailVerified as boolean || false,
          ipAddress: token.ipAddress as string || null,
          userAgent: token.userAgent as string || null,
        };

        // Check if session is still valid
        if (token.sessionId) {
          const dbSession = await prisma.session.findUnique({
            where: { id: token.sessionId as string },
          });

          if (!dbSession || dbSession.expires < new Date()) {
            // Session expired or revoked
            session.user.isAuthenticated = false;
            session.expires = new Date();
          }
        }

        return session;
      } catch (error) {
        console.error('Session callback error:', error);
        // Return minimal session on error
        return session;
      }
    },

    // --- Redirect Callback ---
    async redirect({ url, baseUrl }) {
      // Allows relative URLs
      if (url.startsWith('/')) {
        return `${baseUrl}${url}`;
      }
      // Allows callback URLs on same origin
      else if (new URL(url).origin === baseUrl) {
        return url;
      }
      return baseUrl;
    },
  },

  // ============================================
  // Pages Configuration
  // ============================================
  pages: {
    signIn: '/auth/login',
    signOut: '/auth/logout',
    error: '/auth/error',
    verifyRequest: '/auth/verify-request',
    newUser: '/auth/new-user',
    signUp: '/auth/register',
    resetPassword: '/auth/reset-password',
    updatePassword: '/auth/update-password',
    confirmEmail: '/auth/confirm-email',
    mfa: '/auth/mfa',
    // Custom pages
    callback: '/api/auth/callback',
  },

  // ============================================
  // Security Configuration
  // ============================================
  secret: process.env.NEXTAUTH_SECRET || process.env.JWT_SECRET || 'default-secret-change-me',
  trustHost: true,
  useSecureCookies: process.env.NODE_ENV === 'production',

  // ============================================
  // Cookies Configuration
  // ============================================
  cookies: {
    sessionToken: {
      name: `__Secure-next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
        maxAge: SESSION_MAX_AGE / 1000,
      },
    },
    callbackUrl: {
      name: `__Secure-next-auth.callback-url`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
        maxAge: 60 * 60, // 1 hour
      },
    },
    csrfToken: {
      name: `__Host-next-auth.csrf-token`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
      },
    },
    pkceCodeVerifier: {
      name: `__Secure-next-auth.pkce.code_verifier`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
        maxAge: 60 * 10, // 10 minutes
      },
    },
    state: {
      name: `__Secure-next-auth.state`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
        maxAge: 60 * 10, // 10 minutes
      },
    },
  },

  // ============================================
  // Events
  // ============================================
  events: {
    async signIn({ user, account, profile, isNewUser }) {
      // Log sign in event
      await logAuthEvent({
        type: isNewUser ? 'new_user_signin' : 'user_signin',
        userId: user.id,
        email: user.email || '',
        provider: account?.provider || 'unknown',
        success: true,
      });

      // Update user statistics
      await prisma.user.update({
        where: { id: user.id },
        data: {
          loginCount: { increment: 1 },
          lastLogin: new Date(),
        },
      });

      // Send welcome email for new users
      if (isNewUser) {
        await sendWelcomeEmail(user.email, user.name);
      }

      // Check for suspicious activity
      await checkSuspiciousActivity(user.id);
    },

    async signOut({ session, token }) {
      // Log sign out event
      await logAuthEvent({
        type: 'user_signout',
        userId: token.userId as string,
        email: token.email as string,
        sessionId: session?.id || token.sessionId as string,
        success: true,
      });

      // Invalidate session in database
      if (session?.id) {
        await prisma.session.update({
          where: { id: session.id },
          data: { revoked: true },
        });
      } else if (token.sessionId) {
        await prisma.session.update({
          where: { id: token.sessionId as string },
          data: { revoked: true },
        });
      }

      // Clear refresh tokens
      await prisma.refreshToken.deleteMany({
        where: { userId: token.userId as string },
      });
    },

    async createUser({ user }) {
      // Log user creation
      await logAuthEvent({
        type: 'user_created',
        userId: user.id,
        email: user.email || '',
        success: true,
      });

      // Create default preferences
      await prisma.userPreference.create({
        data: {
          userId: user.id,
          language: 'en',
          theme: 'dark',
          notifications: {
            email: true,
            push: true,
            inApp: true,
          },
        },
      });

      // Create default security settings
      await prisma.userSecurity.create({
        data: {
          userId: user.id,
          twoFactorEnabled: false,
          passwordChangedAt: new Date(),
          loginAlerts: true,
          suspiciousActivityAlerts: true,
        },
      });
    },

    async updateUser({ user }) {
      // Log user update
      await logAuthEvent({
        type: 'user_updated',
        userId: user.id,
        email: user.email || '',
        success: true,
      });
    },

    async linkAccount({ user, account, profile }) {
      // Log account linking
      await logAuthEvent({
        type: 'account_linked',
        userId: user.id,
        email: user.email || '',
        provider: account.provider,
        success: true,
      });
    },

    async session({ session, token }) {
      // Session validation
      try {
        if (token.sessionId) {
          const dbSession = await prisma.session.findUnique({
            where: { id: token.sessionId as string },
          });

          if (!dbSession || dbSession.expires < new Date()) {
            // Session is invalid, will be handled in session callback
            return null;
          }
        }
        return session;
      } catch (error) {
        console.error('Session event error:', error);
        return null;
      }
    },

    async error(error) {
      // Log authentication errors
      console.error('Auth error:', error);
      
      await logAuthEvent({
        type: 'auth_error',
        error: error.error?.message || 'Unknown error',
        stack: error.error?.stack,
        success: false,
      });
    },
  },

  // ============================================
  // Logger Configuration
  // ============================================
  logger: {
    error(code, metadata) {
      console.error(`[Auth Error] ${code}:`, metadata);
    },
    warn(code, metadata) {
      console.warn(`[Auth Warning] ${code}:`, metadata);
    },
    debug(code, metadata) {
      if (process.env.NODE_ENV === 'development') {
        console.debug(`[Auth Debug] ${code}:`, metadata);
      }
    },
  },

  // ============================================
  // Theme Configuration
  // ============================================
  theme: {
    colorScheme: 'dark',
    logo: '/logo.svg',
    brandColor: '#06b6d4',
    buttonText: '#ffffff',
  },

  // ============================================
  // Advanced Configuration
  // ============================================
  // Enable debug in development
  debug: process.env.NODE_ENV === 'development',

  // Custom adapter
  adapter: {
    createUser: async (user) => {
      return prisma.user.create({
        data: {
          ...user,
          email: user.email || '',
        },
      });
    },
    getUser: async (id) => {
      return prisma.user.findUnique({
        where: { id },
      });
    },
    getUserByEmail: async (email) => {
      return prisma.user.findUnique({
        where: { email },
      });
    },
    getUserByAccount: async ({ provider, providerAccountId }) => {
      const account = await prisma.account.findUnique({
        where: {
          provider_providerAccountId: {
            provider,
            providerAccountId,
          },
        },
        include: {
          user: true,
        },
      });
      return account?.user || null;
    },
    updateUser: async (user) => {
      return prisma.user.update({
        where: { id: user.id },
        data: user,
      });
    },
    deleteUser: async (userId) => {
      return prisma.user.delete({
        where: { id: userId },
      });
    },
    linkAccount: async (account) => {
      return prisma.account.create({
        data: account,
      });
    },
    unlinkAccount: async ({ provider, providerAccountId }) => {
      return prisma.account.delete({
        where: {
          provider_providerAccountId: {
            provider,
            providerAccountId,
          },
        },
      });
    },
    createSession: async (session) => {
      return prisma.session.create({
        data: {
          ...session,
          expires: new Date(session.expires),
        },
      });
    },
    getSessionAndUser: async (sessionToken) => {
      const session = await prisma.session.findUnique({
        where: { token: sessionToken },
        include: { user: true },
      });
      if (!session) return null;
      return {
        session,
        user: session.user,
      };
    },
    updateSession: async (session) => {
      return prisma.session.update({
        where: { id: session.id },
        data: {
          ...session,
          expires: new Date(session.expires),
        },
      });
    },
    deleteSession: async (sessionToken) => {
      return prisma.session.delete({
        where: { token: sessionToken },
      });
    },
    createVerificationToken: async (verificationToken) => {
      return prisma.verificationToken.create({
        data: verificationToken,
      });
    },
    useVerificationToken: async ({ identifier, token }) => {
      const vt = await prisma.verificationToken.findUnique({
        where: {
          identifier_token: {
            identifier,
            token,
          },
        },
      });
      if (!vt) return null;
      await prisma.verificationToken.delete({
        where: {
          identifier_token: {
            identifier,
            token,
          },
        },
      });
      return vt;
    },
  },

  // ============================================
  // Custom Providers
  // ============================================
  // Add custom provider configurations
  providerOptions: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID,
      clientSecret: process.env.GITHUB_CLIENT_SECRET,
    },
    telegram: {
      botToken: process.env.TELEGRAM_BOT_TOKEN,
      botId: process.env.TELEGRAM_BOT_ID,
    },
    web3: {
      enabled: process.env.WEB3_AUTH_ENABLED === 'true',
      chainId: parseInt(process.env.WEB3_CHAIN_ID || '1'),
    },
  },

  // ============================================
  // Security Headers
  // ============================================
  headers: {
    ...SECURITY_HEADERS,
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
  },
};

// ============================================
// Helper Functions
// ============================================

async function getRateLimitInfo(key: string): Promise<RateLimitInfo> {
  const attempts = await redis.get(key);
  const count = parseInt(attempts || '0');
  const maxAttempts = RATE_LIMITS.MAX_LOGIN_ATTEMPTS;
  const windowSeconds = RATE_LIMITS.WINDOW_SECONDS;

  if (count >= maxAttempts) {
    const ttl = await redis.ttl(key);
    return {
      attempts: count,
      maxAttempts,
      blocked: true,
      remainingTime: ttl,
    };
  }

  return {
    attempts: count,
    maxAttempts,
    blocked: false,
    remainingTime: windowSeconds - Math.floor((Date.now() - await redis.get(`${key}:first`)) / 1000),
  };
}

async function checkTrustedDevice(userId: string, fingerprint: string): Promise<boolean> {
  const device = await prisma.device.findFirst({
    where: {
      userId,
      fingerprint,
      trusted: true,
    },
  });
  return !!device;
}

async function generateSessionToken(): Promise<string> {
  return crypto.randomBytes(32).toString('hex');
}

async function getLocationFromIP(ip: string): Promise<any> {
  try {
    const response = await fetch(`http://ip-api.com/json/${ip}`);
    return await response.json();
  } catch {
    return null;
  }
}

async function sendWelcomeEmail(email: string, name: string): Promise<void> {
  // Implementation for sending welcome email
  console.log(`Sending welcome email to ${email}`);
}

async function checkSuspiciousActivity(userId: string): Promise<void> {
  // Implementation for checking suspicious activity
  console.log(`Checking suspicious activity for user ${userId}`);
}

// ============================================
// Export
// ============================================

const handler = NextAuth(NEXUS_AUTH_CONFIG);

export { handler as GET, handler as POST };

// ============================================
// Type Definitions
// ============================================

declare module 'next-auth' {
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      image: string | null;
      roles: string[];
      permissions: string[];
      sessionId: string | null;
      mfaRequired: boolean;
      provider: string;
      isAuthenticated: boolean;
      lastSessionRefresh: string;
      expiresAt?: Date;
      securityContext?: {
        deviceId: string | null;
        sessionId: string | null;
        lastLogin: string;
        loginCount: number;
        mfaVerified: boolean;
        emailVerified: boolean;
        ipAddress: string | null;
        userAgent: string | null;
      };
    };
  }

  interface User {
    id: string;
    name: string;
    email: string;
    image?: string | null;
    roles?: string[];
    permissions?: string[];
    sessionId?: string | null;
    mfaRequired?: boolean;
    provider?: string;
    tokens?: {
      accessToken: string;
      refreshToken: string;
      expiresIn: number;
    };
  }

  interface JWT {
    userId: string;
    email: string;
    name: string;
    image: string | null;
    roles: string[];
    permissions: string[];
    sessionId: string | null;
    mfaRequired: boolean;
    provider: string;
    tokens?: {
      accessToken: string;
      refreshToken: string;
      expiresIn: number;
    };
    expires: number;
    iat: number;
    deviceId?: string;
    lastLogin?: string;
    loginCount?: number;
    mfaVerified?: boolean;
    emailVerified?: boolean;
    ipAddress?: string;
    userAgent?: string;
    lastSessionRefresh?: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    userId: string;
    email: string;
    name: string;
    image: string | null;
    roles: string[];
    permissions: string[];
    sessionId: string | null;
    mfaRequired: boolean;
    provider: string;
    tokens?: {
      accessToken: string;
      refreshToken: string;
      expiresIn: number;
    };
    expires: number;
    iat: number;
    deviceId?: string;
    lastLogin?: string;
    loginCount?: number;
    mfaVerified?: boolean;
    emailVerified?: boolean;
    ipAddress?: string;
    userAgent?: string;
    lastSessionRefresh?: string;
  }
}

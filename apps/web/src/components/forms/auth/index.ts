// apps/web/src/components/forms/auth/index.ts

// ============================================================================
// EXPORTS PRINCIPAUX - FORMULAIRES D'AUTHENTIFICATION
// ============================================================================

// --- Formulaire de Connexion ---
export { default as LoginForm } from './LoginForm';
export type {
  LoginFormProps,
  LoginFormData,
  LoginStep,
} from './LoginForm';

// --- Formulaire d'Inscription ---
export { default as RegisterForm } from './RegisterForm';
export type {
  RegisterFormProps,
  RegisterFormData,
  RegisterStep,
} from './RegisterForm';

// --- Formulaire de Mot de Passe Oublié ---
export { default as ForgotPasswordForm } from './ForgotPasswordForm';
export type {
  ForgotPasswordFormProps,
  ForgotPasswordFormData,
  ForgotPasswordStep,
} from './ForgotPasswordForm';

// --- Formulaire de Réinitialisation du Mot de Passe ---
export { default as ResetPasswordForm } from './ResetPasswordForm';
export type {
  ResetPasswordFormProps,
  ResetPasswordFormData,
  ResetPasswordStep,
} from './ResetPasswordForm';

// --- Formulaire de Vérification d'Email ---
export { default as VerifyEmailForm } from './VerifyEmailForm';
export type {
  VerifyEmailFormProps,
  VerifyEmailFormData,
  VerifyEmailStep,
} from './VerifyEmailForm';

// --- Formulaire d'Authentification à Deux Facteurs (2FA) ---
export { default as TwoFactorForm } from './TwoFactorForm';
export type {
  TwoFactorFormProps,
  TwoFactorFormData,
  TwoFactorMethod,
  TwoFactorStep,
} from './TwoFactorForm';

// --- Formulaire de Profil Utilisateur ---
export { default as ProfileForm } from './ProfileForm';
export type {
  ProfileFormProps,
  ProfileFormData,
  ProfileTab,
} from './ProfileForm';

// ============================================================================
// EXPORTS DE TYPE - CONSTANTES ET UTILITAIRES
// ============================================================================

// --- Types Génériques pour l'Authentification ---
export type AuthFormVariant = 'default' | 'glass' | 'solid' | 'outlined';
export type AuthFormSize = 'sm' | 'md' | 'lg';
export type AuthFormStatus = 'idle' | 'loading' | 'success' | 'error' | 'locked';

// --- Interface de Base pour les Formulaires d'Auth ---
export interface BaseAuthFormProps {
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre du formulaire */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: AuthFormVariant;
  /** Taille du formulaire */
  size?: AuthFormSize;
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;
  /** Mode débogage */
  debug?: boolean;
}

// --- Configuration des Providers Sociaux ---
export type SocialProvider = 'google' | 'github' | 'apple' | 'facebook' | 'twitter' | 'linkedin' | 'microsoft';

export interface SocialProviderConfig {
  /** Identifiant du provider */
  id: SocialProvider;
  /** Nom affiché */
  name: string;
  /** Icône (composant React) */
  icon: React.ReactNode;
  /** Couleur du provider */
  color: string;
  /** URL de l'icône (fallback) */
  iconUrl?: string;
  /** Scopes requis */
  scopes?: string[];
}

// --- Configuration Sociale par Défaut ---
export const SOCIAL_PROVIDERS: Record<SocialProvider, SocialProviderConfig> = {
  google: {
    id: 'google',
    name: 'Google',
    color: '#4285F4',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
      </svg>
    ),
    scopes: ['profile', 'email'],
  },
  github: {
    id: 'github',
    name: 'GitHub',
    color: '#181717',
    icon: (
      <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.468-2.38 1.235-3.22-.123-.3-.535-1.52.117-3.16 0 0 1.008-.322 3.3 1.23.96-.267 1.98-.399 3-.399s2.04.132 3 .399c2.292-1.552 3.3-1.23 3.3-1.23.653 1.64.24 2.86.118 3.16.768.84 1.233 1.91 1.233 3.22 0 4.61-2.804 5.62-5.476 5.92.43.37.824 1.102.824 2.22 0 1.602-.015 2.894-.015 3.287 0 .322.216.694.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
      </svg>
    ),
    scopes: ['user:email', 'read:user'],
  },
  apple: {
    id: 'apple',
    name: 'Apple',
    color: '#000000',
    icon: (
      <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
      </svg>
    ),
    scopes: ['email', 'name'],
  },
  facebook: {
    id: 'facebook',
    name: 'Facebook',
    color: '#1877F2',
    icon: (
      <svg className="h-5 w-5" fill="#1877F2" viewBox="0 0 24 24">
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
      </svg>
    ),
    scopes: ['email', 'public_profile'],
  },
  twitter: {
    id: 'twitter',
    name: 'Twitter / X',
    color: '#1DA1F2',
    icon: (
      <svg className="h-5 w-5" fill="#1DA1F2" viewBox="0 0 24 24">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    ),
    scopes: ['users.read', 'tweet.read'],
  },
  linkedin: {
    id: 'linkedin',
    name: 'LinkedIn',
    color: '#0A66C2',
    icon: (
      <svg className="h-5 w-5" fill="#0A66C2" viewBox="0 0 24 24">
        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
      </svg>
    ),
    scopes: ['r_emailaddress', 'r_liteprofile'],
  },
  microsoft: {
    id: 'microsoft',
    name: 'Microsoft',
    color: '#00A4EF',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24">
        <rect x="1" y="1" width="10" height="10" fill="#F25022" />
        <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
        <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
        <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
      </svg>
    ),
    scopes: ['User.Read', 'email'],
  },
};

// ============================================================================
// UTILITAIRES - VÉRIFICATION DE SESSION
// ============================================================================

export const isAuthenticated = (): boolean => {
  if (typeof window === 'undefined') return false;
  
  try {
    const token = localStorage.getItem('nexus_auth_token');
    const user = localStorage.getItem('nexus_user');
    return !!(token && user);
  } catch {
    return false;
  }
};

export const getAuthToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  
  try {
    return localStorage.getItem('nexus_auth_token');
  } catch {
    return null;
  }
};

export const getAuthUser = (): any | null => {
  if (typeof window === 'undefined') return null;
  
  try {
    const user = localStorage.getItem('nexus_user');
    return user ? JSON.parse(user) : null;
  } catch {
    return null;
  }
};

export const clearAuthData = (): void => {
  if (typeof window === 'undefined') return;
  
  try {
    localStorage.removeItem('nexus_auth_token');
    localStorage.removeItem('nexus_user');
    localStorage.removeItem('nexus_refresh_token');
    sessionStorage.clear();
  } catch {
    // Ignorer les erreurs
  }
};

// ============================================================================
// HOOKS D'AUTHENTIFICATION (RE-EXPORTS)
// ============================================================================

// Ces hooks sont généralement importés depuis '@/hooks/useAuth'
// Mais nous les ré-exportons ici pour faciliter l'importation
export { useAuth } from '@/hooks/useAuth';
export { useSession } from '@/hooks/useSession';
export { usePermissions } from '@/hooks/usePermissions';
export { useTwoFactor } from '@/hooks/useTwoFactor';

// ============================================================================
// EXPORTATION PAR DÉFAUT - TOUS LES FORMULAIRES
// ============================================================================

/**
 * Exportation groupée de tous les formulaires d'authentification
 */
const AuthForms = {
  Login: LoginForm,
  Register: RegisterForm,
  ForgotPassword: ForgotPasswordForm,
  ResetPassword: ResetPasswordForm,
  VerifyEmail: VerifyEmailForm,
  TwoFactor: TwoFactorForm,
  Profile: ProfileForm,
};

export default AuthForms;

// ============================================================================
// TYPES DÉRIVÉS POUR UNE UTILISATION FACILE
// ============================================================================

/**
 * Type union de tous les noms de formulaires d'authentification
 */
export type AuthFormName = 
  | 'Login'
  | 'Register'
  | 'ForgotPassword'
  | 'ResetPassword'
  | 'VerifyEmail'
  | 'TwoFactor'
  | 'Profile';

/**
 * Mapping des props pour chaque formulaire d'authentification
 */
export interface AuthFormPropsMap {
  Login: LoginFormProps;
  Register: RegisterFormProps;
  ForgotPassword: ForgotPasswordFormProps;
  ResetPassword: ResetPasswordFormProps;
  VerifyEmail: VerifyEmailFormProps;
  TwoFactor: TwoFactorFormProps;
  Profile: ProfileFormProps;
}

/**
 * Type générique pour obtenir les props d'un formulaire spécifique
 */
export type AuthFormProps<T extends AuthFormName> = AuthFormPropsMap[T];

/**
 * Type générique pour les données d'un formulaire spécifique
 */
export type AuthFormDataMap = {
  Login: LoginFormData;
  Register: RegisterFormData;
  ForgotPassword: ForgotPasswordFormData;
  ResetPassword: ResetPasswordFormData;
  VerifyEmail: VerifyEmailFormData;
  TwoFactor: TwoFactorFormData;
  Profile: ProfileFormData;
};

export type AuthFormData<T extends AuthFormName> = AuthFormDataMap[T];

/**
 * Type générique pour les étapes d'un formulaire spécifique
 */
export type AuthFormStepMap = {
  Login: LoginStep;
  Register: RegisterStep;
  ForgotPassword: ForgotPasswordStep;
  ResetPassword: ResetPasswordStep;
  VerifyEmail: VerifyEmailStep;
  TwoFactor: TwoFactorStep;
  Profile: ProfileTab;
};

export type AuthFormStep<T extends AuthFormName> = AuthFormStepMap[T];

// ============================================================================
// CONFIGURATION DES ROUTES D'AUTHENTIFICATION
// ============================================================================

export const AUTH_ROUTES = {
  LOGIN: '/login',
  REGISTER: '/register',
  FORGOT_PASSWORD: '/forgot-password',
  RESET_PASSWORD: '/reset-password',
  VERIFY_EMAIL: '/verify-email',
  TWO_FACTOR: '/two-factor',
  PROFILE: '/profile',
  LOGOUT: '/logout',
} as const;

export type AuthRoute = typeof AUTH_ROUTES[keyof typeof AUTH_ROUTES];

// ============================================================================
// MESSAGES D'ERREUR STANDARDISÉS
// ============================================================================

export const AUTH_ERROR_MESSAGES = {
  // Général
  UNKNOWN: 'Une erreur inattendue est survenue',
  NETWORK: 'Erreur réseau. Veuillez vérifier votre connexion',
  TIMEOUT: 'La requête a expiré. Veuillez réessayer',
  
  // Connexion
  INVALID_CREDENTIALS: 'Email ou mot de passe incorrect',
  ACCOUNT_LOCKED: 'Compte verrouillé. Veuillez réessayer plus tard',
  ACCOUNT_DISABLED: 'Ce compte a été désactivé',
  TOO_MANY_ATTEMPTS: 'Trop de tentatives. Veuillez réessayer plus tard',
  
  // Inscription
  EMAIL_TAKEN: 'Cette adresse email est déjà utilisée',
  USERNAME_TAKEN: 'Ce nom d\'utilisateur est déjà pris',
  INVALID_EMAIL: 'Veuillez entrer une adresse email valide',
  WEAK_PASSWORD: 'Le mot de passe est trop faible',
  PASSWORDS_DONT_MATCH: 'Les mots de passe ne correspondent pas',
  
  // Réinitialisation
  INVALID_TOKEN: 'Token de réinitialisation invalide ou expiré',
  RESET_FAILED: 'La réinitialisation du mot de passe a échoué',
  
  // 2FA
  INVALID_2FA_CODE: 'Code 2FA invalide',
  EXPIRED_2FA_CODE: 'Code 2FA expiré',
  INVALID_RECOVERY_CODE: 'Code de récupération invalide',
  
  // Email
  EMAIL_NOT_VERIFIED: 'Veuillez vérifier votre adresse email',
  VERIFICATION_CODE_INVALID: 'Code de vérification invalide',
  VERIFICATION_CODE_EXPIRED: 'Le code de vérification a expiré',
  
  // Session
  SESSION_EXPIRED: 'Votre session a expiré. Veuillez vous reconnecter',
  UNAUTHORIZED: 'Vous n\'êtes pas autorisé à effectuer cette action',
} as const;

// ============================================================================
// MESSAGES DE SUCCÈS STANDARDISÉS
// ============================================================================

export const AUTH_SUCCESS_MESSAGES = {
  LOGIN: 'Connexion réussie ! Bienvenue sur Nexus Trading IA',
  REGISTER: 'Inscription réussie ! Bienvenue sur Nexus Trading IA',
  LOGOUT: 'Déconnexion réussie',
  PASSWORD_RESET: 'Mot de passe réinitialisé avec succès',
  PASSWORD_RESET_EMAIL: 'Un email de réinitialisation vous a été envoyé',
  EMAIL_VERIFIED: 'Email vérifié avec succès',
  EMAIL_VERIFICATION_SENT: 'Un email de vérification vous a été envoyé',
  TWO_FACTOR_ENABLED: 'Authentification à deux facteurs activée',
  TWO_FACTOR_DISABLED: 'Authentification à deux facteurs désactivée',
  PROFILE_UPDATED: 'Profil mis à jour avec succès',
} as const;

// ============================================================================
// EXPORTATION DES VALIDATEURS
// ============================================================================

export * from '../validators/authValidators';

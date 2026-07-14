// apps/web/src/components/forms/layouts/index.ts

// ============================================================================
// EXPORTS PRINCIPAUX - LAYOUTS DE FORMULAIRE
// ============================================================================

// --- Layout de carte ---
export { default as FormCardLayout } from './FormCardLayout';
export { FormCardSection } from './FormCardLayout';
export type {
  FormCardLayoutProps,
  FormCardSection as FormCardSectionType,
  FormCardVariant,
  FormCardSize,
  FormCardStatus,
  FormCardAlignment,
  FormCardActionPosition,
} from './FormCardLayout';

// --- Layout de formulaire ---
export { default as FormLayout } from './FormLayout';
export {
  FormField,
  FormActions,
  FormGroup,
} from './FormLayout';
export type {
  FormLayoutProps,
  FormLayoutVariant,
  FormLayoutSize,
  FormLayoutGap,
  FormLayoutAlign,
  FormLayoutJustify,
  FormLayoutWrap,
  FormLayoutColumns,
} from './FormLayout';

// --- Layout de modale ---
export { default as FormModalLayout } from './FormModalLayout';
export { FormModalSection } from './FormModalLayout';
export type {
  FormModalLayoutProps,
  FormModalSection as FormModalSectionType,
  FormModalSize,
  FormModalVariant,
  FormModalStatus,
  FormModalAnimation,
  FormModalPosition,
  FormModalBackdrop,
} from './FormModalLayout';

// --- Layout de panneau ---
export { default as FormPanelLayout } from './FormPanelLayout';
export { FormPanelSection } from './FormPanelLayout';
export type {
  FormPanelLayoutProps,
  FormPanelSection as FormPanelSectionType,
  FormPanelSide,
  FormPanelSize,
  FormPanelVariant,
  FormPanelStatus,
  FormPanelAnimation,
  FormPanelBackdrop,
  FormPanelMode,
} from './FormPanelLayout';

// --- Layout de barre latérale ---
export { default as FormSidebarLayout } from './FormSidebarLayout';
export {
  FormSidebarSection,
  FormSidebarItem,
} from './FormSidebarLayout';
export type {
  FormSidebarLayoutProps,
  FormSidebarSection as FormSidebarSectionType,
  FormSidebarItem as FormSidebarItemType,
  FormSidebarSize,
  FormSidebarVariant,
  FormSidebarStatus,
  FormSidebarAnimation,
  FormSidebarBackdrop,
  FormSidebarMode,
  FormSidebarPosition,
} from './FormSidebarLayout';

// --- Layout d'onglets ---
export { default as FormTabsLayout } from './FormTabsLayout';
export {
  FormTab,
  FormTabPanel,
} from './FormTabsLayout';
export type {
  FormTabsLayoutProps,
  FormTab as FormTabType,
  FormTabsVariant,
  FormTabsSize,
  FormTabsAlignment,
  FormTabsPosition,
  FormTabsStatus,
  FormTabsAnimation,
} from './FormTabsLayout';

// --- Layout de wizard ---
export { default as FormWizardLayout } from './FormWizardLayout';
export {
  WizardStep,
  WizardContent,
} from './FormWizardLayout';
export type {
  FormWizardLayoutProps,
  WizardStep as WizardStepType,
  WizardVariant,
  WizardSize,
  WizardStatus,
  WizardAnimation,
  WizardNavigation,
  WizardStepDisplay,
} from './FormWizardLayout';

// ============================================================================
// EXPORTS DE TYPE - TYPES GÉNÉRIQUES
// ============================================================================

export type FormLayoutName = 
  | 'FormCardLayout'
  | 'FormLayout'
  | 'FormModalLayout'
  | 'FormPanelLayout'
  | 'FormSidebarLayout'
  | 'FormTabsLayout'
  | 'FormWizardLayout';

export type FormLayoutPropsMap = {
  FormCardLayout: FormCardLayoutProps;
  FormLayout: FormLayoutProps;
  FormModalLayout: FormModalLayoutProps;
  FormPanelLayout: FormPanelLayoutProps;
  FormSidebarLayout: FormSidebarLayoutProps;
  FormTabsLayout: FormTabsLayoutProps;
  FormWizardLayout: FormWizardLayoutProps;
};

/**
 * Type générique pour obtenir les props d'un layout spécifique
 */
export type FormLayoutProps<T extends FormLayoutName> = FormLayoutPropsMap[T];

// ============================================================================
// CONSTANTES - CONFIGURATIONS PAR DÉFAUT
// ============================================================================

export const DEFAULT_LAYOUT_CONFIG = {
  // Variantes par défaut
  cardVariant: 'default' as FormCardVariant,
  layoutVariant: 'vertical' as FormLayoutVariant,
  modalVariant: 'default' as FormModalVariant,
  panelVariant: 'default' as FormPanelVariant,
  sidebarVariant: 'default' as FormSidebarVariant,
  tabsVariant: 'default' as FormTabsVariant,
  wizardVariant: 'default' as WizardVariant,

  // Tailles par défaut
  cardSize: 'md' as FormCardSize,
  layoutSize: 'md' as FormLayoutSize,
  modalSize: 'md' as FormModalSize,
  panelSize: 'md' as FormPanelSize,
  sidebarSize: 'md' as FormSidebarSize,
  tabsSize: 'md' as FormTabsSize,
  wizardSize: 'md' as WizardSize,

  // Positions par défaut
  panelSide: 'right' as FormPanelSide,
  sidebarPosition: 'right' as FormSidebarPosition,
  tabsPosition: 'top' as FormTabsPosition,
  wizardNavigation: 'bottom' as WizardNavigation,

  // Animations par défaut
  modalAnimation: 'scale' as FormModalAnimation,
  panelAnimation: 'slide' as FormPanelAnimation,
  sidebarAnimation: 'slide' as FormSidebarAnimation,
  tabsAnimation: 'fade' as FormTabsAnimation,
  wizardAnimation: 'slide' as WizardAnimation,
} as const;

// ============================================================================
// UTILITAIRES - CRÉATEURS DE LAYOUTS
// ============================================================================

import React from 'react';
import { FormCardLayout } from './FormCardLayout';
import { FormLayout } from './FormLayout';
import { FormModalLayout } from './FormModalLayout';
import { FormPanelLayout } from './FormPanelLayout';
import { FormSidebarLayout } from './FormSidebarLayout';
import { FormTabsLayout } from './FormTabsLayout';
import { FormWizardLayout } from './FormWizardLayout';

/**
 * Créer un layout de carte personnalisé
 */
export const createCardLayout = <T extends FormCardLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormCardLayout {...defaultProps} {...props} />;
  };
};

/**
 * Créer un layout de formulaire personnalisé
 */
export const createFormLayout = <T extends FormLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormLayout {...defaultProps} {...props} />;
  };
};

/**
 * Créer un layout de modale personnalisé
 */
export const createModalLayout = <T extends FormModalLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormModalLayout {...defaultProps} {...props} />;
  };
};

/**
 * Créer un layout de panneau personnalisé
 */
export const createPanelLayout = <T extends FormPanelLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormPanelLayout {...defaultProps} {...props} />;
  };
};

/**
 * Créer un layout de barre latérale personnalisé
 */
export const createSidebarLayout = <T extends FormSidebarLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormSidebarLayout {...defaultProps} {...props} />;
  };
};

/**
 * Créer un layout d'onglets personnalisé
 */
export const createTabsLayout = <T extends FormTabsLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormTabsLayout {...defaultProps} {...props} />;
  };
};

/**
 * Créer un layout de wizard personnalisé
 */
export const createWizardLayout = <T extends FormWizardLayoutProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <FormWizardLayout {...defaultProps} {...props} />;
  };
};

// ============================================================================
// UTILITAIRES - COMBINAISON DE LAYOUTS
// ============================================================================

/**
 * Combiner un layout de carte avec un layout de formulaire
 */
export const CardFormLayout: React.FC<FormCardLayoutProps & FormLayoutProps> = ({
  children,
  ...props
}) => {
  const { cardProps, formProps } = props as any;
  return (
    <FormCardLayout {...cardProps}>
      <FormLayout {...formProps}>
        {children}
      </FormLayout>
    </FormCardLayout>
  );
};

/**
 * Combiner un layout de modale avec un layout de formulaire
 */
export const ModalFormLayout: React.FC<FormModalLayoutProps & FormLayoutProps> = ({
  children,
  ...props
}) => {
  const { modalProps, formProps } = props as any;
  return (
    <FormModalLayout {...modalProps}>
      <FormLayout {...formProps}>
        {children}
      </FormLayout>
    </FormModalLayout>
  );
};

/**
 * Combiner un layout de panneau avec un layout de formulaire
 */
export const PanelFormLayout: React.FC<FormPanelLayoutProps & FormLayoutProps> = ({
  children,
  ...props
}) => {
  const { panelProps, formProps } = props as any;
  return (
    <FormPanelLayout {...panelProps}>
      <FormLayout {...formProps}>
        {children}
      </FormLayout>
    </FormPanelLayout>
  );
};

/**
 * Combiner un layout de sidebar avec un layout de formulaire
 */
export const SidebarFormLayout: React.FC<FormSidebarLayoutProps & FormLayoutProps> = ({
  children,
  ...props
}) => {
  const { sidebarProps, formProps } = props as any;
  return (
    <FormSidebarLayout {...sidebarProps}>
      <FormLayout {...formProps}>
        {children}
      </FormLayout>
    </FormSidebarLayout>
  );
};

/**
 * Combiner un layout d'onglets avec un layout de formulaire
 */
export const TabsFormLayout: React.FC<FormTabsLayoutProps & FormLayoutProps> = ({
  children,
  ...props
}) => {
  const { tabsProps, formProps } = props as any;
  return (
    <FormTabsLayout {...tabsProps}>
      <FormLayout {...formProps}>
        {children}
      </FormLayout>
    </FormTabsLayout>
  );
};

/**
 * Combiner un layout de wizard avec un layout de formulaire
 */
export const WizardFormLayout: React.FC<FormWizardLayoutProps & FormLayoutProps> = ({
  children,
  ...props
}) => {
  const { wizardProps, formProps } = props as any;
  return (
    <FormWizardLayout {...wizardProps}>
      <FormLayout {...formProps}>
        {children}
      </FormLayout>
    </FormWizardLayout>
  );
};

// ============================================================================
// UTILITAIRES - SÉLECTION DE LAYOUT
// ============================================================================

export type LayoutSelectorProps = {
  /** Type de layout à utiliser */
  type: FormLayoutName;
  /** Props du layout */
  props: any;
  /** Enfants */
  children: React.ReactNode;
};

export const LayoutSelector: React.FC<LayoutSelectorProps> = ({
  type,
  props,
  children,
}) => {
  switch (type) {
    case 'FormCardLayout':
      return <FormCardLayout {...props}>{children}</FormCardLayout>;
    case 'FormLayout':
      return <FormLayout {...props}>{children}</FormLayout>;
    case 'FormModalLayout':
      return <FormModalLayout {...props}>{children}</FormModalLayout>;
    case 'FormPanelLayout':
      return <FormPanelLayout {...props}>{children}</FormPanelLayout>;
    case 'FormSidebarLayout':
      return <FormSidebarLayout {...props}>{children}</FormSidebarLayout>;
    case 'FormTabsLayout':
      return <FormTabsLayout {...props}>{children}</FormTabsLayout>;
    case 'FormWizardLayout':
      return <FormWizardLayout {...props}>{children}</FormWizardLayout>;
    default:
      return <FormLayout {...props}>{children}</FormLayout>;
  }
};

// ============================================================================
// EXPORTATION PAR DÉFAUT - TOUS LES LAYOUTS
// ============================================================================

/**
 * Exportation groupée de tous les layouts de formulaire
 */
const FormLayouts = {
  Card: FormCardLayout,
  Layout: FormLayout,
  Modal: FormModalLayout,
  Panel: FormPanelLayout,
  Sidebar: FormSidebarLayout,
  Tabs: FormTabsLayout,
  Wizard: FormWizardLayout,
  // Utilitaires
  CardFormLayout,
  ModalFormLayout,
  PanelFormLayout,
  SidebarFormLayout,
  TabsFormLayout,
  WizardFormLayout,
  LayoutSelector,
  // Créateurs
  createCardLayout,
  createFormLayout,
  createModalLayout,
  createPanelLayout,
  createSidebarLayout,
  createTabsLayout,
  createWizardLayout,
};

export default FormLayouts;

// ============================================================================
// TYPES DÉRIVÉS POUR UNE UTILISATION FACILE
// ============================================================================

/**
 * Type pour un layout générique
 */
export type AnyFormLayout = React.ComponentType<any>;

/**
 * Type pour un layout avec ses props
 */
export type LayoutWithProps<T extends AnyFormLayout> = {
  component: T;
  props: React.ComponentProps<T>;
};

/**
 * Type pour une collection de layouts
 */
export type LayoutCollection = {
  [K in FormLayoutName]: React.ComponentType<FormLayoutPropsMap[K]>;
};

// ============================================================================
// UTILITAIRES - GESTION DES LAYOUTS
// ============================================================================

export const getLayoutComponent = (
  type: FormLayoutName
): React.ComponentType<any> => {
  const map: Record<FormLayoutName, React.ComponentType<any>> = {
    FormCardLayout,
    FormLayout,
    FormModalLayout,
    FormPanelLayout,
    FormSidebarLayout,
    FormTabsLayout,
    FormWizardLayout,
  };
  return map[type] || FormLayout;
};

export const getLayoutDefaultProps = (
  type: FormLayoutName
): Partial<any> => {
  const map: Record<FormLayoutName, Partial<any>> = {
    FormCardLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.cardVariant,
      size: DEFAULT_LAYOUT_CONFIG.cardSize,
    },
    FormLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.layoutVariant,
      size: DEFAULT_LAYOUT_CONFIG.layoutSize,
    },
    FormModalLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.modalVariant,
      size: DEFAULT_LAYOUT_CONFIG.modalSize,
      animation: DEFAULT_LAYOUT_CONFIG.modalAnimation,
    },
    FormPanelLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.panelVariant,
      size: DEFAULT_LAYOUT_CONFIG.panelSize,
      side: DEFAULT_LAYOUT_CONFIG.panelSide,
      animation: DEFAULT_LAYOUT_CONFIG.panelAnimation,
    },
    FormSidebarLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.sidebarVariant,
      size: DEFAULT_LAYOUT_CONFIG.sidebarSize,
      position: DEFAULT_LAYOUT_CONFIG.sidebarPosition,
      animation: DEFAULT_LAYOUT_CONFIG.sidebarAnimation,
    },
    FormTabsLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.tabsVariant,
      size: DEFAULT_LAYOUT_CONFIG.tabsSize,
      position: DEFAULT_LAYOUT_CONFIG.tabsPosition,
      animation: DEFAULT_LAYOUT_CONFIG.tabsAnimation,
    },
    FormWizardLayout: {
      variant: DEFAULT_LAYOUT_CONFIG.wizardVariant,
      size: DEFAULT_LAYOUT_CONFIG.wizardSize,
      navigation: DEFAULT_LAYOUT_CONFIG.wizardNavigation,
      animation: DEFAULT_LAYOUT_CONFIG.wizardAnimation,
    },
  };
  return map[type] || {};
};

// ============================================================================
// EXPORTATION DES TYPES DE CONFIGURATION
// ============================================================================

export type {
  FormCardLayoutProps,
  FormCardVariant,
  FormCardSize,
  FormCardStatus,
  FormCardAlignment,
  FormCardActionPosition,
} from './FormCardLayout';

export type {
  FormLayoutProps,
  FormLayoutVariant,
  FormLayoutSize,
  FormLayoutGap,
  FormLayoutAlign,
  FormLayoutJustify,
  FormLayoutWrap,
  FormLayoutColumns,
} from './FormLayout';

export type {
  FormModalLayoutProps,
  FormModalSize,
  FormModalVariant,
  FormModalStatus,
  FormModalAnimation,
  FormModalPosition,
  FormModalBackdrop,
} from './FormModalLayout';

export type {
  FormPanelLayoutProps,
  FormPanelSide,
  FormPanelSize,
  FormPanelVariant,
  FormPanelStatus,
  FormPanelAnimation,
  FormPanelBackdrop,
  FormPanelMode,
} from './FormPanelLayout';

export type {
  FormSidebarLayoutProps,
  FormSidebarSize,
  FormSidebarVariant,
  FormSidebarStatus,
  FormSidebarAnimation,
  FormSidebarBackdrop,
  FormSidebarMode,
  FormSidebarPosition,
} from './FormSidebarLayout';

export type {
  FormTabsLayoutProps,
  FormTabsVariant,
  FormTabsSize,
  FormTabsAlignment,
  FormTabsPosition,
  FormTabsStatus,
  FormTabsAnimation,
} from './FormTabsLayout';

export type {
  FormWizardLayoutProps,
  WizardVariant,
  WizardSize,
  WizardStatus,
  WizardAnimation,
  WizardNavigation,
  WizardStepDisplay,
} from './FormWizardLayout';

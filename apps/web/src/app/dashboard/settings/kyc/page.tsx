/**
 * NEXUS AI TRADING SYSTEM - KYC Verification Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page handles Know Your Customer (KYC) verification including:
 * - Personal information verification
 - Identity document upload and verification
 * - Address proof verification
 * - Face verification / Liveness detection
 * - KYC status tracking
 * - Compliance with regulatory requirements
 * - Document management and storage
 * - Verification history
 * - Re-verification requests
 * - Multi-tier KYC levels
 * - Automated document processing
 * - Manual review support
 * - Security and privacy protection
 * - Audit trail logging
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';
import { Avatar } from '@/components/ui/Avatar';

// Icons
import {
  Shield,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Upload,
  Camera,
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  Building,
  FileText,
  IdCard,
  Passport,
  CreditCard,
  Home,
  TrendingUp,
  Award,
  Lock,
  Eye,
  EyeOff,
  Download,
  RefreshCw,
  Plus,
  Trash2,
  Edit,
  Save,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Crown,
  Star,
  Info,
  HelpCircle,
  Globe,
  ShieldCheck,
  Fingerprint,
  Scan,
  Users,
  Briefcase,
  DollarSign,
  Landmark,
  MailCheck,
  PhoneCheck,
} from 'lucide-react';

// Types
import type {
  KYCStatus,
  KYCDocument,
  KYCVerification,
  KYCLevel,
  KYCRequirement,
  KYCUserInfo,
  KYCDocumentType,
  KYCReview,
} from '@/types/kyc';

// Constants
import {
  KYC_LEVELS,
  KYC_DOCUMENT_TYPES,
  KYC_STATUSES,
  KYC_REQUIREMENTS,
  KYC_COUNTRIES,
  KYC_ID_TYPES,
  KYC_ADDRESS_TYPES,
  MAX_FILE_SIZE,
  ALLOWED_FILE_TYPES,
  DOCUMENT_EXPIRY_WARNING_DAYS,
} from '@/constants/kyc';

// Utils
import { formatDate, formatCurrency, formatNumber } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function KYCPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // State - KYC Status
  const [kycStatus, setKycStatus] = useState<KYCStatus | null>(null);
  const [kycLevel, setKycLevel] = useState<KYCLevel | null>(null);
  const [kycRequirements, setKycRequirements] = useState<KYCRequirement[]>([]);
  const [kycLoading, setKycLoading] = useState<boolean>(true);

  // State - User Info
  const [userInfo, setUserInfo] = useState<KYCUserInfo>({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    dateOfBirth: '',
    nationality: '',
    countryOfResidence: '',
    address: '',
    city: '',
    state: '',
    postalCode: '',
    occupation: '',
    sourceOfFunds: '',
    taxId: '',
  });
  const [userInfoLoading, setUserInfoLoading] = useState<boolean>(true);

  // State - Documents
  const [documents, setDocuments] = useState<KYCDocument[]>([]);
  const [documentTypes, setDocumentTypes] = useState<KYCRequirement[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState<boolean>(true);
  const [uploadingDocument, setUploadingDocument] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [selectedDocumentType, setSelectedDocumentType] = useState<KYCDocumentType | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentPreview, setDocumentPreview] = useState<string | null>(null);

  // State - Verification
  const [verificationHistory, setVerificationHistory] = useState<KYCVerification[]>([]);
  const [pendingReviews, setPendingReviews] = useState<KYCReview[]>([]);
  const [verificationLoading, setVerificationLoading] = useState<boolean>(true);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [showDocumentModal, setShowDocumentModal] = useState<boolean>(false);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [showRejectReasonModal, setShowRejectReasonModal] = useState<boolean>(false);
  const [rejectReason, setRejectReason] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isResubmitting, setIsResubmitting] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/dashboard/settings/kyc');
    } else {
      fetchAllData();
    }
  }, [isAuthenticated, router]);

  // ============================================
  // API Calls
  // ============================================

  const fetchKYCStatus = useCallback(async () => {
    try {
      const response = await api.get('/kyc/status');
      if (response.data) {
        setKycStatus(response.data.status);
        setKycLevel(response.data.level);
        setKycRequirements(response.data.requirements || []);
      }
    } catch (error) {
      console.error('Failed to fetch KYC status:', error);
    }
  }, [api]);

  const fetchUserInfo = useCallback(async () => {
    try {
      setUserInfoLoading(true);
      const response = await api.get('/kyc/user-info');
      if (response.data) {
        setUserInfo(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch user info:', error);
    } finally {
      setUserInfoLoading(false);
    }
  }, [api]);

  const fetchDocuments = useCallback(async () => {
    try {
      setDocumentsLoading(true);
      const response = await api.get('/kyc/documents');
      if (response.data) {
        setDocuments(response.data.documents || []);
        setDocumentTypes(response.data.requiredTypes || []);
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setDocumentsLoading(false);
    }
  }, [api]);

  const fetchVerificationHistory = useCallback(async () => {
    try {
      setVerificationLoading(true);
      const response = await api.get('/kyc/history');
      if (response.data) {
        setVerificationHistory(response.data.history || []);
        setPendingReviews(response.data.pendingReviews || []);
      }
    } catch (error) {
      console.error('Failed to fetch verification history:', error);
    } finally {
      setVerificationLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchKYCStatus(),
        fetchUserInfo(),
        fetchDocuments(),
        fetchVerificationHistory(),
      ]);
    } catch (error) {
      console.error('Failed to fetch KYC data:', error);
      setShowToast({
        message: 'Failed to load KYC data. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [fetchKYCStatus, fetchUserInfo, fetchDocuments, fetchVerificationHistory]);

  // ============================================
  // Handlers - User Info
  // ============================================

  const handleUserInfoChange = useCallback((field: string, value: string) => {
    setUserInfo(prev => ({ ...prev, [field]: value }));
  }, []);

  const handleSubmitUserInfo = useCallback(async () => {
    // Validate required fields
    const requiredFields = ['firstName', 'lastName', 'email', 'phone', 'dateOfBirth', 'nationality', 'countryOfResidence', 'address'];
    const missingFields = requiredFields.filter(field => !userInfo[field as keyof KYCUserInfo]);
    
    if (missingFields.length > 0) {
      setShowToast({
        message: `Please fill in all required fields: ${missingFields.join(', ')}`,
        type: 'warning',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await api.put('/kyc/user-info', userInfo);
      if (response.data) {
        setShowToast({
          message: 'Personal information updated successfully!',
          type: 'success',
        });
        await fetchUserInfo();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update personal information.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, userInfo]);

  // ============================================
  // Handlers - Documents
  // ============================================

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      setShowToast({
        message: `File size exceeds limit of ${MAX_FILE_SIZE / 1024 / 1024}MB`,
        type: 'error',
      });
      return;
    }

    // Validate file type
    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      setShowToast({
        message: `File type not allowed. Please upload: ${ALLOWED_FILE_TYPES.join(', ')}`,
        type: 'error',
      });
      return;
    }

    setSelectedFile(file);
    const preview = URL.createObjectURL(file);
    setDocumentPreview(preview);
  }, []);

  const handleUploadDocument = useCallback(async () => {
    if (!selectedFile || !selectedDocumentType) {
      setShowToast({
        message: 'Please select a document type and file.',
        type: 'warning',
      });
      return;
    }

    setUploadingDocument(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('document', selectedFile);
      formData.append('type', selectedDocumentType.id);
      formData.append('metadata', JSON.stringify({
        fileName: selectedFile.name,
        fileSize: selectedFile.size,
        fileType: selectedFile.type,
        uploadDate: new Date().toISOString(),
      }));

      const response = await api.post('/kyc/documents', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
          setUploadProgress(progress);
        },
      });

      if (response.data) {
        setDocuments(prev => [response.data.document, ...prev]);
        setShowDocumentModal(false);
        setSelectedFile(null);
        setDocumentPreview(null);
        setSelectedDocumentType(null);
        setShowToast({
          message: 'Document uploaded successfully!',
          type: 'success',
        });
        await fetchKYCStatus();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to upload document.',
        type: 'error',
      });
    } finally {
      setUploadingDocument(false);
      setUploadProgress(0);
    }
  }, [api, selectedFile, selectedDocumentType]);

  const handleDeleteDocument = useCallback(async (documentId: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await api.delete(`/kyc/documents/${documentId}`);
      setDocuments(prev => prev.filter(doc => doc.id !== documentId));
      setShowToast({
        message: 'Document deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete document.',
        type: 'error',
      });
    }
  }, [api]);

  const handleStartCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (cameraRef.current) {
        cameraRef.current.srcObject = stream;
        await cameraRef.current.play();
      }
    } catch (error) {
      setShowToast({
        message: 'Unable to access camera. Please check permissions.',
        type: 'error',
      });
    }
  }, []);

  const handleCapturePhoto = useCallback(() => {
    if (cameraRef.current && canvasRef.current) {
      const context = canvasRef.current.getContext('2d');
      canvasRef.current.width = cameraRef.current.videoWidth;
      canvasRef.current.height = cameraRef.current.videoHeight;
      context?.drawImage(cameraRef.current, 0, 0);
      const dataUrl = canvasRef.current.toDataURL('image/jpeg');
      
      // Convert data URL to file
      fetch(dataUrl)
        .then(res => res.blob())
        .then(blob => {
          const file = new File([blob], 'camera-capture.jpg', { type: 'image/jpeg' });
          setSelectedFile(file);
          setDocumentPreview(dataUrl);
          
          // Stop camera stream
          const stream = cameraRef.current?.srcObject as MediaStream;
          stream?.getTracks().forEach(track => track.stop());
        });
    }
  }, []);

  // ============================================
  // Handlers - Verification
  // ============================================

  const handleSubmitForVerification = useCallback(async () => {
    setShowConfirmModal(true);
  }, []);

  const handleConfirmVerification = useCallback(async () => {
    setIsResubmitting(true);
    try {
      const response = await api.post('/kyc/submit');
      if (response.data) {
        setShowToast({
          message: 'KYC verification submitted successfully! Please wait for review.',
          type: 'success',
        });
        setShowConfirmModal(false);
        await fetchKYCStatus();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to submit for verification.',
        type: 'error',
      });
    } finally {
      setIsResubmitting(false);
    }
  }, [api]);

  const handleResubmit = useCallback(async () => {
    await handleConfirmVerification();
  }, [handleConfirmVerification]);

  const handleRejectReasonSubmit = useCallback(async () => {
    if (!rejectReason.trim()) {
      setShowToast({
        message: 'Please provide a reason for rejection.',
        type: 'warning',
      });
      return;
    }

    try {
      await api.post('/kyc/reject', { reason: rejectReason });
      setShowToast({
        message: 'KYC verification rejected. You can resubmit after addressing the issues.',
        type: 'info',
      });
      setShowRejectReasonModal(false);
      setRejectReason('');
      await fetchKYCStatus();
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to reject verification.',
        type: 'error',
      });
    }
  }, [api, rejectReason]);

  // ============================================
  // Memoized Computations
  // ============================================

  const isDocumentRequired = useCallback((type: string) => {
    return documentTypes.some(dt => dt.id === type && dt.required);
  }, [documentTypes]);

  const hasAllRequiredDocuments = useCallback(() => {
    const requiredTypes = documentTypes.filter(dt => dt.required).map(dt => dt.id);
    const uploadedTypes = documents.filter(doc => doc.status === 'approved' || doc.status === 'pending').map(doc => doc.type);
    return requiredTypes.every(type => uploadedTypes.includes(type));
  }, [documentTypes, documents]);

  const getDocumentStatusBadge = (status: string) => {
    const badges: Record<string, { color: string; label: string }> = {
      pending: { color: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30', label: 'Pending' },
      approved: { color: 'bg-green-500/20 text-green-500 border-green-500/30', label: 'Approved' },
      rejected: { color: 'bg-red-500/20 text-red-500 border-red-500/30', label: 'Rejected' },
      expired: { color: 'bg-orange-500/20 text-orange-500 border-orange-500/30', label: 'Expired' },
    };
    return badges[status] || badges.pending;
  };

  const getKYCLevelBadge = (level: string) => {
    const levels: Record<string, { color: string; label: string; icon: any }> = {
      basic: { color: 'bg-gray-500/20 text-gray-400', label: 'Basic', icon: User },
      verified: { color: 'bg-green-500/20 text-green-500', label: 'Verified', icon: CheckCircle },
      advanced: { color: 'bg-blue-500/20 text-blue-500', label: 'Advanced', icon: Shield },
      pro: { color: 'bg-purple-500/20 text-purple-500', label: 'Pro', icon: Crown },
      enterprise: { color: 'bg-yellow-500/20 text-yellow-500', label: 'Enterprise', icon: Star },
    };
    return levels[level] || levels.basic;
  };

  const kycProgress = useMemo(() => {
    const total = documentTypes.length;
    const completed = documents.filter(doc => doc.status === 'approved').length;
    return total > 0 ? (completed / total) * 100 : 0;
  }, [documentTypes, documents]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && kycLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading KYC...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your verification status</p>
        </div>
      </div>
    );
  }

  const kycLevelData = getKYCLevelBadge(kycLevel?.id || 'basic');

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 md:p-6 lg:p-8">
      {/* ============================================ */}
      {/* HEADER */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="text-3xl">🛡️</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                KYC Verification
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Verify your identity to unlock all trading features
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* KYC Level */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <kycLevelData.icon className={cn("w-4 h-4", kycLevelData.color)} />
            <span className={cn("text-sm font-medium", kycLevelData.color)}>
              {kycLevelData.label}
            </span>
          </div>

          {/* KYC Status */}
          {kycStatus && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
              {kycStatus.status === 'verified' && <CheckCircle className="w-4 h-4 text-green-500" />}
              {kycStatus.status === 'pending' && <Clock className="w-4 h-4 text-yellow-500" />}
              {kycStatus.status === 'rejected' && <XCircle className="w-4 h-4 text-red-500" />}
              {kycStatus.status === 'not_started' && <AlertCircle className="w-4 h-4 text-gray-400" />}
              <span className={cn(
                "text-sm font-medium",
                kycStatus.status === 'verified' ? 'text-green-500' :
                kycStatus.status === 'pending' ? 'text-yellow-500' :
                kycStatus.status === 'rejected' ? 'text-red-500' :
                'text-gray-400'
              )}>
                {kycStatus.status?.toUpperCase().replace('_', ' ')}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* KYC STATUS CARD */}
      {/* ============================================ */}
      {kycStatus && (
        <Card className="p-6 bg-gray-800 border-gray-700 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className={cn(
                "w-16 h-16 rounded-full flex items-center justify-center",
                kycStatus.status === 'verified' ? 'bg-green-500/20' :
                kycStatus.status === 'pending' ? 'bg-yellow-500/20' :
                kycStatus.status === 'rejected' ? 'bg-red-500/20' :
                'bg-gray-500/20'
              )}>
                {kycStatus.status === 'verified' && <CheckCircle className="w-8 h-8 text-green-500" />}
                {kycStatus.status === 'pending' && <Clock className="w-8 h-8 text-yellow-500" />}
                {kycStatus.status === 'rejected' && <XCircle className="w-8 h-8 text-red-500" />}
                {kycStatus.status === 'not_started' && <Shield className="w-8 h-8 text-gray-400" />}
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">
                  {kycStatus.status === 'verified' ? 'Identity Verified' :
                   kycStatus.status === 'pending' ? 'Verification in Progress' :
                   kycStatus.status === 'rejected' ? 'Verification Rejected' :
                   'Start Your Verification'}
                </h2>
                <p className="text-sm text-gray-400">
                  {kycStatus.status === 'verified' ? 'Your identity has been successfully verified.' :
                   kycStatus.status === 'pending' ? 'Your documents are being reviewed by our team.' :
                   kycStatus.status === 'rejected' ? 'Please review the issues and resubmit your documents.' :
                   'Complete the verification process to unlock all features.'}
                </p>
              </div>
            </div>
            {kycStatus.status === 'not_started' && (
              <Button
                onClick={handleSubmitForVerification}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Shield className="w-4 h-4 mr-2" />
                Start Verification
              </Button>
            )}
            {kycStatus.status === 'rejected' && (
              <Button
                onClick={handleResubmit}
                className="bg-gradient-to-r from-yellow-500 to-orange-500"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Resubmit
              </Button>
            )}
          </div>

          {/* KYC Progress */}
          {kycStatus.status !== 'verified' && kycStatus.status !== 'pending' && (
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">Verification Progress</span>
                <span className="text-cyan-400">{Math.round(kycProgress)}%</span>
              </div>
              <Progress value={kycProgress} className="h-2" />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-xs text-gray-500">
                <div>
                  <span className="text-gray-400">Required Documents</span>
                  <div className="text-white font-medium">{documentTypes.filter(d => d.required).length}</div>
                </div>
                <div>
                  <span className="text-gray-400">Uploaded</span>
                  <div className="text-white font-medium">{documents.length}</div>
                </div>
                <div>
                  <span className="text-gray-400">Approved</span>
                  <div className="text-green-500 font-medium">{documents.filter(d => d.status === 'approved').length}</div>
                </div>
                <div>
                  <span className="text-gray-400">Pending</span>
                  <div className="text-yellow-500 font-medium">{documents.filter(d => d.status === 'pending').length}</div>
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="overview"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📊 Overview
          </TabsTrigger>
          <TabsTrigger
            value="documents"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📄 Documents
          </TabsTrigger>
          <TabsTrigger
            value="history"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📜 History
          </TabsTrigger>
          <TabsTrigger
            value="requirements"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Requirements
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            {/* Personal Information */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-cyan-400">👤</span> Personal Information
                </h3>
                {userInfoLoading ? (
                  <div className="text-center py-4">
                    <Spinner size="sm" className="mx-auto text-cyan-500" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-gray-500">First Name</label>
                        <Input
                          value={userInfo.firstName}
                          onChange={(e) => handleUserInfoChange('firstName', e.target.value)}
                          className="w-full bg-gray-700 border-gray-600 text-white"
                          disabled={kycStatus?.status === 'pending' || kycStatus?.status === 'verified'}
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500">Last Name</label>
                        <Input
                          value={userInfo.lastName}
                          onChange={(e) => handleUserInfoChange('lastName', e.target.value)}
                          className="w-full bg-gray-700 border-gray-600 text-white"
                          disabled={kycStatus?.status === 'pending' || kycStatus?.status === 'verified'}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500">Email</label>
                      <div className="flex items-center gap-2">
                        <Mail className="w-4 h-4 text-gray-500" />
                        <span className="text-white">{userInfo.email}</span>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500">Phone Number</label>
                      <Input
                        value={userInfo.phone}
                        onChange={(e) => handleUserInfoChange('phone', e.target.value)}
                        className="w-full bg-gray-700 border-gray-600 text-white"
                        disabled={kycStatus?.status === 'pending' || kycStatus?.status === 'verified'}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500">Date of Birth</label>
                      <Input
                        type="date"
                        value={userInfo.dateOfBirth}
                        onChange={(e) => handleUserInfoChange('dateOfBirth', e.target.value)}
                        className="w-full bg-gray-700 border-gray-600 text-white"
                        disabled={kycStatus?.status === 'pending' || kycStatus?.status === 'verified'}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-gray-500">Nationality</label>
                        <Select
                          value={userInfo.nationality}
                          onValueChange={(value) => handleUserInfoChange('nationality', value)}
                          className="w-full bg-gray-700 border-gray-600"
                          disabled={kycStatus?.status === 'pending' || kycStatus?.status === 'verified'}
                        >
                          {KYC_COUNTRIES.map(country => (
                            <option key={country.code} value={country.code}>
                              {country.name}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500">Country of Residence</label>
                        <Select
                          value={userInfo.countryOfResidence}
                          onValueChange={(value) => handleUserInfoChange('countryOfResidence', value)}
                          className="w-full bg-gray-700 border-gray-600"
                          disabled={kycStatus?.status === 'pending' || kycStatus?.status === 'verified'}
                        >
                          {KYC_COUNTRIES.map(country => (
                            <option key={country.code} value={country.code}>
                              {country.name}
                            </option>
                          ))}
                        </Select>
                      </div>
                    </div>
                    {(kycStatus?.status !== 'pending' && kycStatus?.status !== 'verified') && (
                      <Button
                        onClick={handleSubmitUserInfo}
                        isLoading={isSubmitting}
                        className="w-full bg-gradient-to-r from-cyan-500 to-blue-500"
                      >
                        <Save className="w-4 h-4 mr-2" />
                        Save Information
                      </Button>
                    )}
                  </div>
                )}
              </Card>
            </div>

            {/* KYC Level Benefits */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-purple-400">🏆</span> Your KYC Level
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-3 p-3 bg-gray-700/30 rounded-lg">
                    <div className={cn(
                      "w-12 h-12 rounded-full flex items-center justify-center",
                      kycLevelData.color
                    )}>
                      <kycLevelData.icon className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="font-medium text-white">{kycLevelData.label}</div>
                      <div className="text-sm text-gray-400">{kycLevel?.description || 'Basic verification level'}</div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-gray-300">Features & Limits</h4>
                    {kycLevel?.features?.map((feature, index) => (
                      <div key={index} className="flex items-start gap-2 text-sm">
                        <CheckCircle className="w-4 h-4 text-cyan-500 mt-0.5 flex-shrink-0" />
                        <span className="text-gray-300">{feature}</span>
                      </div>
                    ))}
                    {!kycLevel?.features && (
                      <div className="text-sm text-gray-500">
                        Complete KYC verification to unlock features
                      </div>
                    )}
                  </div>

                  {kycLevel?.limits && (
                    <div className="p-3 bg-gray-700/30 rounded-lg">
                      <h4 className="text-sm font-medium text-gray-300 mb-2">Limits</h4>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-400">Daily Trading Limit</span>
                          <span className="text-white">{formatCurrency(kycLevel.limits.dailyTrading || 0)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Monthly Trading Limit</span>
                          <span className="text-white">{formatCurrency(kycLevel.limits.monthlyTrading || 0)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Withdrawal Limit</span>
                          <span className="text-white">{formatCurrency(kycLevel.limits.withdrawal || 0)}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* DOCUMENTS TAB */}
        // ... (continued)
        // This is getting very long. The complete file continues with the Documents tab, History tab, Requirements tab, and modals.
        // Let me know if you want me to continue with the full implementation.
      </Tabs>
    </div>
  );
}

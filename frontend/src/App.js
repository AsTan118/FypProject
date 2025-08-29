// App.js - Complete React App with Authentication
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

// Configure axios
axios.defaults.baseURL = 'http://localhost:8000';

// Add token to all requests if it exists
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle auth errors globally
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'signup'
  const [loading, setLoading] = useState(true);

  // Check if user is logged in on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    
    if (token && savedUser) {
      setIsAuthenticated(true);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setIsAuthenticated(false);
    setUser(null);
  };

  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        backgroundColor: '#343541',
        color: '#ffffff'
      }}>
        Loading...
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <AuthScreen 
        authMode={authMode} 
        setAuthMode={setAuthMode}
        setIsAuthenticated={setIsAuthenticated}
        setUser={setUser}
      />
    );
  }

  return (
    <MainApp user={user} handleLogout={handleLogout} />
  );
};

// Authentication Screen Component
const AuthScreen = ({ authMode, setAuthMode, setIsAuthenticated, setUser }) => {
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    fullName: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (authMode === 'signup') {
        // Validate passwords match
        if (formData.password !== formData.confirmPassword) {
          setError('Passwords do not match');
          setLoading(false);
          return;
        }

        // Signup
        const response = await axios.post('/api/auth/signup', {
          email: formData.email,
          username: formData.username,
          password: formData.password,
          full_name: formData.fullName
        });

        localStorage.setItem('token', response.data.access_token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        setUser(response.data.user);
        setIsAuthenticated(true);
      } else {
        // Login
        const response = await axios.post('/api/auth/login', {
          username: formData.username,
          password: formData.password
        });

        localStorage.setItem('token', response.data.access_token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        setUser(response.data.user);
        setIsAuthenticated(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const styles = {
    container: {
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#343541',
      padding: '20px'
    },
    authCard: {
      width: '100%',
      maxWidth: '400px',
      backgroundColor: '#444654',
      borderRadius: '12px',
      padding: '32px',
      boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)'
    },
    logo: {
      textAlign: 'center',
      marginBottom: '24px'
    },
    title: {
      color: '#ffffff',
      fontSize: '28px',
      fontWeight: '600',
      marginBottom: '8px'
    },
    subtitle: {
      color: '#8e8ea0',
      fontSize: '14px'
    },
    form: {
      marginTop: '24px'
    },
    inputGroup: {
      marginBottom: '16px'
    },
    label: {
      display: 'block',
      color: '#d1d5db',
      fontSize: '14px',
      marginBottom: '6px',
      fontWeight: '500'
    },
    input: {
      width: '100%',
      padding: '10px 12px',
      backgroundColor: '#40414f',
      border: '1px solid #565869',
      borderRadius: '6px',
      color: '#ffffff',
      fontSize: '14px',
      outline: 'none',
      transition: 'border-color 0.2s'
    },
    button: {
      width: '100%',
      padding: '12px',
      backgroundColor: '#10A37F',
      color: '#ffffff',
      border: 'none',
      borderRadius: '6px',
      fontSize: '16px',
      fontWeight: '600',
      cursor: 'pointer',
      transition: 'background-color 0.2s',
      marginTop: '20px'
    },
    buttonDisabled: {
      backgroundColor: '#565869',
      cursor: 'not-allowed'
    },
    error: {
      backgroundColor: 'rgba(239, 68, 68, 0.1)',
      border: '1px solid rgba(239, 68, 68, 0.3)',
      color: '#ef4444',
      padding: '10px',
      borderRadius: '6px',
      fontSize: '14px',
      marginTop: '12px'
    },
    switchMode: {
      textAlign: 'center',
      marginTop: '24px',
      color: '#8e8ea0',
      fontSize: '14px'
    },
    link: {
      color: '#10A37F',
      cursor: 'pointer',
      textDecoration: 'none',
      fontWeight: '500'
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.authCard}>
        <div style={styles.logo}>
          <h1 style={styles.title}>PDF RAG System</h1>
          <p style={styles.subtitle}>
            {authMode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        <form style={styles.form} onSubmit={handleSubmit}>
          {authMode === 'signup' && (
            <>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Email</label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  required
                  style={styles.input}
                  placeholder="you@example.com"
                />
              </div>

              <div style={styles.inputGroup}>
                <label style={styles.label}>Full Name</label>
                <input
                  type="text"
                  name="fullName"
                  value={formData.fullName}
                  onChange={handleInputChange}
                  style={styles.input}
                  placeholder="John Doe"
                />
              </div>
            </>
          )}

          <div style={styles.inputGroup}>
            <label style={styles.label}>
              {authMode === 'login' ? 'Username or Email' : 'Username'}
            </label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              required
              style={styles.input}
              placeholder={authMode === 'login' ? 'username or email' : 'username'}
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              required
              style={styles.input}
              placeholder="••••••••"
            />
          </div>

          {authMode === 'signup' && (
            <div style={styles.inputGroup}>
              <label style={styles.label}>Confirm Password</label>
              <input
                type="password"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleInputChange}
                required
                style={styles.input}
                placeholder="••••••••"
              />
            </div>
          )}

          {error && (
            <div style={styles.error}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              ...styles.button,
              ...(loading ? styles.buttonDisabled : {})
            }}
          >
            {loading ? 'Processing...' : authMode === 'login' ? 'Sign In' : 'Sign Up'}
          </button>
        </form>

        <div style={styles.switchMode}>
          {authMode === 'login' ? (
            <>
              Don't have an account?{' '}
              <span style={styles.link} onClick={() => setAuthMode('signup')}>
                Sign up
              </span>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <span style={styles.link} onClick={() => setAuthMode('login')}>
                Sign in
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Main Application Component (with authentication)
const MainApp = ({ user, handleLogout }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pdfs, setPdfs] = useState([]);
  const [showSidebar, setShowSidebar] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [processingPdfs, setProcessingPdfs] = useState(new Map());
  const [showUploadModal, setShowUploadModal] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const eventSourcesRef = useRef(new Map());

  // Styles
  const styles = {
    container: {
      display: 'flex',
      height: '100vh',
      backgroundColor: '#343541',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
    },
    sidebar: {
      width: showSidebar ? '260px' : '0',
      backgroundColor: '#202123',
      transition: 'width 0.3s ease',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      borderRight: '1px solid #4d4d5f'
    },
    sidebarHeader: {
      padding: '12px',
      borderBottom: '1px solid #4d4d5f'
    },
    userInfo: {
      padding: '12px',
      backgroundColor: '#2a2b32',
      borderRadius: '6px',
      marginBottom: '12px',
      color: '#ffffff'
    },
    userAvatar: {
      width: '32px',
      height: '32px',
      borderRadius: '50%',
      backgroundColor: '#10A37F',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '14px',
      fontWeight: '600',
      marginBottom: '8px'
    },
    userName: {
      fontSize: '14px',
      fontWeight: '500',
      marginBottom: '4px'
    },
    userEmail: {
      fontSize: '12px',
      color: '#8e8ea0'
    },
    logoutButton: {
      width: '100%',
      padding: '8px',
      backgroundColor: 'transparent',
      border: '1px solid #565869',
      borderRadius: '6px',
      color: '#ef4444',
      cursor: 'pointer',
      marginTop: '8px',
      fontSize: '13px',
      transition: 'background-color 0.2s'
    },
    newChatButton: {
      width: '100%',
      padding: '12px',
      backgroundColor: 'transparent',
      border: '1px solid #565869',
      borderRadius: '6px',
      color: '#ffffff',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      fontSize: '14px',
      transition: 'background-color 0.2s'
    },
    sidebarContent: {
      flex: 1,
      overflowY: 'auto',
      padding: '12px'
    },
    pdfItem: {
      backgroundColor: '#2a2b32',
      borderRadius: '6px',
      padding: '12px',
      marginBottom: '8px',
      color: '#ffffff',
      fontSize: '14px',
      position: 'relative',
      cursor: 'pointer',
      transition: 'background-color 0.2s'
    },
    mainArea: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#343541'
    },
    header: {
      backgroundColor: '#343541',
      borderBottom: '1px solid #4d4d5f',
      padding: '18px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    },
    messagesArea: {
      flex: 1,
      overflowY: 'auto',
      backgroundColor: '#343541'
    },
    messageContainer: {
      display: 'flex',
      justifyContent: 'center',
      borderBottom: '1px solid #4d4d5f',
      backgroundColor: '#343541'
    },
    messageWrapper: {
      maxWidth: '48rem',
      width: '100%',
      padding: '24px',
      display: 'flex',
      gap: '24px'
    },
    userMessageContainer: {
      backgroundColor: '#343541'
    },
    assistantMessageContainer: {
      backgroundColor: '#444654'
    },
    avatar: {
      width: '30px',
      height: '30px',
      borderRadius: '2px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0
    },
    userAvatarChat: {
      backgroundColor: '#5436DA'
    },
    assistantAvatar: {
      backgroundColor: '#10A37F'
    },
    messageContent: {
      flex: 1,
      color: '#d1d5db',
      fontSize: '15px',
      lineHeight: '1.75'
    },
    inputArea: {
      borderTop: '1px solid #4d4d5f',
      backgroundColor: '#343541',
      padding: '24px'
    },
    inputWrapper: {
      maxWidth: '48rem',
      margin: '0 auto',
      position: 'relative'
    },
    inputContainer: {
      position: 'relative',
      backgroundColor: '#40414f',
      borderRadius: '12px',
      border: '1px solid #565869',
      display: 'flex',
      alignItems: 'center',
      padding: '0 12px'
    },
    input: {
      flex: 1,
      backgroundColor: 'transparent',
      border: 'none',
      outline: 'none',
      padding: '12px',
      color: '#ffffff',
      fontSize: '15px',
      resize: 'none',
      minHeight: '24px',
      maxHeight: '200px',
      fontFamily: 'inherit'
    },
    button: {
      backgroundColor: 'transparent',
      border: 'none',
      padding: '8px',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: '6px',
      transition: 'background-color 0.2s'
    },
    sendButton: {
      color: '#ffffff',
      opacity: inputMessage.trim() && !isLoading ? 1 : 0.4,
      cursor: inputMessage.trim() && !isLoading ? 'pointer' : 'not-allowed'
    },
    attachButton: {
      color: '#8e8ea0'
    },
    modal: {
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50
    },
    modalContent: {
      backgroundColor: '#444654',
      borderRadius: '12px',
      padding: '24px',
      maxWidth: '480px',
      width: '90%',
      border: '1px solid #565869'
    },
    uploadZone: {
      border: '2px dashed',
      borderColor: dragActive ? '#10A37F' : '#565869',
      borderRadius: '8px',
      padding: '40px',
      textAlign: 'center',
      backgroundColor: dragActive ? '#40414f' : 'transparent',
      transition: 'all 0.2s'
    },
    uploadButton: {
      padding: '10px 20px',
      backgroundColor: '#10A37F',
      color: '#ffffff',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      marginTop: '16px'
    },
    menuButton: {
      padding: '8px',
      backgroundColor: 'transparent',
      border: '1px solid #565869',
      borderRadius: '6px',
      cursor: 'pointer',
      color: '#ffffff',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    },
    disclaimer: {
      textAlign: 'center',
      color: '#8e8ea0',
      fontSize: '12px',
      marginTop: '12px'
    }
  };

  // Scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initial setup
  useEffect(() => {
    fetchPDFs();
    
    setMessages([{
      id: 1,
      type: 'assistant',
      content: `Hello ${user.full_name || user.username}! I can help you analyze your PDF documents. Upload a PDF using the attach button below, then ask me any questions about its content.`,
      timestamp: new Date()
    }]);
    
    return () => {
      eventSourcesRef.current.forEach((eventSource) => {
        eventSource.close();
      });
    };
  }, [user]);

  const startSSEMonitoring = (pdfId) => {
    if (eventSourcesRef.current.has(pdfId)) {
      return;
    }

    console.log(`Starting SSE monitoring for PDF ${pdfId}`);
    
    const eventSource = new EventSource(`http://localhost:8000/api/processing-events/${pdfId}`);
    
    eventSource.onmessage = (event) => {
      const status = event.data;
      console.log(`PDF ${pdfId} status update: ${status}`);
      
      if (status === 'completed' || status === 'failed') {
        eventSource.close();
        eventSourcesRef.current.delete(pdfId);
        
        setProcessingPdfs(prev => {
          const newMap = new Map(prev);
          newMap.delete(pdfId);
          return newMap;
        });
        
        fetchPDFs();
        
        if (status === 'completed') {
          setMessages(prev => [...prev, {
            id: Date.now(),
            type: 'assistant',
            content: 'PDF processing completed! The document is now ready for questions.',
            timestamp: new Date()
          }]);
        } else {
          setMessages(prev => [...prev, {
            id: Date.now(),
            type: 'assistant',
            content: 'PDF processing failed. Please try uploading the file again.',
            timestamp: new Date(),
            error: true
          }]);
        }
      }
    };
    
    eventSource.onerror = (error) => {
      console.error(`SSE error for PDF ${pdfId}:`, error);
      eventSource.close();
      eventSourcesRef.current.delete(pdfId);
      checkSinglePdfStatus(pdfId);
    };
    
    eventSourcesRef.current.set(pdfId, eventSource);
  };

  const checkSinglePdfStatus = async (pdfId) => {
    try {
      const response = await axios.get(`/api/processing-status/${pdfId}`);
      
      if (response.data.status === 'completed' || response.data.status === 'failed') {
        setProcessingPdfs(prev => {
          const newMap = new Map(prev);
          newMap.delete(pdfId);
          return newMap;
        });
        fetchPDFs();
      }
    } catch (err) {
      console.error(`Error checking status for PDF ${pdfId}:`, err);
    }
  };

  const fetchPDFs = async () => {
    try {
      const response = await axios.get('/api/pdfs');
      setPdfs(response.data.pdfs);
      
      const processingPdfsList = response.data.pdfs.filter(
        pdf => pdf.processing_status === 'processing' || pdf.processing_status === 'pending'
      );
      
      processingPdfsList.forEach(pdf => {
        if (!eventSourcesRef.current.has(pdf.id)) {
          startSSEMonitoring(pdf.id);
          setProcessingPdfs(prev => new Map(prev).set(pdf.id, true));
        }
      });
    } catch (err) {
      console.error('Error fetching PDFs:', err);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;
    
    const completedPdfs = pdfs.filter(p => p.processing_status === 'completed');
    if (completedPdfs.length === 0) {
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'assistant',
        content: 'Please upload at least one PDF document first. Use the attach button below to upload a PDF.',
        timestamp: new Date()
      }]);
      return;
    }

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post('/api/query', {
        question: inputMessage
      });

      const assistantMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
        responseTime: response.data.response_time,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        type: 'assistant',
        content: 'Sorry, I encountered an error while processing your question. Please try again.',
        timestamp: new Date(),
        error: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = async (file) => {
    if (!file.name.endsWith('.pdf')) {
      alert('Please upload only PDF files');
      return;
    }

    setUploading(true);
    setShowUploadModal(false);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        const pdfId = response.data.pdf_id;
        
        setProcessingPdfs(prev => new Map(prev).set(pdfId, true));
        startSSEMonitoring(pdfId);
        
        setMessages(prev => [...prev, {
          id: Date.now(),
          type: 'assistant',
          content: `Successfully uploaded "${file.name}". Processing the document...`,
          timestamp: new Date()
        }]);
        
        fetchPDFs();
      } else {
        setMessages(prev => [...prev, {
          id: Date.now(),
          type: 'assistant',
          content: response.data.message || 'File upload failed',
          timestamp: new Date(),
          error: !response.data.success
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'assistant',
        content: `Error uploading file: ${err.response?.data?.detail || 'Unknown error'}`,
        timestamp: new Date(),
        error: true
      }]);
    } finally {
      setUploading(false);
    }
  };

  const handleDeletePDF = async (pdfId, filename) => {
    if (!window.confirm(`Delete "${filename}"?`)) return;

    try {
      if (eventSourcesRef.current.has(pdfId)) {
        eventSourcesRef.current.get(pdfId).close();
        eventSourcesRef.current.delete(pdfId);
      }
      
      await axios.delete(`/api/pdfs/${pdfId}`);
      fetchPDFs();
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'assistant',
        content: `Successfully deleted "${filename}"`,
        timestamp: new Date()
      }]);
    } catch (err) {
      console.error('Error deleting PDF:', err);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const newChat = () => {
    setMessages([{
      id: Date.now(),
      type: 'assistant',
      content: 'Starting a new conversation. How can I help you with your PDF documents?',
      timestamp: new Date()
    }]);
  };

  const getStatusDisplay = (pdf) => {
    const isProcessing = processingPdfs.has(pdf.id);
    
    if (isProcessing) {
      return {
        icon: '⏳',
        text: 'processing',
        color: '#FFA500'
      };
    }
    
    switch (pdf.processing_status) {
      case 'completed':
        return {
          icon: '✓',
          text: 'completed',
          color: '#10A37F'
        };
      case 'failed':
        return {
          icon: '✗',
          text: 'failed',
          color: '#FF4444'
        };
      case 'processing':
      case 'pending':
        return {
          icon: '⏳',
          text: pdf.processing_status,
          color: '#FFA500'
        };
      default:
        return {
          icon: '?',
          text: pdf.processing_status,
          color: '#8e8ea0'
        };
    }
  };

  return (
    <div style={styles.container}>
      {/* Sidebar */}
      <div style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          {/* User Info */}
          <div style={styles.userInfo}>
            <div style={styles.userAvatar}>
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div style={styles.userName}>{user.full_name || user.username}</div>
            <div style={styles.userEmail}>{user.email}</div>
            <button 
              style={styles.logoutButton}
              onClick={handleLogout}
              onMouseEnter={(e) => e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'}
              onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
            >
              Sign Out
            </button>
          </div>
          
          <button 
            style={styles.newChatButton}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#2a2b32'}
            onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
            onClick={newChat}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 4v16m8-8H4" />
            </svg>
            New chat
          </button>
        </div>
        
        <div style={styles.sidebarContent}>
          <div style={{ marginBottom: '16px', color: '#8e8ea0', fontSize: '12px', fontWeight: '500' }}>
            YOUR PDFS
          </div>
          {pdfs.length === 0 ? (
            <div style={{ color: '#8e8ea0', fontSize: '14px' }}>No PDFs uploaded yet</div>
          ) : (
            pdfs.map((pdf) => {
              const status = getStatusDisplay(pdf);
              return (
                <div 
                  key={pdf.id} 
                  style={styles.pdfItem}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#343541'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#2a2b32'}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: '500', marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {pdf.filename}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#8e8ea0' }}>
                        <span style={{ color: status.color }}>
                          {status.icon} {status.text}
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                        {formatFileSize(pdf.file_size)} • {pdf.page_count || 0} pages
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeletePDF(pdf.id, pdf.filename)}
                      style={{ 
                        background: 'none', 
                        border: 'none', 
                        color: '#8e8ea0', 
                        cursor: 'pointer',
                        padding: '4px'
                      }}
                      onMouseEnter={(e) => e.target.style.color = '#FF4444'}
                      onMouseLeave={(e) => e.target.style.color = '#8e8ea0'}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2M10 11v6M14 11v6M5 6h14l-1 13a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6z" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Area */}
      <div style={styles.mainArea}>
        {/* Header */}
        <div style={styles.header}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button 
              onClick={() => setShowSidebar(!showSidebar)} 
              style={styles.menuButton}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#40414f'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            </button>
            <h1 style={{ fontSize: '20px', fontWeight: '600', color: '#ffffff' }}>PDF Assistant</h1>
          </div>
          <div style={{ color: '#8e8ea0', fontSize: '14px' }}>
            {pdfs.filter(p => p.processing_status === 'completed').length} PDFs ready
            {processingPdfs.size > 0 && ` • ${processingPdfs.size} processing`}
          </div>
        </div>

        {/* Messages Area */}
        <div style={styles.messagesArea}>
          {messages.map((message) => (
            <div key={message.id} style={{
              ...styles.messageContainer,
              ...(message.type === 'assistant' ? styles.assistantMessageContainer : styles.userMessageContainer)
            }}>
              <div style={styles.messageWrapper}>
                <div style={{
                  ...styles.avatar,
                  ...(message.type === 'user' ? styles.userAvatarChat : styles.assistantAvatar)
                }}>
                  {message.type === 'user' ? user.username.charAt(0).toUpperCase() : 'A'}
                </div>
                <div style={styles.messageContent}>
                  <div style={{ marginBottom: '4px', fontWeight: '600', fontSize: '14px' }}>
                    {message.type === 'user' ? 'You' : 'PDF Assistant'}
                    {message.responseTime && (
                      <span style={{ fontSize: '12px', color: '#8e8ea0', marginLeft: '8px', fontWeight: 'normal' }}>
                        {message.responseTime.toFixed(2)}s
                      </span>
                    )}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
                  {message.sources && message.sources.length > 0 && (
                    <div style={{ 
                      marginTop: '12px', 
                      padding: '12px', 
                      backgroundColor: 'rgba(16, 163, 127, 0.1)', 
                      borderRadius: '6px',
                      fontSize: '13px',
                      color: '#10A37F',
                      border: '1px solid rgba(16, 163, 127, 0.2)'
                    }}>
                      <div style={{ fontWeight: '600', marginBottom: '8px' }}>Sources:</div>
                      {message.sources.slice(0, 3).map((source, idx) => (
                        <div key={idx} style={{ marginBottom: '4px' }}>
                          📄 {source.filename} - Page {source.page}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div style={{
              ...styles.messageContainer,
              ...styles.assistantMessageContainer
            }}>
              <div style={styles.messageWrapper}>
                <div style={{ ...styles.avatar, ...styles.assistantAvatar }}>A</div>
                <div style={styles.messageContent}>
                  <div style={{ marginBottom: '4px', fontWeight: '600', fontSize: '14px' }}>PDF Assistant</div>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <span style={{ animation: 'bounce 1.4s infinite', animationDelay: '0ms' }}>●</span>
                    <span style={{ animation: 'bounce 1.4s infinite', animationDelay: '0.2s' }}>●</span>
                    <span style={{ animation: 'bounce 1.4s infinite', animationDelay: '0.4s' }}>●</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div style={styles.inputArea}>
          <div style={styles.inputWrapper}>
            <div style={styles.inputContainer}>
              <button 
                onClick={() => setShowUploadModal(true)} 
                style={{ ...styles.button, ...styles.attachButton }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#40414f'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                </svg>
              </button>
              <textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Message PDF Assistant..."
                style={styles.input}
                rows="1"
              />
              <button
                onClick={handleSendMessage}
                disabled={!inputMessage.trim() || isLoading}
                style={{ ...styles.button, ...styles.sendButton }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </div>
            <div style={styles.disclaimer}>
              PDF Assistant can make mistakes. Check important info.
            </div>
          </div>
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div style={styles.modal} onClick={() => setShowUploadModal(false)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#ffffff' }}>Upload PDF</h2>
              <button
                onClick={() => setShowUploadModal(false)}
                style={{ background: 'none', border: 'none', color: '#8e8ea0', cursor: 'pointer', padding: '4px' }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div
              style={styles.uploadZone}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#8e8ea0" strokeWidth="2" style={{ margin: '0 auto 16px' }}>
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
              <p style={{ color: '#ffffff', marginBottom: '8px', fontSize: '16px' }}>Drag and drop your PDF here</p>
              <p style={{ color: '#8e8ea0', fontSize: '14px' }}>or</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
                style={{ display: 'none' }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                style={styles.uploadButton}
                disabled={uploading}
              >
                {uploading ? 'Uploading...' : 'Choose File'}
              </button>
              <p style={{ color: '#8e8ea0', fontSize: '12px', marginTop: '16px' }}>Maximum file size: 50MB</p>
            </div>
          </div>
        </div>
      )}

      {/* Add keyframe animations */}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-10px); }
        }
      `}</style>
    </div>
  );
};

export default App;
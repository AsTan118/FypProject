import React, { useState, useEffect, useRef } from 'react';

// Axios configuration
const API_BASE = 'http://localhost:8000';

// Simple axios-like implementation with better error handling
const axios = {
  defaults: { baseURL: API_BASE },
  
  async request(config) {
    const url = `${this.defaults.baseURL}${config.url}`;
    const token = sessionStorage.getItem('token');
    
    const headers = {
      ...config.headers
    };
    
    // Add auth token if available
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Don't set Content-Type for FormData - let browser set it with boundary
    if (!(config.data instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    
    try {
      const response = await fetch(url, {
        method: config.method || 'GET',
        headers,
        body: config.data instanceof FormData 
          ? config.data 
          : config.data 
            ? JSON.stringify(config.data) 
            : undefined
      });
      
      const text = await response.text();
      let data;
      
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
      
      if (!response.ok) {
        throw { 
          response: { 
            status: response.status, 
            data: data || { detail: 'Request failed' }
          } 
        };
      }
      
      return { data };
    } catch (error) {
      console.error('Request error:', error);
      throw error;
    }
  },
  
  get(url) { return this.request({ url, method: 'GET' }); },
  post(url, data, config = {}) { return this.request({ url, method: 'POST', data, ...config }); },
  put(url, data) { return this.request({ url, method: 'PUT', data }); },
  delete(url) { return this.request({ url, method: 'DELETE' }); }
};

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login');
  const [loading, setLoading] = useState(true);
  const [currentView, setCurrentView] = useState('chat'); // 'chat' or 'admin'

  useEffect(() => {
    const token = sessionStorage.getItem('token');
    const savedUser = sessionStorage.getItem('user');
    
    if (token && savedUser) {
      setIsAuthenticated(true);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const handleLogout = () => {
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    setIsAuthenticated(false);
    setUser(null);
    setCurrentView('chat');
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

  // Admin users get admin panel, students get chat
  if (user?.role === 'admin' && currentView === 'admin') {
    return (
      <AdminPanel 
        user={user} 
        handleLogout={handleLogout} 
        setCurrentView={setCurrentView}
      />
    );
  }

  return (
    <MainApp 
      user={user} 
      handleLogout={handleLogout} 
      setCurrentView={setCurrentView}
    />
  );
};

// Authentication Screen
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
        if (formData.password !== formData.confirmPassword) {
          setError('Passwords do not match');
          setLoading(false);
          return;
        }

        const response = await axios.post('/api/auth/signup', {
          email: formData.email,
          username: formData.username,
          password: formData.password,
          full_name: formData.fullName
        });

        sessionStorage.setItem('token', response.data.access_token);
        sessionStorage.setItem('user', JSON.stringify(response.data.user));
        setUser(response.data.user);
        setIsAuthenticated(true);
      } else {
        const response = await axios.post('/api/auth/login', {
          username: formData.username,
          password: formData.password
        });

        sessionStorage.setItem('token', response.data.access_token);
        sessionStorage.setItem('user', JSON.stringify(response.data.user));
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
      transition: 'border-color 0.2s',
      boxSizing: 'border-box'  // Added this to ensure padding is included in width
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
      marginTop: '20px',
      boxSizing: 'border-box'  // Added this
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
      marginTop: '12px',
      boxSizing: 'border-box'  // Added this
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
    },
    adminNote: {
      backgroundColor: 'rgba(16, 163, 127, 0.1)',
      border: '1px solid rgba(16, 163, 127, 0.3)',
      color: '#10A37F',
      padding: '10px',
      borderRadius: '6px',
      fontSize: '12px',
      marginTop: '12px',
      textAlign: 'center',
      boxSizing: 'border-box'  // Added this
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.authCard}>
        <div style={styles.logo}>
          <h1 style={styles.title}>UTAR</h1>
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

// Admin Panel Component
const AdminPanel = ({ user, handleLogout, setCurrentView }) => {
  const [activeTab, setActiveTab] = useState('stats');
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [pdfs, setPdfs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadStats();
    loadUsers();
    loadPdfs();
  }, []);

  const loadStats = async () => {
    try {
      const response = await axios.get('/api/admin/stats');
      setStats(response.data);
    } catch (err) {
      console.error('Error loading stats:', err);
    }
  };

  const loadUsers = async () => {
    try {
      const response = await axios.get('/api/admin/users');
      setUsers(response.data.users);
    } catch (err) {
      console.error('Error loading users:', err);
    }
  };

  const loadPdfs = async () => {
    try {
      const response = await axios.get('/api/admin/pdfs');
      setPdfs(response.data.pdfs);
    } catch (err) {
      console.error('Error loading PDFs:', err);
    }
  };

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setLoading(true);
    setUploadProgress({ total: files.length, current: 0, results: [] });
    
    // Create FormData and add all PDF files
    const formData = new FormData();
    let validFiles = 0;
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setUploadProgress(prev => ({
          ...prev,
          results: [...(prev.results || []), { 
            filename: file.name, 
            success: false, 
            error: 'Not a PDF file' 
          }]
        }));
        continue;
      }
      // Append each file with the same field name 'files'
      formData.append('files', file);
      validFiles++;
    }

    if (validFiles === 0) {
      alert('No valid PDF files selected');
      setLoading(false);
      setUploadProgress(null);
      return;
    }

    try {
      // Don't set Content-Type header - let browser set it with boundary
      const response = await axios.post('/api/admin/upload-public', formData);
      
      // Update progress with results
      setUploadProgress({
        total: files.length,
        current: files.length,
        results: response.data.results || []
      });
      
      // Reload PDFs list after a short delay
      setTimeout(() => {
        loadPdfs();
        loadStats();
      }, 1000);
      
      // Show success message
      const successCount = response.data.successful_count || 0;
      const failedCount = response.data.failed_count || 0;
      
      if (successCount > 0) {
        alert(`Successfully uploaded ${successCount} file(s)${failedCount > 0 ? `, ${failedCount} failed` : ''}`);
      } else {
        alert('All uploads failed. Please check the files and try again.');
      }
      
    } catch (err) {
      console.error('Upload error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      alert('Failed to upload files: ' + errorMsg);
      
      // Show error in progress
      setUploadProgress(prev => ({
        ...prev,
        error: errorMsg
      }));
    } finally {
      setLoading(false);
      // Clear progress after 3 seconds
      setTimeout(() => {
        setUploadProgress(null);
      }, 3000);
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const updatePdfVisibility = async (pdfId, visibility) => {
    try {
      await axios.put(`/api/admin/pdfs/${pdfId}/visibility`, visibility);
      loadPdfs();
    } catch (err) {
      console.error('Error updating visibility:', err);
    }
  };

  const deleteUser = async (userId, username) => {
    if (!window.confirm(`Delete user "${username}"?`)) return;
    
    try {
      await axios.delete(`/api/admin/users/${userId}`);
      loadUsers();
      loadStats();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error deleting user');
    }
  };

  const styles = {
    container: {
      height: '100vh',
      backgroundColor: '#343541',
      display: 'flex',
      flexDirection: 'column'
    },
    header: {
      backgroundColor: '#202123',
      padding: '16px 24px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      borderBottom: '1px solid #4d4d5f'
    },
    title: {
      color: '#ffffff',
      fontSize: '20px',
      fontWeight: '600',
      display: 'flex',
      alignItems: 'center',
      gap: '12px'
    },
    userInfo: {
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      color: '#ffffff'
    },
    tabs: {
      display: 'flex',
      gap: '8px',
      padding: '16px 24px',
      backgroundColor: '#202123',
      borderBottom: '1px solid #4d4d5f'
    },
    tab: {
      padding: '8px 16px',
      backgroundColor: 'transparent',
      border: '1px solid #565869',
      borderRadius: '6px',
      color: '#8e8ea0',
      cursor: 'pointer',
      fontSize: '14px',
      transition: 'all 0.2s'
    },
    activeTab: {
      backgroundColor: '#10A37F',
      borderColor: '#10A37F',
      color: '#ffffff'
    },
    content: {
      flex: 1,
      overflowY: 'auto',
      padding: '24px'
    },
    statsGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '16px',
      marginBottom: '24px'
    },
    statCard: {
      backgroundColor: '#444654',
      borderRadius: '8px',
      padding: '16px',
      border: '1px solid #565869'
    },
    statValue: {
      fontSize: '28px',
      fontWeight: '600',
      color: '#ffffff',
      marginBottom: '4px'
    },
    statLabel: {
      fontSize: '14px',
      color: '#8e8ea0'
    },
    table: {
      width: '100%',
      backgroundColor: '#444654',
      borderRadius: '8px',
      overflow: 'hidden',
      border: '1px solid #565869'
    },
    tableHeader: {
      backgroundColor: '#40414f'
    },
    th: {
      padding: '12px',
      textAlign: 'left',
      color: '#d1d5db',
      fontWeight: '600',
      fontSize: '14px',
      borderBottom: '1px solid #565869'
    },
    td: {
      padding: '12px',
      color: '#ffffff',
      fontSize: '14px',
      borderBottom: '1px solid #565869'
    },
    button: {
      padding: '6px 12px',
      backgroundColor: '#10A37F',
      border: 'none',
      borderRadius: '4px',
      color: '#ffffff',
      cursor: 'pointer',
      fontSize: '13px',
      marginRight: '8px'
    },
    deleteButton: {
      backgroundColor: '#ef4444'
    },
    uploadSection: {
      backgroundColor: '#444654',
      borderRadius: '8px',
      padding: '20px',
      marginBottom: '20px',
      border: '1px solid #565869'
    },
    uploadButton: {
      padding: '10px 20px',
      backgroundColor: '#10A37F',
      border: 'none',
      borderRadius: '6px',
      color: '#ffffff',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: '600'
    },
    backButton: {
      padding: '8px 16px',
      backgroundColor: 'transparent',
      border: '1px solid #565869',
      borderRadius: '6px',
      color: '#ffffff',
      cursor: 'pointer',
      fontSize: '14px'
    },
    progressBar: {
      marginTop: '16px',
      padding: '12px',
      backgroundColor: '#40414f',
      borderRadius: '6px'
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.title}>
          <span>🛡️ Admin Panel</span>
          <button 
            onClick={() => setCurrentView('chat')}
            style={styles.backButton}
          >
            Switch to Chat
          </button>
        </div>
        <div style={styles.userInfo}>
          <span>{user.full_name || user.username} (Admin)</span>
          <button onClick={handleLogout} style={{...styles.button, ...styles.deleteButton}}>
            Logout
          </button>
        </div>
      </div>

      <div style={styles.tabs}>
        <button
          style={{...styles.tab, ...(activeTab === 'stats' ? styles.activeTab : {})}}
          onClick={() => setActiveTab('stats')}
        >
          Dashboard
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'users' ? styles.activeTab : {})}}
          onClick={() => setActiveTab('users')}
        >
          Users
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'pdfs' ? styles.activeTab : {})}}
          onClick={() => setActiveTab('pdfs')}
        >
          PDFs
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'upload' ? styles.activeTab : {})}}
          onClick={() => setActiveTab('upload')}
        >
          Upload PDFs
        </button>
      </div>

      <div style={styles.content}>
        {activeTab === 'stats' && stats && (
          <div>
            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{stats.total_users}</div>
                <div style={styles.statLabel}>Total Users</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{stats.admin_users}</div>
                <div style={styles.statLabel}>Admins</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{stats.student_users}</div>
                <div style={styles.statLabel}>Students</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{stats.total_pdfs}</div>
                <div style={styles.statLabel}>Total PDFs</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{stats.public_pdfs}</div>
                <div style={styles.statLabel}>Public PDFs</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{stats.total_queries}</div>
                <div style={styles.statLabel}>Total Queries</div>
              </div>
            </div>

            <h3 style={{color: '#ffffff', marginTop: '32px', marginBottom: '16px'}}>Recent Queries</h3>
            <table style={styles.table}>
              <thead style={styles.tableHeader}>
                <tr>
                  <th style={styles.th}>User</th>
                  <th style={styles.th}>Question</th>
                  <th style={styles.th}>Time</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_queries?.map((query, idx) => (
                  <tr key={idx}>
                    <td style={styles.td}>{query.username}</td>
                    <td style={styles.td}>{query.question}</td>
                    <td style={styles.td}>{new Date(query.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'users' && (
          <div>
            <h3 style={{color: '#ffffff', marginBottom: '16px'}}>All Users</h3>
            <table style={styles.table}>
              <thead style={styles.tableHeader}>
                <tr>
                  <th style={styles.th}>Username</th>
                  <th style={styles.th}>Email</th>
                  <th style={styles.th}>Full Name</th>
                  <th style={styles.th}>Role</th>
                  <th style={styles.th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id}>
                    <td style={styles.td}>{u.username}</td>
                    <td style={styles.td}>{u.email}</td>
                    <td style={styles.td}>{u.full_name || '-'}</td>
                    <td style={styles.td}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: u.role === 'admin' ? '#10A37F' : '#565869',
                        fontSize: '12px'
                      }}>
                        {u.role}
                      </span>
                    </td>
                    <td style={styles.td}>
                      {u.id !== user.id && (
                        <button
                          style={{...styles.button, ...styles.deleteButton}}
                          onClick={() => deleteUser(u.id, u.username)}
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'pdfs' && (
          <div>
            <h3 style={{color: '#ffffff', marginBottom: '16px'}}>All PDFs</h3>
            <table style={styles.table}>
              <thead style={styles.tableHeader}>
                <tr>
                  <th style={styles.th}>Filename</th>
                  <th style={styles.th}>Owner</th>
                  <th style={styles.th}>Visibility</th>
                  <th style={styles.th}>Status</th>
                  <th style={styles.th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pdfs.map(pdf => (
                  <tr key={pdf.id}>
                    <td style={styles.td}>{pdf.filename}</td>
                    <td style={styles.td}>{pdf.owner_username || pdf.username}</td>
                    <td style={styles.td}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: pdf.visibility === 'public' ? '#10A37F' : '#565869',
                        fontSize: '12px'
                      }}>
                        {pdf.visibility}
                      </span>
                    </td>
                    <td style={styles.td}>{pdf.processing_status}</td>
                    <td style={styles.td}>
                      <select
                        value={pdf.visibility}
                        onChange={(e) => updatePdfVisibility(pdf.id, e.target.value)}
                        style={{
                          padding: '4px',
                          backgroundColor: '#40414f',
                          border: '1px solid #565869',
                          borderRadius: '4px',
                          color: '#ffffff'
                        }}
                      >
                        <option value="public">Public</option>
                        <option value="private">Private</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'upload' && (
          <div style={styles.uploadSection}>
            <h3 style={{color: '#ffffff', marginBottom: '16px'}}>Upload Public PDFs</h3>
            <p style={{color: '#8e8ea0', marginBottom: '20px'}}>
              PDFs uploaded here will be accessible to all users in the system.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              style={styles.uploadButton}
              disabled={loading}
            >
              {loading ? 'Uploading...' : 'Select PDFs to Upload'}
            </button>
            <p style={{color: '#8e8ea0', marginTop: '12px', fontSize: '13px'}}>
              You can select multiple PDF files at once
            </p>
            
            {uploadProgress && (
              <div style={styles.progressBar}>
                <div style={{color: '#ffffff', marginBottom: '8px'}}>
                  Processing: {uploadProgress.current} / {uploadProgress.total} files
                </div>
                {uploadProgress.results.map((result, idx) => (
                  <div key={idx} style={{
                    color: result.success ? '#10A37F' : '#ef4444',
                    fontSize: '13px',
                    marginTop: '4px'
                  }}>
                    {result.filename}: {result.success ? '✓ Success' : `✗ ${result.error}`}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Main Chat Application
const MainApp = ({ user, handleLogout, setCurrentView }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pdfs, setPdfs] = useState([]);
  const [showSidebar, setShowSidebar] = useState(true);
  const [uploading, setUploading] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Styles
  const styles = {
    container: {
      display: 'flex',
      height: '100vh',
      backgroundColor: '#343541',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif',
      flexDirection: 'column'
    },
    header: {
      height: '50px',
      backgroundColor: '#40414f',
      borderBottom: '1px solid #565869',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      position: 'relative',
      zIndex: 100
    },
    headerTitle: {
      color: '#ffffff',
      fontSize: '16px',
      fontWeight: '600',
      marginLeft: '12px',
      letterSpacing: '0.5px'
    },
    menuButton: {
      backgroundColor: 'transparent',
      border: 'none',
      color: '#d1d5db',
      cursor: 'pointer',
      padding: '6px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: '4px',
      transition: 'background-color 0.2s'
    },
    mainContent: {
      display: 'flex',
      flex: 1,
      overflow: 'hidden'
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
    adminButton: {
      width: '100%',
      padding: '8px',
      backgroundColor: '#10A37F',
      border: 'none',
      borderRadius: '6px',
      color: '#ffffff',
      cursor: 'pointer',
      marginTop: '8px',
      fontSize: '13px',
      fontWeight: '600'
    },
    mainArea: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#343541'
    },
    messagesArea: {
      flex: 1,
      overflowY: 'auto',
      backgroundColor: '#343541'
    },
    inputArea: {
      borderTop: '1px solid #4d4d5f',
      backgroundColor: '#343541',
      padding: '24px'
    }
  };

  useEffect(() => {
    fetchPDFs();
    setMessages([{
      id: 1,
      type: 'assistant',
      content: `Hello ${user.full_name || user.username}! I can help you analyze PDF documents. ${user.role === 'admin' ? 'As an admin, you can upload public PDFs for all users and manage the system.' : 'Upload your PDFs to get started.'}`,
      timestamp: new Date()
    }]);
  }, [user]);

  // Only poll for updates when there are PDFs being processed
  useEffect(() => {
    const hasProcessingPdfs = pdfs.some(pdf => pdf.processing_status === 'processing');
    
    if (hasProcessingPdfs) {
      const interval = setInterval(fetchPDFs, 5000);
      return () => clearInterval(interval);
    }
  }, [pdfs]);

  const fetchPDFs = async () => {
    try {
      const response = await axios.get('/api/pdfs');
      setPdfs(response.data.pdfs);
    } catch (err) {
      console.error('Error fetching PDFs:', err);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

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

      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        type: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
        responseTime: response.data.response_time,
        timestamp: new Date()
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        type: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        error: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload only PDF files');
      return;
    }

    setUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      console.log(`Uploading: ${file.name}`);
      
      const response = await axios.post('/api/upload', formData);

      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'assistant',
        content: `Successfully uploaded "${file.name}". The file is being processed and will be ready shortly.`,
        timestamp: new Date()
      }]);
      
      // Fetch PDFs immediately and after a delay
      fetchPDFs();
      setTimeout(fetchPDFs, 2000);
      
    } catch (err) {
      console.error('Upload error:', err);
      
      let errorMsg = 'Unknown error';
      if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail;
      } else if (err.response?.status === 401) {
        errorMsg = 'Session expired. Please login again.';
        handleLogout();
        return;
      }
      
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'assistant',
        content: `Error uploading file: ${errorMsg}`,
        timestamp: new Date(),
        error: true
      }]);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeletePDF = async (pdfId, filename) => {
    if (!window.confirm(`Delete "${filename}"?`)) return;

    try {
      await axios.delete(`/api/pdfs/${pdfId}`);
      fetchPDFs();
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'assistant',
        content: `Deleted "${filename}"`,
        timestamp: new Date()
      }]);
    } catch (err) {
      console.error('Error deleting PDF:', err);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div style={styles.container}>
      {/* Header with navigation */}
      <div style={styles.header}>
        <button 
          onClick={() => setShowSidebar(!showSidebar)}
          style={styles.menuButton}
          title={showSidebar ? "Hide sidebar" : "Show sidebar"}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <h1 style={styles.headerTitle}>UTAR HANDBOOK</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ color: '#8e8ea0', fontSize: '12px' }}>
            {pdfs.filter(p => p.processing_status === 'completed').length} PDFs ready
          </span>
        </div>
      </div>

      <div style={styles.mainContent}>
        <div style={styles.sidebar}>
          <div style={styles.sidebarHeader}>
            <div style={styles.userInfo}>
              <div style={{ fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>
                {user.full_name || user.username}
              </div>
              <div style={{ fontSize: '12px', color: '#8e8ea0' }}>{user.email}</div>
              <div style={{ fontSize: '11px', color: '#10A37F', marginTop: '4px' }}>
                Role: {user.role}
              </div>
              {user.role === 'admin' && (
                <button 
                  style={styles.adminButton}
                  onClick={() => setCurrentView('admin')}
                >
                  Admin Panel
                </button>
              )}
              <button 
                style={{ ...styles.adminButton, backgroundColor: 'transparent', border: '1px solid #565869', marginTop: '8px' }}
                onClick={handleLogout}
              >
                Sign Out
              </button>
            </div>

            {/* New Chat Button */}
            <button
              style={{
                width: '100%',
                padding: '10px',
                backgroundColor: 'transparent',
                border: '1px solid #565869',
                borderRadius: '6px',
                color: '#ffffff',
                cursor: 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '12px',
                transition: 'background-color 0.2s'
              }}
              onClick={() => {
                setMessages([{
                  id: 1,
                  type: 'assistant',
                  content: `Hello ${user.full_name || user.username}! I can help you analyze PDF documents. Upload your PDFs to get started.`,
                  timestamp: new Date()
                }]);
              }}
              onMouseEnter={(e) => e.target.style.backgroundColor = '#2a2b32'}
              onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
            >
              <span style={{ fontSize: '18px' }}>+</span> New chat
            </button>
          </div>
          
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
            <div style={{ marginBottom: '16px', color: '#8e8ea0', fontSize: '12px', fontWeight: '500', textTransform: 'uppercase' }}>
              Your PDFs ({pdfs.length})
            </div>
            {pdfs.length === 0 ? (
              <div style={{ 
                color: '#8e8ea0', 
                fontSize: '13px', 
                textAlign: 'center', 
                padding: '20px' 
              }}>
                No PDFs uploaded yet
              </div>
            ) : (
              pdfs.map(pdf => (
                <div key={pdf.id} style={{ 
                  backgroundColor: '#2a2b32', 
                  borderRadius: '6px', 
                  padding: '12px', 
                  marginBottom: '8px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#3a3b42'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#2a2b32'}
                >
                  <div style={{ fontWeight: '500', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>📄</span> {pdf.filename}
                  </div>
                  <div style={{ fontSize: '12px', color: '#8e8ea0' }}>
                    {pdf.visibility === 'public' ? '🌐 Public' : '🔒 Private'}
                    {pdf.is_owner && ' • Owner'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                    Status: {pdf.processing_status === 'completed' ? '✓ Ready' : '⏳ Processing...'}
                  </div>
                  {pdf.is_owner && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeletePDF(pdf.id, pdf.filename);
                      }}
                      style={{ 
                        marginTop: '8px',
                        padding: '4px 8px',
                        backgroundColor: 'transparent',
                        border: '1px solid #565869',
                        borderRadius: '4px',
                        color: '#ef4444',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Delete
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        <div style={styles.mainArea}>
          <div style={styles.messagesArea}>
            {messages.map(message => (
              <div key={message.id} style={{ 
                padding: '24px', 
                backgroundColor: message.type === 'assistant' ? '#444654' : '#343541',
                borderBottom: '1px solid #4d4d5f'
              }}>
                <div style={{ maxWidth: '48rem', margin: '0 auto', display: 'flex', gap: '24px' }}>
                  <div style={{ 
                    width: '30px', 
                    height: '30px', 
                    borderRadius: '2px',
                    backgroundColor: message.type === 'user' ? '#5436DA' : '#10A37F',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                    fontSize: '14px',
                    fontWeight: '600',
                    flexShrink: 0
                  }}>
                    {message.type === 'user' ? user.username.charAt(0).toUpperCase() : 'A'}
                  </div>
                  <div style={{ flex: 1, color: '#d1d5db', fontSize: '15px', lineHeight: '1.75' }}>
                    <div style={{ marginBottom: '4px', fontWeight: '600', fontSize: '14px' }}>
                      {message.type === 'user' ? 'You' : 'UTAR Assistant'}
                    </div>
                    {message.content}
                    {message.sources && message.sources.length > 0 && (
                      <div style={{ 
                        marginTop: '12px', 
                        padding: '12px', 
                        backgroundColor: 'rgba(16, 163, 127, 0.1)', 
                        borderRadius: '6px',
                        fontSize: '13px',
                        color: '#10A37F'
                      }}>
                        <div style={{ fontWeight: '600', marginBottom: '8px' }}>Sources:</div>
                        {message.sources.map((source, idx) => (
                          <div key={idx}>📄 {source.filename} - Page {source.page}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div style={{ padding: '24px', backgroundColor: '#444654' }}>
                <div style={{ maxWidth: '48rem', margin: '0 auto', display: 'flex', gap: '24px' }}>
                  <div style={{ 
                    width: '30px', 
                    height: '30px', 
                    borderRadius: '2px',
                    backgroundColor: '#10A37F',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                    fontSize: '14px',
                    fontWeight: '600',
                    flexShrink: 0
                  }}>
                    A
                  </div>
                  <div style={{ flex: 1, color: '#d1d5db' }}>
                    <div style={{ marginBottom: '4px', fontWeight: '600', fontSize: '14px' }}>
                      UTAR Assistant
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <span>Thinking</span>
                      <span className="animate-pulse">...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div style={styles.inputArea}>
            <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
              <div style={{ 
                display: 'flex', 
                gap: '12px',
                backgroundColor: '#40414f',
                borderRadius: '12px',
                border: '1px solid #565869',
                padding: '12px'
              }}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0])}
                  style={{ display: 'none' }}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  title="Upload PDF"
                  style={{ 
                    padding: '8px',
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: uploading ? '#565869' : '#8e8ea0',
                    cursor: uploading ? 'not-allowed' : 'pointer',
                    fontSize: '20px'
                  }}
                >
                  {uploading ? '⏳' : '📎'}
                </button>
                <input
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                  placeholder={pdfs.some(p => p.processing_status === 'completed') ? "Ask about your PDFs..." : "Upload a PDF to get started..."}
                  disabled={isLoading}
                  style={{ 
                    flex: 1,
                    backgroundColor: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: '#ffffff',
                    fontSize: '15px'
                  }}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isLoading}
                  style={{ 
                    padding: '8px 16px',
                    backgroundColor: inputMessage.trim() && !isLoading ? '#10A37F' : 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    color: inputMessage.trim() && !isLoading ? '#ffffff' : '#565869',
                    cursor: inputMessage.trim() && !isLoading ? 'pointer' : 'not-allowed',
                    fontSize: '14px',
                    fontWeight: '600'
                  }}
                >
                  Send
                </button>
              </div>
              {uploading && (
                <div style={{ marginTop: '8px', color: '#8e8ea0', fontSize: '13px', textAlign: 'center' }}>
                  Uploading file...
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
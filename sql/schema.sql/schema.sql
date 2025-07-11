-- RBAC Memory Management System Schema
-- This file contains all table definitions and constraints

-- ==========================================
-- ORGANIZATIONAL STRUCTURE TABLES
-- ==========================================

-- Departments table
CREATE TABLE IF NOT EXISTS departments (
    department_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_name VARCHAR(100) NOT NULL,
    department_code VARCHAR(10) UNIQUE NOT NULL DEFAULT generate_unique_code('DEPT-'),
    parent_department_id UUID REFERENCES departments(department_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    department_head_id UUID, 
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    project_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_name VARCHAR(100) NOT NULL,
    project_code VARCHAR(10) UNIQUE NOT NULL DEFAULT generate_unique_code('PRJ-'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    project_lead_id UUID,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    start_date DATE,
    end_date DATE,
    status project_status DEFAULT 'planning',
    classification classification_type DEFAULT 'internal',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RBAC Core Tables

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    department_id UUID REFERENCES departments(department_id) ON DELETE SET NULL,
    employee_id VARCHAR(20) UNIQUE,
    hire_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    phone_number VARCHAR(20),
    classification_level classification_type DEFAULT 'internal',
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(user_id) 
);

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    role_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_name VARCHAR(100) NOT NULL,
    role_code VARCHAR(10) UNIQUE NOT NULL DEFAULT generate_unique_code('ROLE-'),
    description TEXT,
    hierarchy_level INTEGER NOT NULL CHECK (hierarchy_level >= 1 AND hierarchy_level <= 10),
    parent_role_id UUID REFERENCES roles(role_id) ON DELETE SET NULL,
    can_manage_users BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    permission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    permission_name VARCHAR(100) NOT NULL,
    permission_code VARCHAR(50) UNIQUE NOT NULL DEFAULT generate_unique_code('PERM-'),
    resource_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    scope access_scope_type DEFAULT 'own',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_system_permission BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(user_id)
);

-- User-Role assignments
CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by UUID REFERENCES users(user_id),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    assignment_reason TEXT,
    PRIMARY KEY (user_id, role_id)
);

-- Role-Permission mappings
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id UUID REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(permission_id) ON DELETE CASCADE,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES users(user_id),
    conditions JSONB, -- Additional conditions for the permission
    PRIMARY KEY (role_id, permission_id)
);

-- Project team memberships
CREATE TABLE IF NOT EXISTS project_members (
    project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    role_in_project VARCHAR(50) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    permissions JSONB, -- Project-specific permissions
    PRIMARY KEY (project_id, user_id)
);

-- ==========================================
-- MEMORY MANAGEMENT TABLES
-- ==========================================

-- Short-term memory (session-based)
CREATE TABLE IF NOT EXISTS rbac_session_memory (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_end TIMESTAMP,
    messages JSONB NOT NULL,
    context_data JSONB,
    agent_name VARCHAR(100),
    agent_version VARCHAR(20),
    project_id UUID REFERENCES projects(project_id),
    department_id UUID REFERENCES departments(department_id),
    security_level classification_type DEFAULT 'internal',
    ip_address INET,
    user_agent TEXT,
    session_duration INTEGER, -- in seconds
    access_log JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mid-term memory (summaries and decisions)
CREATE TABLE IF NOT EXISTS rbac_mid_term_memory (
    summary_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    original_content_hash VARCHAR(64),
    conversation_ids UUID[] NOT NULL,
    summary_type VARCHAR(50) DEFAULT 'conversation',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agents_associated VARCHAR(100)[],
    tags VARCHAR(50)[],
    entities JSONB, -- Named entities extracted
    sentiment_score DECIMAL(3,2), -- -1 to 1
    importance_score DECIMAL(3,2), -- 0 to 1
    persona_attached VARCHAR(100),
    task_id UUID,
    project_id UUID REFERENCES projects(project_id),
    department_id UUID REFERENCES departments(department_id),
    classification_level classification_type DEFAULT 'internal',
    access_scope access_scope_type DEFAULT 'department',
    retention_period INTEGER DEFAULT 90, -- days
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Long-term memory (knowledge base)
CREATE TABLE IF NOT EXISTS rbac_long_term_memory (
    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255),
    content TEXT NOT NULL,
    content_hash VARCHAR(64),
    embedding VECTOR(1536), -- OpenAI embedding dimension
    metadata JSONB NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    source_type VARCHAR(50),
    source_url VARCHAR(500),
    file_path VARCHAR(500),
    file_size INTEGER,
    mime_type VARCHAR(100),
    project_id UUID REFERENCES projects(project_id),
    department_id UUID REFERENCES departments(department_id),
    created_by UUID REFERENCES users(user_id),
    last_modified_by UUID REFERENCES users(user_id),
    classification_level classification_type DEFAULT 'internal',
    access_scope access_scope_type DEFAULT 'project',
    retention_period INTEGER DEFAULT 2555, -- days (7 years)
    keywords VARCHAR(100)[],
    entities JSONB,
    language VARCHAR(10) DEFAULT 'en',
    word_count INTEGER,
    version INTEGER DEFAULT 1,
    parent_memory_id UUID REFERENCES rbac_long_term_memory(memory_id),
    is_archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Memory access control lists
CREATE TABLE IF NOT EXISTS memory_access_control (
    access_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL,
    memory_type memory_tier_type NOT NULL,
    user_id UUID REFERENCES users(user_id),
    role_id UUID REFERENCES roles(role_id),
    department_id UUID REFERENCES departments(department_id),
    project_id UUID REFERENCES projects(project_id),
    permission_type VARCHAR(20) NOT NULL,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES users(user_id),
    expires_at TIMESTAMP,
    conditions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Constraints
    CONSTRAINT memory_access_check CHECK (
        (user_id IS NOT NULL) OR 
        (role_id IS NOT NULL) OR 
        (department_id IS NOT NULL) OR 
        (project_id IS NOT NULL)
    )
);

-- ==========================================
-- AUDIT AND MONITORING TABLES
-- ==========================================

-- Comprehensive audit log
CREATE TABLE IF NOT EXISTS rbac_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    session_id UUID,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    execution_time_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User sessions tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    device_info JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    logout_reason VARCHAR(50),
    logout_at TIMESTAMP
);

-- Security events
CREATE TABLE IF NOT EXISTS security_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    user_id UUID REFERENCES users(user_id),
    ip_address INET,
    user_agent TEXT,
    event_data JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolved_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- INDEXES FOR PERFORMANCE
-- ==========================================

-- User indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_department ON users(department_id) WHERE is_active = TRUE;
CREATE INDEX idx_users_employee_id ON users(employee_id);
CREATE INDEX idx_users_active ON users(is_active);

-- Role and permission indexes
CREATE INDEX idx_roles_hierarchy ON roles(hierarchy_level);
CREATE INDEX idx_roles_code ON roles(role_code);
CREATE INDEX idx_permissions_resource ON permissions(resource_type, action);
CREATE INDEX idx_permissions_scope ON permissions(scope);

-- User-role indexes
CREATE INDEX idx_user_roles_user ON user_roles(user_id) WHERE is_active = TRUE;
CREATE INDEX idx_user_roles_role ON user_roles(role_id) WHERE is_active = TRUE;
CREATE INDEX idx_user_roles_expires ON user_roles(expires_at) WHERE expires_at IS NOT NULL;

-- Project indexes
CREATE INDEX idx_projects_department ON projects(department_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_code ON projects(project_code);
CREATE INDEX idx_project_members_user ON project_members(user_id) WHERE is_active = TRUE;

-- Memory indexes
CREATE INDEX idx_session_memory_user ON rbac_session_memory(user_id);
CREATE INDEX idx_session_memory_project ON rbac_session_memory(project_id);
CREATE INDEX idx_session_memory_created ON rbac_session_memory(created_at DESC);

CREATE INDEX idx_mid_term_memory_user ON rbac_mid_term_memory(user_id);
CREATE INDEX idx_mid_term_memory_project ON rbac_mid_term_memory(project_id);
CREATE INDEX idx_mid_term_memory_timestamp ON rbac_mid_term_memory(timestamp DESC);
CREATE INDEX idx_mid_term_memory_tags ON rbac_mid_term_memory USING GIN(tags);

CREATE INDEX idx_long_term_memory_project ON rbac_long_term_memory(project_id);
CREATE INDEX idx_long_term_memory_department ON rbac_long_term_memory(department_id);
CREATE INDEX idx_long_term_memory_created_by ON rbac_long_term_memory(created_by);
CREATE INDEX idx_long_term_memory_created_at ON rbac_long_term_memory(created_at DESC);
CREATE INDEX idx_long_term_memory_keywords ON rbac_long_term_memory USING GIN(keywords);
CREATE INDEX idx_long_term_memory_metadata ON rbac_long_term_memory USING GIN(metadata);
CREATE INDEX idx_long_term_memory_classification ON rbac_long_term_memory(classification_level);
CREATE INDEX idx_long_term_memory_content_hash ON rbac_long_term_memory(content_hash);

-- Audit indexes
CREATE INDEX idx_audit_log_user ON rbac_audit_log(user_id);
CREATE INDEX idx_audit_log_timestamp ON rbac_audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_action ON rbac_audit_log(action);
CREATE INDEX idx_audit_log_resource ON rbac_audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_log_success ON rbac_audit_log(success);

-- Session indexes
CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_user_sessions_active ON user_sessions(is_active) WHERE is_active = TRUE;

-- Security event indexes
CREATE INDEX idx_security_events_type ON security_events(event_type);
CREATE INDEX idx_security_events_user ON security_events(user_id);
CREATE INDEX idx_security_events_created ON security_events(created_at DESC);
CREATE INDEX idx_security_events_resolved ON security_events(resolved);

-- ==========================================
-- TRIGGERS
-- ==========================================

-- Auto-update timestamps
CREATE TRIGGER update_departments_updated_at BEFORE UPDATE ON departments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_permissions_updated_at BEFORE UPDATE ON permissions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_mid_term_memory_updated_at BEFORE UPDATE ON rbac_mid_term_memory FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_long_term_memory_updated_at BEFORE UPDATE ON rbac_long_term_memory FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_session_memory_updated_at BEFORE UPDATE ON rbac_session_memory FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- VIEWS FOR COMMON QUERIES
-- ==========================================

-- User permissions view
CREATE VIEW user_permissions_view AS
SELECT 
    u.user_id,
    u.username,
    u.email,
    u.department_id,
    d.department_name,
    r.role_name,
    r.hierarchy_level,
    p.permission_code,
    p.resource_type,
    p.action,
    p.scope
FROM users u
JOIN user_roles ur ON u.user_id = ur.user_id AND ur.is_active = TRUE
JOIN roles r ON ur.role_id = r.role_id
JOIN role_permissions rp ON r.role_id = rp.role_id
JOIN permissions p ON rp.permission_id = p.permission_id
LEFT JOIN departments d ON u.department_id = d.department_id
WHERE u.is_active = TRUE;

-- Memory access summary view
CREATE VIEW memory_access_summary AS
SELECT 
    u.user_id,
    u.username,
    COUNT(DISTINCT sm.session_id) as short_term_sessions,
    COUNT(DISTINCT mm.summary_id) as mid_term_summaries,
    COUNT(DISTINCT lm.memory_id) as long_term_memories
FROM users u
LEFT JOIN rbac_session_memory sm ON u.user_id = sm.user_id
LEFT JOIN rbac_mid_term_memory mm ON u.user_id = mm.user_id
LEFT JOIN rbac_long_term_memory lm ON u.user_id = lm.created_by
WHERE u.is_active = TRUE
GROUP BY u.user_id, u.username;

-- Project team view
CREATE VIEW project_team_view AS
SELECT 
    p.project_id,
    p.project_name,
    p.project_code,
    p.status,
    u.user_id,
    u.username,
    u.first_name,
    u.last_name,
    pm.role_in_project,
    pm.joined_at,
    pm.is_active
FROM projects p
JOIN project_members pm ON p.project_id = pm.project_id
JOIN users u ON pm.user_id = u.user_id
WHERE pm.is_active = TRUE AND u.is_active = TRUE;

-- ==========================================
-- SECURITY CONSTRAINTS
-- ==========================================

-- Add foreign key constraints that were deferred
ALTER TABLE departments ADD CONSTRAINT fk_departments_head 
    FOREIGN KEY (department_head_id) REFERENCES users(user_id);

ALTER TABLE projects ADD CONSTRAINT fk_projects_lead 
    FOREIGN KEY (project_lead_id) REFERENCES users(user_id);

-- Row Level Security (RLS) - commented out for now, enable in production
-- ALTER TABLE rbac_session_memory ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE rbac_mid_term_memory ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE rbac_long_term_memory ENABLE ROW LEVEL SECURITY;

-- ==========================================
-- COMPLETION MESSAGE
-- ==========================================

DO $$
BEGIN
    RAISE NOTICE 'RBAC Memory Management schema created successfully at %', CURRENT_TIMESTAMP;
    RAISE NOTICE 'Total tables created: %', (
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    );
END $$;
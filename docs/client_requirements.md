# MeatTrace System - Client Requirements Document

**Project Name:** MeatTrace - Meat Supply Chain Traceability Platform  
**Document Version:** 1.0  
**Date:** December 2024  
**Client:** Ministry of Agriculture & Food Safety Authority  
**Prepared By:** MeatTrace Development Team

---

## 1. EXECUTIVE SUMMARY

### 1.1 Project Overview
The MeatTrace platform is required to provide end-to-end traceability of meat products from farm to consumer in compliance with international food safety standards (HACCP, ISO 22000) and local regulatory requirements. The system must track the complete journey of livestock through slaughter, processing, distribution, and retail sale while ensuring food safety, quality control, and regulatory compliance.

### 1.2 Business Objectives
1. **Food Safety Assurance** - Enable rapid tracing of meat products during food safety incidents or disease outbreaks
2. **Regulatory Compliance** - Meet government requirements for livestock tracking and meat product certification
3. **Supply Chain Transparency** - Provide visibility to all stakeholders from farmers to consumers
4. **Quality Management** - Implement rejection/appeal workflows for quality control
5. **Consumer Confidence** - Enable consumers to verify product authenticity and origin via QR codes

### 1.3 Target Users
- **Farmers** - Livestock owners registering and managing animals
- **Processing Unit Staff** - Abattoir workers, quality controllers, managers
- **Shop Owners/Staff** - Retail outlet personnel
- **Government Inspectors** - Regulatory auditors and certifiers
- **System Administrators** - Platform managers
- **Consumers** - End users scanning QR codes for product information

---

## 2. FUNCTIONAL REQUIREMENTS

### 2.1 User Management & Authentication

#### FR-UM-001: Multi-Role User System
**Priority:** CRITICAL  
**Description:** The system must support multiple distinct user roles with hierarchical permissions.

**Required User Roles:**
- **Farmer** - Livestock owners
- **Processing Unit Owner** - Abattoir/processing facility owners
- **Processing Unit Manager** - Facility supervisors
- **Processing Unit Supervisor** - Shift supervisors
- **Processing Unit Worker** - Line workers
- **Quality Control Officer** - Inspection personnel
- **Shop Owner** - Retail outlet owners
- **Shop Manager** - Store managers
- **Salesperson** - Store staff
- **Government Inspector** - Regulatory auditors
- **System Administrator** - Platform managers

#### FR-UM-002: User Profile Management
**Priority:** HIGH  
**Requirements:**
- User registration with email/phone verification
- Profile completion wizard with progressive disclosure
- Avatar upload capability
- Contact information (phone, address)
- Geographic coordinates (auto-geocoded from address for farmers)
- Preferred species selection (for farmers)
- Notification preferences (email, SMS, push, in-app)
- Bio/description field

#### FR-UM-003: Multi-Tenant Access Control
**Priority:** CRITICAL  
**Requirements:**
- Users can belong to multiple processing units with different roles
- Users can belong to multiple shops with different roles
- Granular permissions system beyond basic role assignment
- Invitation workflow for adding users to entities
- Suspension/deactivation capability for users
- Audit trail of all user management actions

#### FR-UM-004: Security & Compliance
**Priority:** CRITICAL  
**Requirements:**
- Secure authentication (token-based)
- Security logging (login attempts, access violations)
- Session management
- IP address tracking for security events

### 2.2 Livestock Registration & Management

#### FR-LM-001: Animal Registration
**Priority:** CRITICAL  
**Requirements:**
- Farmers can register animals with following attributes:
  - Auto-generated unique animal ID
  - Optional custom animal name/tag
  - Species (Cow, Pig, Chicken, Sheep, Goat)
  - Breed
  - Age (in months with auto-conversion to years/days)
  - Gender (Male/Female/Unknown)
  - Live weight
  - Health status
  - Photo upload
  - Farmer's address with auto-geocoding
  - Notes/remarks
- Support for batch registration of multiple animals
- QR code generation for each animal

#### FR-LM-002: Animal Lifecycle Tracking
**Priority:** CRITICAL  
**Requirements:**
- Track animal status changes: registered → transferred → received → slaughtered → processed
- Record slaughter date/time
- Track weight changes (live weight → remaining weight)
- Transfer animals to processing units with approval workflow
- Processing unit receives and confirms animal receipt
- Maintain complete audit trail of ownership/custody

#### FR-LM-003: Animal Health & Rejection Workflow
**Priority:** HIGH  
**Requirements:**
- Rejection status workflow: Pending Review → Rejected → Appealed → Resolved
- Quality control officers can reject animals with:
  - Rejection category
  - Specific reason
  - Detailed notes
  - Timestamp and rejector information
  - Associated processing unit
- Farmers can appeal rejections with:
  - Appeal status: Pending → Approved → Denied → Resolved
  - Appeal notes
  - Resolution tracking
- Automated notifications for rejections and appeals

### 2.3 Slaughter & Processing

#### FR-SP-001: Slaughter Operation
**Priority:** CRITICAL  
**Requirements:**
- Worker can mark animal as slaughtered
- Record slaughter date/time automatically
- Generate carcass measurements with two types:
  - **Whole Carcass**: Total weight
  - **Split Carcass**: Separate weights for head, torso, left carcass, right carcass, feet, organs
- Automatically create slaughter parts based on carcass type
- Support for different split options:
  - Whole carcass (no split)
  - Left/Right sides
  - Detailed breakdown (head, feet, organs, torso, legs)

#### FR-SP-002: Slaughter Part Management
**Priority:** CRITICAL  
**Requirements:**
- Auto-generate unique part IDs
- Track part types: whole carcass, left side, right side, head, feet, internal organs, torso, front legs, hind legs
- Record weight and weight unit (kg, lbs, g)
- Track remaining weight for product creation
- Mark parts as "used in product"
- Support transfer of specific parts to other processing units
- Rejection/appeal workflow for parts (same as animals)

#### FR-SP-003: Product Creation
**Priority:** CRITICAL  
**Requirements:**
- Create products from animals or specific slaughter parts
- Record product details:
  - Name
  - Batch number
  - Product type (Meat, Milk, Eggs, Wool)
  - Weight and unit
  - Price
  - Description
  - Manufacturer
  - Product category
- Track product ingredients (which parts were used)
- Generate QR code for each product automatically
- Track quantity and remaining inventory

### 2.4 Transfer & Distribution

#### FR-TD-001: Transfer Request System
**Priority:** HIGH  
**Requirements:**
- Support transfer of:
  - Live animals between processing units
  - Slaughter parts between processing units
  - Finished products to shops
- Transfer approval workflow
- Transfer request tracking: requested → approved → transferred → received
- Record transfer/receipt dates and personnel
- Partial receipt support (quantity transferred vs. quantity received)

#### FR-TD-002: Product Reception at Shops
**Priority:** CRITICAL  
**Requirements:**
- Shop receives notification of incoming products
- Shop user confirms receipt with:
  - Received quantity
  - Receipt date/time
  - Product condition
- Automatic inventory update upon receipt
- Receipt record generation
- Rejection capability with reasons

### 2.5 Inventory Management

#### FR-IM-001: Shop Inventory Tracking
**Priority:** CRITICAL  
**Requirements:**
- Track current stock levels per product per shop
- Set minimum stock level thresholds
- Low stock alerts/notifications
- Automatic inventory updates on:
  - Product receipt
  - Product sale
  - Product waste/spoilage
- Inventory audit logs

### 2.6 Sales & Orders

#### FR-SO-001: Customer Order Management
**Priority:** HIGH  
**Requirements:**
- Customers can place orders at shops with:
  - Multiple products (order items)
  - Delivery address
  - Order notes
  - QR code for order tracking
- Order status workflow: Pending → Confirmed → Preparing → Ready → Delivered → Cancelled
- Automatic total calculation
- Order update tracking (created_at, updated_at)

#### FR-SO-002: Direct Sales
**Priority:** HIGH  
**Requirements:**
- Record walk-in sales at shops with:
  - Customer name and phone (optional)
  - Multiple products (sale items)
  - Payment method
  - QR code for receipt
- Sale items with quantity, unit price, and auto-calculated subtotal
- Automatic inventory deduction

### 2.7 Product Traceability

#### FR-PT-001: Complete Product Timeline
**Priority:** CRITICAL  
**Requirements:**
- Track product journey through processing stages:
  - Received
  - Inspected
  - Processed
  - Packaged
  - Ready for Transfer
  - Transferred
  - Quality Checked
- Record timeline events with:
  - Timestamp
  - Location
  - Action performed
  - Stage in workflow
- Chronological event history

#### FR-PT-002: Aggregated Product Information
**Priority:** HIGH  
**Requirements:**
- Pre-computed denormalized product information including:
  - Product name and batch number
  - Source animal ID
  - Complete timeline events (JSON)
  - Carcass measurement data
  - Inventory count
  - Receipt count
  - Order count
- Enable fast traceability lookups without complex joins

#### FR-PT-003: QR Code Traceability
**Priority:** CRITICAL  
**Requirements:**
- Consumers can scan product QR code to view:
  - Farm origin and farmer details
  - Animal information (species, age, health)
  - Slaughter date and location
  - Processing timeline
  - Product batch and creation date
  - Certifications and compliance audits
  - Shop location
- Support for order QR codes to track order status

### 2.8 Compliance & Certification

#### FR-CC-001: Compliance Audits
**Priority:** CRITICAL  
**Requirements:**
- Track regulatory inspections for:
  - Processing units
  - Shops
  - Farmers
- Audit attributes:
  - Auditor (government inspector)
  - Audit date
  - Status (Scheduled, In Progress, Completed, Failed)
  - Outcome (Pass, Fail, Conditional Pass)
  - Score (0-100)
  - Findings/recommendations
  - Violation count
- Scheduled vs. surprise audits
- Audit history and trending

#### FR-CC-002: Certification Management
**Priority:** HIGH  
**Requirements:**
- Track certifications for processing units, shops, and farmers:
  - HACCP certification
  - ISO 22000 (Food Safety Management)
  - Halal certification
  - Organic certification
  - Custom certifications
- Certificate attributes:
  - Certificate number
  - Issuing authority
  - Issue date and expiry date
  - Status (Valid, Expired, Suspended, Revoked)
- Expiry notifications and renewal reminders

#### FR-CC-003: Registration Application System
**Priority:** HIGH  
**Requirements:**
- New entities apply for government approval
- Application workflow:
  - User submits application with:
    - Entity name and type
    - Business license number
    - Supporting documents (uploaded files)
  - Government official reviews
  - Status: Pending → Under Review → Approved → Rejected
- Document management for licenses/permits

### 2.9 Notification System

#### FR-NS-001: Multi-Channel Notifications
**Priority:** HIGH  
**Requirements:**
- Support notification channels:
  - In-app notifications
  - Email
  - SMS
  - Push notifications (mobile app)
- Notification types:
  - Join requests
  - Join approval/rejection
  - User invitations
  - Role changes
  - Profile update requirements
  - Account verification
  - Animal rejections
  - Appeal submissions/decisions
  - System alerts
  - Maintenance notices
  - Custom messages

#### FR-NS-002: Notification Management
**Priority:** MEDIUM  
**Requirements:**
- Mark notifications as read/unread
- Dismiss notifications
- Archive notifications
- Bulk operations (mark all read, bulk delete)
- Unread count badge
- Filter by:
  - Read/unread status
  - Archived status
  - Priority
  - Type
  - Date range

#### FR-NS-003: Notification Templates
**Priority:** MEDIUM  
**Requirements:**
- Reusable templates with variable substitution
- Template types for each notification scenario
- Support for subject and body content
- Active/inactive status for templates

#### FR-NS-004: Scheduled & Rate-Limited Notifications
**Priority:** LOW  
**Requirements:**
- Schedule notifications for future delivery
- Recurring notifications
- Rate limiting per user per channel (prevent spam)
- Delivery tracking and retry logic
- Failed delivery reporting

### 2.10 Join Requests & User Invitations

#### FR-JR-001: Join Request Workflow
**Priority:** HIGH  
**Requirements:**
- Users can request to join:
  - Processing units (as worker, supervisor, etc.)
  - Shops (as manager, salesperson, etc.)
- Request attributes:
  - Requested role
  - Status: Pending → Under Review → Approved → Rejected
  - Reviewer information
  - Review date
- Notifications to entity owners/managers
- Ability to withdraw pending requests
- Batch approval/rejection capability

#### FR-JR-002: User Invitation System
**Priority:** MEDIUM  
**Requirements:**
- Entity owners/managers can invite users
- Track who invited whom (invited_by)
- Invitation date and acceptance date
- Invitee receives notification
- Invitation expiry (optional)

### 2.11 Quality Control & Rejection Management

#### FR-QC-001: Rejection Tracking
**Priority:** CRITICAL  
**Requirements:**
- Comprehensive rejection tracking for:
  - Animals
  - Slaughter parts
  - Products
- Rejection record includes:
  - Category (e.g., disease, quality, weight, documentation)
  - Specific reason (detailed cause)
  - Notes from quality control officer
  - Rejected by (user)
  - Rejected at (processing unit)
  - Rejection date
- Link rejections to parent entity (animal, part, product)

#### FR-QC-002: Appeal Process
**Priority:** HIGH  
**Requirements:**
- Farmers/suppliers can appeal rejections
- Appeal submission with notes/justification
- Appeal review workflow
- Appeal status: Pending → Approved → Denied → Resolved
- Resolution date tracking
- Notifications at each appeal stage

### 2.12 Geographic & Mapping Features

#### FR-GM-001: Location Tracking
**Priority:** MEDIUM  
**Requirements:**
- Store geographic coordinates for:
  - Processing units
  - Shops
  - Farmers (via user profile address)
- Auto-geocoding service integration
  - Convert addresses to latitude/longitude
  - Fallback to manual coordinate entry
- Map display of:
  - Farm locations
  - Processing unit locations
  - Shop locations
  - Product distribution routes

### 2.13 Reporting & Analytics

#### FR-RA-001: Activity Monitoring
**Priority:** MEDIUM  
**Requirements:**
- Activity feed for farmers showing:
  - Animals registered
  - Slaughter events
  - Product creations
  - Transfers
  - Rejections/Appeals
- Activity type categorization
- Metadata storage (JSON) for flexible analytics

#### FR-RA-002: Performance Metrics
**Priority:** LOW  
**Requirements:**
- Track operational metrics for processing units and shops:
  - Processing efficiency
  - Yield rates
  - Throughput
  - Waste percentage
  - Quality scores
- Metric types: count, percentage, rate, score
- Time-period tracking (daily, weekly, monthly)

#### FR-RA-003: System Health Monitoring
**Priority:** MEDIUM  
**Requirements:**
- Monitor system components:
  - Database health
  - API response times
  - Background job status
  - Integration services (geocoding, notifications)
- Component status: Healthy, Degraded, Down
- Automated alerts for degraded/down components

### 2.14 System Administration

#### FR-SA-001: System Configuration
**Priority:** MEDIUM  
**Requirements:**
- Configurable system settings:
  - Feature flags (enable/disable features)
  - Validation rules
  - Approval workflows
  - Required certifications
  - Notification settings
- Configuration history tracking
- Configuration versioning

#### FR-SA-002: Data Management
**Priority:** LOW  
**Requirements:**
- Backup scheduling and management
- Data export functionality (CSV, JSON, PDF)
- Data import with validation
- Backup encryption
- Retention policies

#### FR-SA-003: System Alerts
**Priority:** HIGH  
**Requirements:**
- Generate alerts for:
  - Performance degradation
  - Security events
  - Compliance issues (expiring certifications)
  - System errors
- Alert categories: Info, Warning, Error, Critical
- Alert acknowledgment by administrators
- Affected entity tracking (processing unit, shop, user)

---

## 3. NON-FUNCTIONAL REQUIREMENTS

### 3.1 Performance
- **NFR-P-001:** API response time < 200ms for 95% of requests
- **NFR-P-002:** Support 1000 concurrent users
- **NFR-P-003:** Database query optimization for traceability lookups
- **NFR-P-004:** Denormalized product info table for fast consumer QR lookups

### 3.2 Scalability
- **NFR-S-001:** Support 100,000+ animals in system
- **NFR-S-002:** Handle 10,000+ products
- **NFR-S-003:** Accommodate 1,000+ processing units and shops
- **NFR-S-004:** Partition large tables (audit trails) for performance

### 3.3 Security
- **NFR-SEC-001:** All data in transit encrypted (HTTPS)
- **NFR-SEC-002:** Sensitive data encrypted at rest
- **NFR-SEC-003:** Token-based authentication
- **NFR-SEC-004:** Role-based access control with granular permissions
- **NFR-SEC-005:** Comprehensive audit logging
- **NFR-SEC-006:** IP-based access restrictions for admin functions
- **NFR-SEC-007:** Session timeout after 30 minutes of inactivity

### 3.4 Reliability & Availability
- **NFR-R-001:** 99.5% uptime SLA
- **NFR-R-002:** Automated daily backups
- **NFR-R-003:** Disaster recovery plan with 24-hour RTO
- **NFR-R-004:** Graceful error handling and user-friendly error messages

### 3.5 Usability
- **NFR-U-001:** Mobile-responsive design for farmers in field
- **NFR-U-002:** Multi-language support (English, Swahili)
- **NFR-U-003:** Accessibility compliance (WCAG 2.1 Level AA)
- **NFR-U-004:** Progressive profile completion (step-by-step wizard)
- **NFR-U-005:** Contextual help and tooltips

### 3.6 Compliance & Standards
- **NFR-C-001:** HACCP compliance tracking
- **NFR-C-002:** ISO 22000 food safety standards support
- **NFR-C-003:** Local regulatory compliance (Ministry of Agriculture)
- **NFR-C-004:** GDPR-compliant data handling (for export markets)
- **NFR-C-005:** Halal certification tracking

### 3.7 Integration
- **NFR-I-001:** RESTful API for mobile app integration
- **NFR-I-002:** Geocoding service integration (OpenStreetMap/Google Maps)
- **NFR-I-003:** SMS gateway integration for notifications
- **NFR-I-004:** Email service integration
- **NFR-I-005:** Push notification service for mobile apps
- **NFR-I-006:** Export APIs for government reporting systems

### 3.8 Data Integrity
- **NFR-D-001:** Complete audit trail for all data changes
- **NFR-D-002:** Immutable traceability records
- **NFR-D-003:** Data validation at all entry points
- **NFR-D-004:** Referential integrity enforcement
- **NFR-D-005:** Automated data consistency checks

---

## 4. USER STORIES

### 4.1 Farmer Stories
**US-F-001:** As a farmer, I want to register my animals with photos and health details so I can track them through the supply chain.

**US-F-002:** As a farmer, I want to receive notifications when my animals are rejected so I can quickly appeal the decision.

**US-F-003:** As a farmer, I want to view my complete animal inventory and their current status/location.

**US-F-004:** As a farmer, I want to transfer animals to processing units for slaughter.

**US-F-005:** As a farmer, I want to see an activity feed of all my livestock operations.

### 4.2 Processing Unit Stories
**US-PU-001:** As a processing unit manager, I want to receive animal transfers and confirm their receipt.

**US-PU-002:** As a quality control officer, I want to reject unhealthy animals with detailed reasons.

**US-PU-003:** As a processing worker, I want to record slaughter operations and create slaughter parts.

**US-PU-004:** As a processing worker, I want to create finished products from slaughter parts and track ingredients used.

**US-PU-005:** As a processing unit owner, I want to invite staff members with specific roles and permissions.

**US-PU-006:** As a processing unit manager, I want to track certification expiry dates and receive renewal reminders.

### 4.3 Shop Stories
**US-S-001:** As a shop manager, I want to receive product transfers from processing units.

**US-S-002:** As a shop employee, I want to record walk-in sales and print receipts.

**US-S-003:** As a shop manager, I want to track inventory levels and receive low-stock alerts.

**US-S-004:** As a shop owner, I want to manage customer orders from placement to delivery.

**US-S-005:** As a shop staff, I want to reject received products that don't meet quality standards.

### 4.4 Consumer Stories
**US-C-001:** As a consumer, I want to scan a QR code on a meat product to see its full traceability history.

**US-C-002:** As a consumer, I want to verify the farm origin, slaughter date, and certifications of the meat I'm buying.

**US-C-003:** As a consumer, I want to track my order status using an order QR code.

### 4.5 Government Inspector Stories
**US-G-001:** As a government inspector, I want to conduct compliance audits for processing units and record findings.

**US-G-002:** As a government inspector, I want to issue and track certifications (HACCP, Halal, etc.).

**US-G-003:** As a government auditor, I want to review registration applications for new processing units.

**US-G-004:** As a government official, I want to track compliance trends across all registered entities.

### 4.6 Administrator Stories
**US-A-001:** As a system admin, I want to manage user accounts and their access permissions.

**US-A-002:** As a system admin, I want to monitor system health and receive alerts for issues.

**US-A-003:** As a system admin, I want to configure system-wide settings like required certifications and validation rules.

**US-A-004:** As a system admin, I want to generate exports of all system data for backup and reporting.

---

## 5. SUCCESS CRITERIA

### 5.1 Functional Success
- ✅ All critical functional requirements implemented
- ✅ 95% test coverage for core modules
- ✅ Successful end-to-end traceability demonstration
- ✅ QR code scanning works for consumers

### 5.2 Performance Success
- ✅ < 200ms API response time (95th percentile)
- ✅ Support 1000 concurrent users without degradation
- ✅ Zero data loss incidents
- ✅ 99.5% uptime achieved

### 5.3 Adoption Success
- 📊 80% of registered processing units actively using system (6 months post-launch)
- 📊 500+ farmers registered and tracking animals (6 months)
- 📊 50+ shops placing orders through the system (6 months)
- 📊 Consumer QR scans: 1000+ scans per month (6 months)

### 5.4 Compliance Success
- ✅ Regulatory approval from Ministry of Agriculture
- ✅ Successful audit by Food Safety Authority
- ✅ HACCP compliance verification
- ✅ Zero compliance violations in first year

---

## 6. APPENDICES

### Appendix A: Database Schema
See separate ERD document: `docs/database_erd.md`

### Appendix B: API Endpoints
Full API documentation available after development phase

### Appendix C: Glossary
- **Traceability:** Ability to track product history, application, or location
- **HACCP:** Hazard Analysis and Critical Control Points
- **ISO 22000:** International food safety management standard
- **Halal:** Food prepared according to Islamic law
- **QR Code:** Quick Response code for product identification

---

**Document Status:** APPROVED  
**Document Owner:** Project Manager  
**Last Updated:** December 2024

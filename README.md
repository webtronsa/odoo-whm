# WHM/cPanel Hosting Management for Odoo 19

A comprehensive WHM/cPanel hosting automation and billing platform for Odoo 19 that replicates WHMCS functionality with seamless integration into your existing Odoo ecosystem.

## � File Structure

```
Odoo19WHM-Addon/
├── __init__.py                    # Main module initialization
├── __manifest__.py                # Module metadata and dependencies
├── hooks.py                       # Installation and uninstallation hooks
├── requirements.txt               # Python dependencies
├── README.md                      # This documentation file
├── CONTRIBUTORS.md                # Contributors and credits
├── LICENSE                        # LGPL-3 License
│
├── models/                        # Data models
│   ├── __init__.py               # Model imports
│   ├── whm_hosting_account.py    # Hosting account model
│   ├── whm_server.py             # WHM server configuration
│   ├── whm_package.py            # Hosting packages
│   ├── whm_domain.py             # Domain management
│   ├── whm_tld.py                # TLD pricing and config
│   ├── product_product.py         # Product variant extensions
│   ├── product_template.py        # Product template extensions
│   ├── sale_order.py             # Sales order integration
│   └── res_partner.py            # Customer extensions
│
├── views/                         # UI views and templates
│   ├── __init__.py               # View imports
│   ├── whm_hosting_views.xml     # Hosting account views
│   ├── whm_server_views.xml      # WHM server views
│   ├── whm_package_views.xml     # Package management views
│   ├── whm_domain_views.xml      # Domain management views
│   ├── whm_tld_views.xml         # TLD management views
│   ├── product_views.xml          # Product configuration views
│   ├── whm_backend_menu.xml      # Backend menu structure
│   ├── portal_hosting_setup.xml  # Portal setup wizard
│   ├── portal_templates.xml      # Customer portal templates
│   └── email_templates.xml       # Email notification templates
│
├── controllers/                   # Web controllers
│   ├── __init__.py               # Controller imports
│   ├── main.py                   # Public API endpoints
│   └── portal.py                 # Customer portal controllers
│
├── security/                      # Security configuration
│   ├── ir.model.access.csv       # Model access rights
│   └── whm_security.xml          # Groups and record rules
│
├── data/                          # Default data and configuration
│   ├── crons.xml                 # Scheduled cron jobs
│   └── whm_data.xml              # Default TLDs, packages, products
│
└── static/                        # Static assets
    └── description/               # Marketplace description
        └── index.html            # Apps store description page
```

## �🚀 Features

### Core Hosting Management
- **Automated Provisioning**: Instant cPanel account creation via WHM API
- **Account Management**: Full lifecycle management (create, suspend, unsuspend, terminate)
- **Resource Monitoring**: Real-time disk and bandwidth usage tracking
- **Package Management**: Create and manage hosting packages synced with WHM
- **Multi-Server Support**: Manage multiple WHM servers from one interface

### Domain Management
- **Domain Registration**: Integrated domain registration and transfer
- **TLD Management**: Configure pricing and requirements for different TLDs
- **DNS Management**: Manage DNS records and nameservers
- **WHOIS Privacy**: Optional WHOIS privacy protection
- **Auto-Renewal**: Automated domain renewal reminders and processing

### Billing & Invoicing
- **Automated Billing**: Recurring invoices for hosting services
- **Multiple Billing Cycles**: Monthly, quarterly, semi-annual, annual, biennial
- **Setup Fees**: Optional one-time setup charges
- **Payment Integration**: Seamless integration with Odoo payment providers
- **Credit Management**: Customer credit limits and balance tracking

### Customer Portal
- **Self-Service Portal**: Customers can manage their accounts 24/7
- **cPanel Auto-Login**: One-click access to cPanel control panel
- **Domain Setup Wizard**: Easy domain configuration during signup
- **Usage Statistics**: View disk, bandwidth, and resource usage
- **Support Integration**: Create and track support tickets

### Advanced Features
- **Reseller Support**: Complete reseller hosting functionality
- **SSL Management**: Automated SSL certificate provisioning and renewal
- **Email Templates**: Customizable email notifications
- **Audit Logging**: Complete audit trail for all operations
- **API Integration**: RESTful API for third-party integrations
- **Multi-Currency**: Support for multiple currencies
- **Multi-Language**: Full translation support

## 📋 Requirements

- Odoo 19.0 or later
- WHM/cPanel server with API access
- Python 3.8+
- Required Python packages: `requests`, `urllib3`

## 🔧 Installation

1. **Download the Module**
   ```bash
   cd /path/to/odoo/addons
   git clone <repository-url> whm_hosting
   ```

2. **Install Dependencies**
   ```bash
   pip install requests urllib3
   ```

3. **Update Module List**
   - Go to Apps → Update Apps List
   - Search for "WHM Hosting" and install

4. **Configure WHM Server**
   - Navigate to WHM → Configuration → Servers
   - Add your WHM server details including API URL and token
   - Test the connection

## ⚙️ Configuration

### WHM Server Setup

1. **Generate API Token in WHM**
   - Log into WHM as root
   - Go to "Manage API Tokens"
   - Create a new token with required permissions

2. **Configure Server in Odoo**
   - WHM → Configuration → Servers → Create
   - Enter server details:
     - Name: Human-readable server name
     - Hostname: WHM server hostname
     - IP Address: Server IP
     - API URL: `https://your-server.com:2087`
     - API Token: Token generated in WHM
     - Default Domain: Default domain for subdomains

3. **Test Connection**
   - Click "Test Connection" to verify API access

### Package Configuration

1. **Create Hosting Packages**
   - WHM → Configuration → Packages → Create
   - Set resource limits and pricing
   - Sync with WHM or create locally

2. **Configure Products**
   - Go to Sales → Products
   - Create products with WHM integration enabled
   - Link products to hosting packages

### Domain Configuration

1. **Configure TLDs**
   - WHM → Configuration → TLD Management
   - Set pricing and requirements for each TLD
   - Configure registrar integration

## 🎯 Usage

### Creating Hosting Accounts

1. **Manual Creation**
   - WHM → Hosting Accounts → Create
   - Select customer and package
   - Configure domain and settings
   - Click "Provision"

2. **Automatic Provisioning**
   - Customer purchases hosting product
   - Account automatically created via order confirmation
   - Welcome email sent with login details

### Customer Portal Access

1. **Customer Login**
   - Customer logs into Odoo portal
   - Navigate to "My Hosting Accounts"
   - View account details and usage

2. **cPanel Access**
   - Click "Login to cPanel" button
   - Auto-login URL generated
   - Direct access to cPanel control panel

### Domain Management

1. **Domain Registration**
   - Customer selects domain during signup
   - Availability checked in real-time
   - Registration processed automatically

2. **Domain Transfer**
   - Customer initiates transfer
   - EPP code collected
   - Transfer processed via registrar API

## 🔌 API Integration

### WHM API Endpoints

The module integrates with the following WHM APIs:
- `createacct`: Create cPanel accounts
- `removeacct`: Terminate accounts
- `suspendacct`/`unsuspendacct`: Suspend/unsuspend accounts
- `listaccts`: List accounts
- `accountsummary`: Get account usage
- `create_user_session`: Generate auto-login URLs

### REST API

The module provides REST API endpoints for:
- Domain availability checking
- Package information
- Server status
- Account management

## 📊 Reporting

### Available Reports
- **Usage Reports**: Disk and bandwidth usage by account
- **Revenue Reports**: Hosting revenue by period and package
- **Server Reports**: Server utilization and performance
- **Customer Reports**: Customer activity and billing

### Automated Reports
- Daily usage summaries
- Weekly revenue reports
- Monthly performance metrics
- Custom report scheduling

## 🛠️ Customization

### Adding New Features

The module is designed to be extensible:

1. **Custom Fields**: Add custom fields to any model
2. **Custom Workflows**: Create automated workflows
3. **Custom Reports**: Build custom reports and dashboards
4. **Third-Party Integration**: Connect to external services

### Theme Customization

- Override portal templates for custom branding
- Customize email templates
- Modify CSS styles for unique appearance

## 🔒 Security

### Access Control
- Role-based access control
- Customer data isolation
- API token security
- Audit logging for all operations

### Data Protection
- Secure password handling
- Encrypted API communications
- GDPR compliance features
- Data backup and recovery

## 🚀 Performance

### Optimization Features
- Efficient API usage
- Cached data where appropriate
- Background job processing
- Resource usage monitoring

### Scaling
- Multi-server support
- Load balancing ready
- Database optimization
- Caching strategies

## 📞 Support

### Documentation
- Comprehensive user guide
- API documentation
- Developer documentation
- Video tutorials

### Getting Help
- Community forum
- Professional support available
- Custom development services
- Training and consulting

## 🔄 Updates

### Version History
- **v19.0.1.0**: Initial release
- **v19.0.1.1**: Bug fixes and improvements
- **v19.0.2.0**: Enhanced reporting features

### Update Process
- Automatic update notifications
- Easy upgrade process
- Data migration included
- Rollback capability

## 📄 License

This module is licensed under LGPL-3.

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines for details.

### Development Setup
```bash
git clone <repository-url>
cd whm_hosting
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Testing
```bash
python -m pytest tests/
```

## 🌟 Roadmap

### Upcoming Features
- Advanced monitoring and alerts
- Mobile app for customers
- Advanced automation rules
- Cloud server integration
- Enhanced reporting dashboard

### Planned Integrations
- More domain registrars
- Additional payment gateways
- Cloud storage providers
- CDN integration
- Backup services

---

**WHM Hosting Management** - Transform your hosting business with the power of Odoo! 🚀

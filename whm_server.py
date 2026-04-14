# -*- coding: utf-8 -*-
import logging
import requests
import urllib3

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = logging.getLogger(__name__)


class WHMServer(models.Model):
    _name = "whm.server"
    _description = "WHM Server"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Server Name", required=True, tracking=True)
    hostname = fields.Char(string="Hostname", required=True, tracking=True)
    ip_address = fields.Char(string="IP Address", required=True, tracking=True)
    
    # API Configuration
    api_url = fields.Char(string="WHM API URL", required=True, tracking=True)
    api_token = fields.Char(string="API Token", required=True, tracking=True)
    verify_ssl = fields.Boolean(string="Verify SSL", default=True, tracking=True)
    
    # Server Details
    whm_version = fields.Char(string="WHM Version", readonly=True)
    php_version = fields.Char(string="PHP Version", readonly=True)
    mysql_version = fields.Char(string="MySQL Version", readonly=True)
    cpanel_version = fields.Char(string="cPanel Version", readonly=True)
    
    # Server Configuration
    default_domain = fields.Char(string="Default Domain", 
                                help="Default domain for subdomain creation (e.g., yourhosting.com)")
    from_email = fields.Char(string="From Email", 
                           help="Default from email for automated emails")
    nameservers = fields.Text(string="Nameservers", 
                            help="Nameservers to provide to customers, one per line")
    
    # Resource Limits
    max_accounts = fields.Integer(string="Max Accounts", default=0,
                                  help="Maximum number of cPanel accounts (0 = unlimited)")
    current_accounts = fields.Integer(string="Current Accounts", readonly=True)
    
    # Status and Monitoring
    is_active = fields.Boolean(string="Active", default=True, tracking=True)
    last_sync = fields.Datetime(string="Last Sync", readonly=True)
    status = fields.Selection([
        ("online", "Online"),
        ("offline", "Offline"),
        ("error", "Error"),
    ], default="offline", readonly=True)
    
    # Statistics
    total_disk_space = fields.Float(string="Total Disk Space (GB)", readonly=True)
    used_disk_space = fields.Float(string="Used Disk Space (GB)", readonly=True)
    total_memory = fields.Float(string="Total Memory (GB)", readonly=True)
    used_memory = fields.Float(string="Used Memory (GB)", readonly=True)
    
    # Relations
    hosting_account_ids = fields.One2many("whm.hosting.account", "server_id", string="Hosting Accounts")
    
    @api.depends('hosting_account_ids')
    def _compute_current_accounts(self):
        for server in self:
            server.current_accounts = len(server.hosting_account_ids.filtered(
                lambda a: a.state not in ['terminated', 'cancelled']
            ))

    # --------------------------------------------------
    # API CONNECTION METHODS
    # --------------------------------------------------

    def _whm_headers(self):
        return {
            "Authorization": f"whm root:{self.api_token}",
        }

    def _whm_call(self, endpoint, params=None):
        """Make WHM API call"""
        if not self.api_url or not self.api_token:
            raise UserError(_("WHM server is not properly configured."))
        
        url = f"{self.api_url.rstrip('/')}/json-api/{endpoint}"
        
        try:
            r = requests.get(
                url,
                headers=self._whm_headers(),
                params=params or {},
                verify=self.verify_ssl,
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()
            else:
                _logger.error("WHM API error [%s]: %s", r.status_code, r.text)
                raise UserError(_("WHM API error [%s]: %s") % (r.status_code, r.text))
        except requests.exceptions.ConnectionError as e:
            raise UserError(_("Cannot connect to WHM server: %s") % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_("WHM API timed out"))

    # --------------------------------------------------
    # SERVER ACTIONS
    # --------------------------------------------------

    def action_test_connection(self):
        """Test WHM API connection"""
        self.ensure_one()
        try:
            result = self._whm_call("version")
            version = result.get("version", "unknown")
            build = result.get("build", "")
            
            self.write({
                'whm_version': f"{version} {build}",
                'status': 'online',
                'last_sync': fields.Datetime.now(),
            })
            
            self.message_post(body=_(
                "<b>✅ Connection Successful</b><br/>"
                "WHM Version: %s %s<br/>"
                "Server: %s"
            ) % (version, build, self.hostname))
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': f'Connected to WHM {version}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({'status': 'error'})
            self.message_post(body=_("<b>❌ Connection Failed</b><br/>%s") % str(e))
            raise UserError(_("Connection failed: %s") % str(e))

    def action_sync_server_info(self):
        """Sync detailed server information"""
        self.ensure_one()
        try:
            # Get system info
            result = self._whm_call("systemloadavg")
            load_avg = result.get("data", {}).get("one", "0")
            
            # Get PHP version
            php_result = self._whm_call("phpconfig", {"showphpversion": 1})
            php_version = php_result.get("data", {}).get("version", "Unknown")
            
            # Get account count
            accounts_result = self._whm_call("listaccts")
            account_count = len(accounts_result.get("acct", []))
            
            self.write({
                'current_accounts': account_count,
                'php_version': php_version,
                'status': 'online',
                'last_sync': fields.Datetime.now(),
            })
            
            self.message_post(body=_(
                "<b>Server Info Synced</b><br/>"
                "Accounts: %d<br/>"
                "PHP Version: %s<br/>"
                "Load Average: %s"
            ) % (account_count, php_version, load_avg))
            
        except Exception as e:
            self.write({'status': 'error'})
            raise UserError(_("Failed to sync server info: %s") % str(e))

    def action_sync_resource_usage(self):
        """Sync server resource usage"""
        self.ensure_one()
        try:
            # Get disk usage
            disk_result = self._whm_call("diskusage")
            disk_data = disk_result.get("data", {})
            
            # Get memory info (if available)
            try:
                mem_result = self._whm_call("loadavg")
                # Note: WHM doesn't provide direct memory usage via API
                # This would require server-side scripts or SSH access
            except:
                pass
            
            self.write({
                'last_sync': fields.Datetime.now(),
                'status': 'online',
            })
            
            self.message_post(body=_("<b>Resource Usage Synced</b>"))
            
        except Exception as e:
            self.write({'status': 'error'})
            raise UserError(_("Failed to sync resource usage: %s") % str(e))

    # --------------------------------------------------
    # PACKAGE MANAGEMENT
    # --------------------------------------------------

    def action_sync_packages(self):
        """Sync WHM packages with Odoo"""
        self.ensure_one()
        try:
            result = self._whm_call("listpkgs")
            packages = result.get("package", [])
            
            package_model = self.env['whm.package']
            synced_count = 0
            
            for pkg_data in packages:
                package = package_model.search([
                    ('name', '=', pkg_data.get('name')),
                    ('server_id', '=', self.id)
                ], limit=1)
                
                if not package:
                    package = package_model.create({
                        'name': pkg_data.get('name'),
                        'server_id': self.id,
                    })
                    synced_count += 1
                else:
                    # Update existing package
                    package.write({
                        'disk_quota': float(pkg_data.get('QUOTA', 0)),
                        'bandwidth_limit': float(pkg_data.get('BWLIMIT', 0)),
                        'max_addon_domains': int(pkg_data.get('MAXADDON', 0)),
                        'max_parked_domains': int(pkg_data.get('MAXPARK', 0)),
                        'max_subdomains': int(pkg_data.get('MAXSUB', 0)),
                        'max_email_accounts': int(pkg_data.get('MAXPOP', 0)),
                        'max_databases': int(pkg_data.get('MAXSQL', 0)),
                        'max_ftp_accounts': int(pkg_data.get('MAXFTP', 0)),
                    })
                    synced_count += 1
            
            self.message_post(body=_(
                "<b>Packages Synced</b><br/>"
                "Synced/Updated: %d packages"
            ) % synced_count)
            
        except Exception as e:
            raise UserError(_("Failed to sync packages: %s") % str(e))

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    @api.constrains('api_url')
    def _check_api_url(self):
        for server in self:
            if server.api_url and not server.api_url.startswith(('http://', 'https://')):
                raise ValidationError(_("API URL must start with http:// or https://"))

    @api.constrains('ip_address')
    def _check_ip_address(self):
        for server in self:
            if server.ip_address:
                import ipaddress
                try:
                    ipaddress.ip_address(server.ip_address)
                except ValueError:
                    raise ValidationError(_("Invalid IP address format"))

    # --------------------------------------------------
    # CRON JOBS
    # --------------------------------------------------

    @api.model
    def cron_check_server_status(self):
        """Check status of all active servers"""
        servers = self.search([('is_active', '=', True)])
        for server in servers:
            try:
                server.action_test_connection()
            except Exception as e:
                _logger.error("Server status check failed for %s: %s", server.name, str(e))
                server.write({'status': 'offline'})

    @api.model
    def cron_sync_all_servers(self):
        """Sync information for all active servers"""
        servers = self.search([('is_active', '=', True)])
        for server in servers:
            try:
                server.action_sync_server_info()
            except Exception as e:
                _logger.error("Server sync failed for %s: %s", server.name, str(e))

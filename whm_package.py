# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WHMPackage(models.Model):
    _name = "whm.package"
    _description = "WHM Hosting Package"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Package Name", required=True, tracking=True)
    server_id = fields.Many2one("whm.server", string="Server", required=True, tracking=True)
    description = fields.Text(string="Description", tracking=True)
    
    # Resource Limits
    disk_quota = fields.Float(string="Disk Space (MB)", default=0, tracking=True,
                             help="0 = unlimited")
    bandwidth_limit = fields.Float(string="Bandwidth (MB)", default=0, tracking=True,
                                  help="0 = unlimited")
    
    # Domain Limits
    max_addon_domains = fields.Integer(string="Max Addon Domains", default=0, tracking=True)
    max_parked_domains = fields.Integer(string="Max Parked Domains", default=0, tracking=True)
    max_subdomains = fields.Integer(string="Max Subdomains", default=0, tracking=True)
    
    # Service Limits
    max_email_accounts = fields.Integer(string="Max Email Accounts", default=0, tracking=True)
    max_databases = fields.Integer(string="Max Databases", default=0, tracking=True)
    max_ftp_accounts = fields.Integer(string="Max FTP Accounts", default=0, tracking=True)
    
    # Advanced Features
    cgi_access = fields.Boolean(string="CGI Access", default=True, tracking=True)
    php_access = fields.Boolean(string="PHP Access", default=True, tracking=True)
    ssl_access = fields.Boolean(string="SSL Access", default=True, tracking=True)
    shell_access = fields.Boolean(string="Shell Access", default=False, tracking=True)
    
    # Reseller Features
    is_reseller = fields.Boolean(string="Reseller Package", default=False, tracking=True)
    max_accounts = fields.Integer(string="Max Accounts", default=0,
                                  help="Maximum accounts for reseller (0 = unlimited)")
    
    # Billing Information
    setup_fee = fields.Float(string="Setup Fee", default=0.0, tracking=True)
    monthly_price = fields.Float(string="Monthly Price", default=0.0, tracking=True)
    quarterly_price = fields.Float(string="Quarterly Price", default=0.0, tracking=True)
    semi_annual_price = fields.Float(string="Semi-Annual Price", default=0.0, tracking=True)
    annual_price = fields.Float(string="Annual Price", default=0.0, tracking=True)
    biennial_price = fields.Float(string="Biennial Price", default=0.0, tracking=True)
    
    # Status
    is_active = fields.Boolean(string="Active", default=True, tracking=True)
    is_featured = fields.Boolean(string="Featured", default=False, tracking=True)
    
    # Relations
    hosting_account_ids = fields.One2many("whm.hosting.account", 
                                        compute="_compute_hosting_accounts")
    
    @api.depends('name', 'server_id')
    def _compute_hosting_accounts(self):
        for package in self:
            package.hosting_account_ids = self.env['whm.hosting.account'].search([
                ('whm_package', '=', package.name),
                ('server_id', '=', package.server_id.id)
            ])

    # --------------------------------------------------
    # PACKAGE ACTIONS
    # --------------------------------------------------

    def action_create_in_whm(self):
        """Create this package in WHM"""
        self.ensure_one()
        try:
            # Prepare package data
            package_data = {
                "name": self.name,
                "quota": str(int(self.disk_quota)) if self.disk_quota > 0 else "unlimited",
                "bwlimit": str(int(self.bandwidth_limit)) if self.bandwidth_limit > 0 else "unlimited",
                "maxaddon": str(self.max_addon_domains),
                "maxpark": str(self.max_parked_domains),
                "maxsub": str(self.max_subdomains),
                "maxpop": str(self.max_email_accounts),
                "maxsql": str(self.max_databases),
                "maxftp": str(self.max_ftp_accounts),
                "cgi": 1 if self.cgi_access else 0,
                "php": 1 if self.php_access else 0,
                "ssl": 1 if self.ssl_access else 0,
                "shell": 1 if self.shell_access else 0,
                "reseller": 1 if self.is_reseller else 0,
            }
            
            if self.is_reseller:
                package_data["maxacc"] = str(self.max_accounts)
            
            result = self.server_id._whm_call("addpkg", package_data)
            
            if result.get("result", [{}])[0].get("status", 0):
                self.message_post(body=_(
                    "<b>✅ Package Created in WHM</b><br/>"
                    "Package: %s<br/>"
                    "Server: %s"
                ) % (self.name, self.server_id.name))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to create package in WHM: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to create package in WHM: %s") % str(e))

    def action_update_in_whm(self):
        """Update this package in WHM"""
        self.ensure_one()
        try:
            package_data = {
                "name": self.name,
                "quota": str(int(self.disk_quota)) if self.disk_quota > 0 else "unlimited",
                "bwlimit": str(int(self.bandwidth_limit)) if self.bandwidth_limit > 0 else "unlimited",
                "maxaddon": str(self.max_addon_domains),
                "maxpark": str(self.max_parked_domains),
                "maxsub": str(self.max_subdomains),
                "maxpop": str(self.max_email_accounts),
                "maxsql": str(self.max_databases),
                "maxftp": str(self.max_ftp_accounts),
                "cgi": 1 if self.cgi_access else 0,
                "php": 1 if self.php_access else 0,
                "ssl": 1 if self.ssl_access else 0,
                "shell": 1 if self.shell_access else 0,
                "reseller": 1 if self.is_reseller else 0,
            }
            
            if self.is_reseller:
                package_data["maxacc"] = str(self.max_accounts)
            
            result = self.server_id._whm_call("editpkg", package_data)
            
            if result.get("result", [{}])[0].get("status", 0):
                self.message_post(body=_(
                    "<b>✅ Package Updated in WHM</b><br/>"
                    "Package: %s<br/>"
                    "Server: %s"
                ) % (self.name, self.server_id.name))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to update package in WHM: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to update package in WHM: %s") % str(e))

    def action_delete_from_whm(self):
        """Delete this package from WHM"""
        self.ensure_one()
        try:
            result = self.server_id._whm_call("killpkg", {"name": self.name})
            
            if result.get("result", [{}])[0].get("status", 0):
                self.message_post(body=_(
                    "<b>✅ Package Deleted from WHM</b><br/>"
                    "Package: %s<br/>"
                    "Server: %s"
                ) % (self.name, self.server_id.name))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to delete package from WHM: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to delete package from WHM: %s") % str(e))

    def action_sync_from_whm(self):
        """Sync package details from WHM"""
        self.ensure_one()
        try:
            result = self.server_id._whm_call("listpkgs", {"name": self.name})
            packages = result.get("package", [])
            
            package_data = None
            for pkg in packages:
                if pkg.get("name") == self.name:
                    package_data = pkg
                    break
            
            if not package_data:
                raise UserError(_("Package '%s' not found in WHM") % self.name)
            
            # Update package with WHM data
            self.write({
                'disk_quota': float(package_data.get("QUOTA", 0)),
                'bandwidth_limit': float(package_data.get("BWLIMIT", 0)),
                'max_addon_domains': int(package_data.get("MAXADDON", 0)),
                'max_parked_domains': int(package_data.get("MAXPARK", 0)),
                'max_subdomains': int(package_data.get("MAXSUB", 0)),
                'max_email_accounts': int(package_data.get("MAXPOP", 0)),
                'max_databases': int(package_data.get("MAXSQL", 0)),
                'max_ftp_accounts': int(package_data.get("MAXFTP", 0)),
                'cgi_access': bool(int(package_data.get("CGI", 0))),
                'php_access': bool(int(package_data.get("PHP", 0))),
                'ssl_access': bool(int(package_data.get("SSL", 0))),
                'shell_access': bool(int(package_data.get("shell", 0))),
                'is_reseller': bool(int(package_data.get("reseller", 0))),
            })
            
            self.message_post(body=_(
                "<b>✅ Package Synced from WHM</b><br/>"
                "Package: %s<br/>"
                "Server: %s"
            ) % (self.name, self.server_id.name))
            
        except Exception as e:
            raise UserError(_("Failed to sync package from WHM: %s") % str(e))

    # --------------------------------------------------
    # UTILITY METHODS
    # --------------------------------------------------

    def get_price_for_cycle(self, billing_cycle):
        """Get price for specific billing cycle"""
        self.ensure_one()
        price_map = {
            'monthly': self.monthly_price,
            'quarterly': self.quarterly_price,
            'semi_annually': self.semi_annual_price,
            'annually': self.annual_price,
            'biennially': self.biennial_price,
        }
        return price_map.get(billing_cycle, self.monthly_price)

    def get_resource_summary(self):
        """Get formatted summary of resources"""
        self.ensure_one()
        resources = []
        
        if self.disk_quota > 0:
            resources.append(f"{self.disk_quota}MB Disk")
        else:
            resources.append("Unlimited Disk")
            
        if self.bandwidth_limit > 0:
            resources.append(f"{self.bandwidth_limit}MB Bandwidth")
        else:
            resources.append("Unlimited Bandwidth")
            
        if self.max_addon_domains > 0:
            resources.append(f"{self.max_addon_domains} Addon Domains")
            
        if self.max_email_accounts > 0:
            resources.append(f"{self.max_email_accounts} Email Accounts")
            
        if self.max_databases > 0:
            resources.append(f"{self.max_databases} Databases")
        
        return " • ".join(resources) if resources else "Basic Hosting"

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    @api.constrains('disk_quota', 'bandwidth_limit')
    def _check_positive_values(self):
        for package in self:
            if package.disk_quota < 0:
                raise ValidationError(_("Disk quota cannot be negative"))
            if package.bandwidth_limit < 0:
                raise ValidationError(_("Bandwidth limit cannot be negative"))

    @api.constrains('max_addon_domains', 'max_parked_domains', 'max_subdomains',
                   'max_email_accounts', 'max_databases', 'max_ftp_accounts')
    def _check_max_values(self):
        for package in self:
            if any(getattr(package, field) < 0 for field in [
                'max_addon_domains', 'max_parked_domains', 'max_subdomains',
                'max_email_accounts', 'max_databases', 'max_ftp_accounts'
            ]):
                raise ValidationError(_("Maximum limits cannot be negative"))

    @api.constrains('setup_fee', 'monthly_price', 'quarterly_price', 
                   'semi_annual_price', 'annual_price', 'biennial_price')
    def _check_prices(self):
        for package in self:
            if any(getattr(package, field) < 0 for field in [
                'setup_fee', 'monthly_price', 'quarterly_price',
                'semi_annual_price', 'annual_price', 'biennial_price'
            ]):
                raise ValidationError(_("Prices cannot be negative"))

    # --------------------------------------------------
    # NAME GET METHOD
    # --------------------------------------------------

    def name_get(self):
        result = []
        for package in self:
            display_name = package.name
            if package.server_id:
                display_name = f"{package.name} ({package.server_id.name})"
            if not package.is_active:
                display_name = f"{display_name} [Inactive]"
            result.append((package.id, display_name))
        return result

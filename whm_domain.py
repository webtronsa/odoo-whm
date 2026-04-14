# -*- coding: utf-8 -*-
import logging
import requests
import urllib3

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = logging.getLogger(__name__)


class WHMDomain(models.Model):
    _name = "whm.domain"
    _description = "WHM Domain"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Domain Name", required=True, tracking=True)
    hosting_account_id = fields.Many2one("whm.hosting.account", 
                                        string="Hosting Account", 
                                        required=True, tracking=True)
    is_primary = fields.Boolean(string="Primary Domain", default=False, tracking=True)
    
    # Domain Registration
    is_registered = fields.Boolean(string="Registered with Us", default=False, tracking=True)
    registrar_id = fields.Many2one("whm.registrar", string="Registrar", tracking=True)
    registration_date = fields.Date(string="Registration Date", tracking=True)
    expiry_date = fields.Date(string="Expiry Date", tracking=True)
    auto_renew = fields.Boolean(string="Auto Renew", default=True, tracking=True)
    registration_status = fields.Selection([
        ("pending", "Pending Registration"),
        ("registered", "Registered"),
        ("transferring", "Transferring"),
        ("transferred", "Transferred"),
        ("expired", "Expired"),
        ("failed", "Registration Failed"),
    ], default="pending", tracking=True)
    
    # DNS Management
    nameservers = fields.Text(string="Nameservers", 
                            help="Nameservers for this domain, one per line")
    dns_records = fields.One2many("whm.dns.record", "domain_id", string="DNS Records")
    
    # Domain Configuration
    document_root = fields.Char(string="Document Root", readonly=True)
    php_version = fields.Selection([
        ("inherit", "Inherit from Account"),
        ("5.6", "PHP 5.6"),
        ("7.0", "PHP 7.0"),
        ("7.1", "PHP 7.1"),
        ("7.2", "PHP 7.2"),
        ("7.3", "PHP 7.3"),
        ("7.4", "PHP 7.4"),
        ("8.0", "PHP 8.0"),
        ("8.1", "PHP 8.1"),
        ("8.2", "PHP 8.2"),
        ("8.3", "PHP 8.3"),
    ], default="inherit", tracking=True)
    
    ssl_enabled = fields.Boolean(string="SSL Enabled", default=False, tracking=True)
    ssl_certificate_id = fields.Many2one("whm.ssl.certificate", 
                                        string="SSL Certificate")
    
    # Status
    state = fields.Selection([
        ("pending", "Pending Setup"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("redirected", "Redirected"),
        ("error", "Error"),
    ], default="pending", tracking=True)
    
    # Statistics
    disk_usage = fields.Float(string="Disk Usage (MB)", readonly=True)
    bandwidth_usage = fields.Float(string="Bandwidth Usage (MB)", readonly=True)
    last_sync = fields.Datetime(string="Last Sync", readonly=True)
    
    # Notes
    notes = fields.Text(string="Notes")
    provisioning_notes = fields.Text(string="Provisioning Notes", readonly=True)

    @api.depends('hosting_account_id')
    def _compute_server_id(self):
        for domain in self:
            domain.server_id = domain.hosting_account_id.server_id

    server_id = fields.Many2one("whm.server", string="Server", compute="_compute_server_id", store=True)

    # --------------------------------------------------
    # DOMAIN ACTIONS
    # --------------------------------------------------

    def action_add_to_cpanel(self):
        """Add domain to cPanel account"""
        self.ensure_one()
        try:
            account = self.hosting_account_id
            result = account._whm_call("adddomain", {
                "domain": self.name,
                "user": account.cpanel_username,
            })
            
            if result.get("result", [{}])[0].get("status", 0):
                self.write({
                    'state': 'active',
                    'document_root': f"/home/{account.cpanel_username}/public_html/{self.name}",
                    'provisioning_notes': f"Domain added to cPanel on {fields.Datetime.now()}",
                })
                self.message_post(body=_(
                    "<b>✅ Domain Added to cPanel</b><br/>"
                    "Domain: %s<br/>"
                    "Account: %s"
                ) % (self.name, account.cpanel_username))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to add domain to cPanel: %s") % error_msg)
                
        except Exception as e:
            self.write({'state': 'error'})
            raise UserError(_("Failed to add domain to cPanel: %s") % str(e))

    def action_remove_from_cpanel(self):
        """Remove domain from cPanel account"""
        self.ensure_one()
        try:
            account = self.hosting_account_id
            result = account._whm_call("killdomain", {
                "domain": self.name,
                "user": account.cpanel_username,
            })
            
            if result.get("result", [{}])[0].get("status", 0):
                self.write({'state': 'suspended'})
                self.message_post(body=_(
                    "<b>✅ Domain Removed from cPanel</b><br/>"
                    "Domain: %s<br/>"
                    "Account: %s"
                ) % (self.name, account.cpanel_username))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to remove domain from cPanel: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to remove domain from cPanel: %s") % str(e))

    def action_set_as_primary(self):
        """Set this domain as the primary domain for the hosting account"""
        self.ensure_one()
        account = self.hosting_account_id
        
        # Unset other primary domains
        other_domains = account.domain_ids.filtered(lambda d: d.id != self.id)
        other_domains.write({'is_primary': False})
        
        # Set this as primary
        self.write({'is_primary': True})
        account.write({'cpanel_domain': self.name})
        
        self.message_post(body=_(
            "<b>✅ Set as Primary Domain</b><br/>"
            "Domain: %s<br/>"
            "Account: %s"
        ) % (self.name, account.cpanel_username))

    def action_sync_from_cpanel(self):
        """Sync domain information from cPanel"""
        self.ensure_one()
        try:
            account = self.hosting_account_id
            result = account._whm_call("domainuserdata", {
                "domain": self.name,
                "user": account.cpanel_username,
            })
            
            data = result.get("data", {})
            if data:
                self.write({
                    'document_root': data.get("documentroot", ""),
                    'disk_usage': float(data.get("diskused", 0) or 0),
                    'bandwidth_usage': float(data.get("bandwidthused", 0) or 0),
                    'last_sync': fields.Datetime.now(),
                    'state': 'active',
                })
                
                self.message_post(body=_(
                    "<b>✅ Domain Synced from cPanel</b><br/>"
                    "Domain: %s<br/>"
                    "Disk Usage: %s MB<br/>"
                    "Bandwidth Usage: %s MB"
                ) % (self.name, self.disk_usage, self.bandwidth_usage))
            else:
                raise UserError(_("Domain data not found in cPanel"))
                
        except Exception as e:
            raise UserError(_("Failed to sync domain from cPanel: %s") % str(e))

    def action_set_php_version(self):
        """Set PHP version for this domain"""
        self.ensure_one()
        if self.php_version == "inherit":
            raise UserError(_("Cannot set PHP version to 'inherit' directly"))
        
        try:
            account = self.hosting_account_id
            result = account._whm_call("php_set_vhost_versions", {
                "vhost": self.name,
                "version": self.php_version,
            })
            
            if result.get("result", [{}])[0].get("status", 0):
                self.message_post(body=_(
                    "<b>✅ PHP Version Updated</b><br/>"
                    "Domain: %s<br/>"
                    "PHP Version: %s"
                ) % (self.name, self.php_version))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to set PHP version: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to set PHP version: %s") % str(e))

    # --------------------------------------------------
    # DOMAIN REGISTRATION
    # --------------------------------------------------

    def action_register_domain(self):
        """Register domain through configured registrar"""
        self.ensure_one()
        if not self.registrar_id:
            raise UserError(_("No registrar configured for this domain"))
        
        # This would integrate with domain registrar APIs
        # For now, just mark as registered
        self.write({
            'is_registered': True,
            'registration_date': fields.Date.today(),
            'registration_status': 'registered',
        })
        
        self.message_post(body=_(
            "<b>✅ Domain Registered</b><br/>"
            "Domain: %s<br/>"
            "Registrar: %s"
        ) % (self.name, self.registrar_id.name))

    def action_transfer_domain(self):
        """Initiate domain transfer"""
        self.ensure_one()
        if not self.registrar_id:
            raise UserError(_("No registrar configured for this domain"))
        
        self.write({
            'registration_status': 'transferring',
        })
        
        self.message_post(body=_(
            "<b>🔄 Domain Transfer Initiated</b><br/>"
            "Domain: %s<br/>"
            "Registrar: %s"
        ) % (self.name, self.registrar_id.name))

    # --------------------------------------------------
    # SSL MANAGEMENT
    # --------------------------------------------------

    def action_install_ssl_certificate(self):
        """Install SSL certificate for this domain"""
        self.ensure_one()
        if not self.ssl_certificate_id:
            raise UserError(_("No SSL certificate selected"))
        
        try:
            account = self.hosting_account_id
            cert = self.ssl_certificate_id
            
            result = account._whm_call("installssl", {
                "domain": self.name,
                "user": account.cpanel_username,
                "cert": cert.certificate,
                "key": cert.private_key,
                "cabundle": cert.ca_bundle or "",
            })
            
            if result.get("result", [{}])[0].get("status", 0):
                self.write({'ssl_enabled': True})
                self.message_post(body=_(
                    "<b>✅ SSL Certificate Installed</b><br/>"
                    "Domain: %s<br/>"
                    "Certificate: %s"
                ) % (self.name, cert.name))
            else:
                error_msg = result.get("result", [{}])[0].get("statusmsg", "Unknown error")
                raise UserError(_("Failed to install SSL certificate: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to install SSL certificate: %s") % str(e))

    def action_request_free_ssl(self):
        """Request free SSL certificate (Let's Encrypt)"""
        self.ensure_one()
        try:
            account = self.hosting_account_id
            result = account._whm_call("request_uapi", {
                "module": "SSL",
                "function": "install_ssl",
                "domain": self.name,
            })
            
            if result.get("result", {}).get("status", 0):
                self.write({'ssl_enabled': True})
                self.message_post(body=_(
                    "<b>✅ Free SSL Certificate Installed</b><br/>"
                    "Domain: %s"
                ) % self.name)
            else:
                error_msg = result.get("result", {}).get("errors", ["Unknown error"])[0]
                raise UserError(_("Failed to request free SSL: %s") % error_msg)
                
        except Exception as e:
            raise UserError(_("Failed to request free SSL: %s") % str(e))

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    @api.constrains('name')
    def _check_domain_name(self):
        for domain in self:
            if domain.name:
                import re
                # Basic domain validation
                pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$'
                if not re.match(pattern, domain.name):
                    raise ValidationError(_("Invalid domain name format"))

    @api.constrains('expiry_date', 'registration_date')
    def _check_dates(self):
        for domain in self:
            if domain.registration_date and domain.expiry_date:
                if domain.expiry_date <= domain.registration_date:
                    raise ValidationError(_("Expiry date must be after registration date"))

    # --------------------------------------------------
    # NAME GET METHOD
    # --------------------------------------------------

    def name_get(self):
        result = []
        for domain in self:
            display_name = domain.name
            if domain.is_primary:
                display_name = f"{domain.name} [Primary]"
            if domain.state != 'active':
                display_name = f"{display_name} [{domain.state.upper()}]"
            result.append((domain.id, display_name))
        return result

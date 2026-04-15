# -*- coding: utf-8 -*-
import logging
import random
import re
import string
import requests
import urllib3

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = logging.getLogger(__name__)


class WHMHostingAccount(models.Model):
    _name = "whm.hosting.account"
    _description = "WHM/cPanel Hosting Account"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    sale_order_id = fields.Many2one("sale.order")
    sale_line_id = fields.Many2one("sale.order.line")
    product_id = fields.Many2one("product.product")
    server_id = fields.Many2one("whm.server", required=True, tracking=True)

    # WHM account details
    cpanel_username = fields.Char(string="cPanel Username", readonly=True, tracking=True)
    cpanel_domain = fields.Char(string="Primary Domain", readonly=True)
    cpanel_password = fields.Char(string="cPanel Password", readonly=True)
    whm_package = fields.Char(string="WHM Package", readonly=True)

    # Resource usage (pulled from WHM)
    disk_used = fields.Float(string="Disk Used (MB)", readonly=True)
    disk_limit = fields.Float(string="Disk Limit (MB)", readonly=True)
    bw_used = fields.Float(string="Bandwidth Used (MB)", readonly=True)
    bw_limit = fields.Float(string="Bandwidth Limit (MB)", readonly=True)

    # Additional WHMCS-like features
    dedicated_ip = fields.Char(string="Dedicated IP", readonly=True)
    reseller = fields.Boolean(string="Reseller Account", default=False)
    overselling_enabled = fields.Boolean(string="Overselling Enabled", default=False)
    max_addon_domains = fields.Integer(string="Max Addon Domains", default=0)
    max_parked_domains = fields.Integer(string="Max Parked Domains", default=0)
    max_subdomains = fields.Integer(string="Max Subdomains", default=0)
    max_email_accounts = fields.Integer(string="Max Email Accounts", default=0)
    max_databases = fields.Integer(string="Max Databases", default=0)
    max_ftp_accounts = fields.Integer(string="Max FTP Accounts", default=0)

    # Domain management
    domain_ids = fields.One2many("whm.domain", "hosting_account_id", string="Domains")
    primary_domain_id = fields.Many2one("whm.domain", string="Primary Domain")

    # Billing and renewal
    next_due_date = fields.Date(string="Next Due Date", tracking=True)
    billing_cycle = fields.Selection([
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annually", "Semi-Annually"),
        ("annually", "Annually"),
        ("biennially", "Biennially"),
        ("triennially", "Triennially"),
    ], default="monthly", tracking=True)
    auto_renew = fields.Boolean(string="Auto Renew", default=True, tracking=True)
    first_payment_amount = fields.Float(string="First Payment Amount")
    recurring_amount = fields.Float(string="Recurring Amount")

    state = fields.Selection([
        ("pending", "Pending"),
        ("provisioning", "Provisioning"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("terminated", "Terminated"),
        ("cancelled", "Cancelled"),
        ("error", "Error"),
    ], default="pending", tracking=True, required=True, index=True)

    last_error = fields.Text(readonly=True)
    provisioning_notes = fields.Text(readonly=True)

    # --------------------------------------------------
    # WHM API HELPERS
    # --------------------------------------------------

    def _whm_server_config(self):
        """Get WHM server configuration from the associated server record"""
        if not self.server_id:
            raise UserError(_("No WHM server configured for this account."))
        
        if not self.server_id.api_url or not self.server_id.api_token:
            raise UserError(_("WHM server is not properly configured. Missing API URL or token."))
        
        return {
            'url': self.server_id.api_url.rstrip('/'),
            'token': self.server_id.api_token,
            'verify_ssl': self.server_id.verify_ssl,
        }

    def _whm_headers(self, token):
        return {
            "Authorization": f"whm root:{token}",
        }

    def _whm_call(self, endpoint, params=None, token=None):
        """Make WHM API call with proper error handling"""
        config = self._whm_server_config()
        url = f"{config['url']}/json-api/{endpoint}"
        
        try:
            r = requests.get(
                url,
                headers=self._whm_headers(token or config['token']),
                params=params or {},
                verify=config['verify_ssl'],
                timeout=30,
            )
            _logger.info("WHM API %s → %s", endpoint, r.status_code)
            if r.status_code == 200:
                return r.json()
            raise UserError(_("WHM API error [%s]: %s") % (r.status_code, r.text))
        except requests.exceptions.ConnectionError as e:
            raise UserError(_("Cannot connect to WHM server: %s") % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_("WHM API timed out"))

    # --------------------------------------------------
    # USERNAME AND PASSWORD GENERATION
    # --------------------------------------------------

    def _generate_username(self, partner):
        """Generate a valid cPanel username (max 16 chars, alphanumeric, lowercase)"""
        base = re.sub(r"[^a-z0-9]", "", partner.name.lower())[:8]
        if not base:
            base = "user"

        # Try up to 5 times to find a non-reserved, non-existing username
        for _ in range(5):
            suffix = "".join(random.choices(string.digits, k=4))
            username = f"{base}{suffix}"[:16]

            # Check it doesn't already exist in WHM
            try:
                existing = self._whm_call("listaccts", {"search": username, "searchtype": "user"})
                accts = existing.get("acct", [])
                if not accts:
                    return username
            except Exception:
                return username

        # Final fallback — pure random
        return "user" + "".join(random.choices(string.digits, k=8))

    def _generate_password(self, length=16):
        """Generate a secure random password meeting WHM requirements"""
        chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
        while True:
            pwd = "".join(random.choices(chars, k=length))
            if (len(pwd) >= 10 and
                any(c.isupper() for c in pwd) and
                any(c.islower() for c in pwd) and
                any(c.isdigit() for c in pwd) and
                any(c in "!@#$%^&*()_+-=" for c in pwd)):
                return pwd

    # --------------------------------------------------
    # PROVISIONING WORKFLOW
    # --------------------------------------------------

    def action_provision(self):
        """Create cPanel account in WHM"""
        for account in self:
            if account.state not in ("pending", "error"):
                continue
            try:
                account._provision_cpanel()
            except Exception as e:
                account.write({"state": "error", "last_error": str(e)})
                account.message_post(body=_(
                    "<b>Provisioning Failed</b><br/>%s"
                ) % str(e))
                _logger.error("WHM provisioning failed for %s: %s", account.name, str(e))

    def action_retry_provisioning(self):
        """Reset stuck provisioning accounts back to pending and retry"""
        for account in self:
            account.write({
                "state": "pending",
                "last_error": False,
                "cpanel_username": False,
                "cpanel_password": False,
            })
            account.message_post(body=_("<b>Provisioning Reset — Retrying</b>"))
            try:
                account._provision_cpanel()
            except Exception as e:
                account.write({"state": "error", "last_error": str(e)})
                account.message_post(body=_(
                    "<b>Provisioning Failed</b><br/>%s"
                ) % str(e))
                _logger.error("WHM re-provisioning failed for %s: %s", account.name, str(e))

    def _provision_cpanel(self):
        """Core provisioning logic"""
        self.ensure_one()
        self.write({"state": "provisioning"})
        self.message_post(body=_("<b>WHM Provisioning Started</b>"))

        try:
            partner = self.partner_id
            package = self.whm_package or "default"

            # Use customer-chosen password if set, otherwise auto-generate
            password = self.cpanel_password or self._generate_password()

            # Generate username
            username = self._generate_username(partner)

            # Domain handling
            domain = self.cpanel_domain or f"{username}.{self.server_id.default_domain}"
            if not self.cpanel_domain:
                _logger.info("No domain set for %s — using default: %s", self.name, domain)

            # Create cPanel account
            result = self._whm_call("createacct", {
                "username": username,
                "domain": domain,
                "password": password,
                "plan": package,
                "contactemail": partner.email or "",
                "ip": self.dedicated_ip or "n",
                "cgi": "y",
                "frontpage": "n",
                "hasshell": "n",
                "reseller": 1 if self.reseller else 0,
            })

            status = result.get("result", [{}])
            if isinstance(status, list):
                status = status[0] if status else {}

            if not status.get("status", 0):
                reason = status.get("statusmsg", "Unknown error")
                raise UserError(_("WHM createacct failed: %s") % reason)

            # Success - update account
            self.write({
                "cpanel_username": username,
                "cpanel_password": False,  # Clear plain text after provisioning
                "cpanel_domain": domain,
                "whm_package": package,
                "state": "active",
                "last_error": False,
                "provisioning_notes": f"Successfully created on {self.server_id.name}",
            })

            self.message_post(body=_(
                "<b>cPanel Account Created</b><br/>"
                "Username: %s<br/>"
                "Domain: %s<br/>"
                "Package: %s<br/>"
                "Server: %s"
            ) % (username, domain, package, self.server_id.name))

            _logger.info("cPanel account created: %s (%s) on %s", username, domain, self.server_id.name)

            # Create primary domain record
            if self.cpanel_domain:
                domain_record = self.env['whm.domain'].create({
                    'name': self.cpanel_domain,
                    'hosting_account_id': self.id,
                    'is_primary': True,
                    'state': 'active',
                })
                self.primary_domain_id = domain_record.id

            # Send welcome email
            self._send_hosting_welcome_email(username, password, domain, package)

        except Exception as e:
            error_msg = str(e)
            _logger.error("cPanel provisioning failed for %s: %s", self.name, error_msg)
            self.write({"state": "error", "last_error": error_msg})
            self.message_post(body=_("<b>Provisioning Failed</b><br/>%s") % error_msg)
            raise

    # --------------------------------------------------
    # ACCOUNT MANAGEMENT
    # --------------------------------------------------

    def action_suspend(self):
        """Suspend cPanel account"""
        self.ensure_one()
        result = self._whm_call("suspendacct", {
            "user": self.cpanel_username,
            "reason": "Suspended via Odoo WHM Management",
        })
        if result.get("result", [{}])[0].get("status", 0):
            self.write({"state": "suspended"})
            self.message_post(body=_("<b>Account Suspended</b>"))
        else:
            raise UserError(_("WHM suspend failed: %s") % result)

    def action_unsuspend(self):
        """Unsuspend cPanel account"""
        self.ensure_one()
        result = self._whm_call("unsuspendacct", {"user": self.cpanel_username})
        if result.get("result", [{}])[0].get("status", 0):
            self.write({"state": "active"})
            self.message_post(body=_("<b>Account Unsuspended</b>"))
        else:
            raise UserError(_("WHM unsuspend failed: %s") % result)

    def action_terminate(self):
        """Terminate cPanel account"""
        self.ensure_one()
        if self.state == 'terminated':
            raise UserError(_("Account is already terminated"))
        
        result = self._whm_call("removeacct", {
            "user": self.cpanel_username,
            "keepdns": 1,  # Keep DNS records
        })
        if result.get("result", [{}])[0].get("status", 0):
            self.write({"state": "terminated"})
            self.message_post(body=_("<b>Account Terminated</b>"))
        else:
            raise UserError(_("WHM termination failed: %s") % result)

    def action_upgrade_package(self, new_package):
        """Upgrade/downgrade cPanel package"""
        self.ensure_one()
        result = self._whm_call("changepackage", {
            "user": self.cpanel_username,
            "pkg": new_package,
        })
        if result.get("result", [{}])[0].get("status", 0):
            self.write({"whm_package": new_package})
            self.message_post(body=_(_("<b>Package Updated</b><br/>New package: %s") % new_package))
        else:
            raise UserError(_("WHM package change failed: %s") % result)

    # --------------------------------------------------
    # USAGE SYNC AND MONITORING
    # --------------------------------------------------

    def action_sync_usage(self):
        """Pull disk/BW usage from WHM"""
        for account in self.filtered(lambda a: a.cpanel_username and a.state == "active"):
            try:
                result = self._whm_call("accountsummary", {
                    "user": account.cpanel_username
                })
                data = result.get("acct", [{}])
                if isinstance(data, list):
                    data = data[0] if data else {}

                account.write({
                    "disk_used": float(data.get("diskused", 0) or 0),
                    "disk_limit": float(data.get("disklimit", 0) or 0),
                    "bw_used": float(data.get("totalbandwidth", 0) or 0),
                    "bw_limit": float(data.get("bandwidthlimit", 0) or 0),
                })
                _logger.info("Synced usage for %s", account.cpanel_username)
            except Exception as e:
                _logger.error("Failed to sync usage for %s: %s", account.cpanel_username, str(e))

    def action_test_connection(self):
        """Test WHM API connection"""
        self.ensure_one()
        try:
            result = self._whm_call("version")
            version = result.get("version", "unknown")
            build = result.get("build", "")
            msg = f"<b>✅ WHM Connection OK</b><br/>Version: {version} {build}<br/>Server: {self.server_id.name}"
            self.message_post(body=_(msg))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'WHM Connection OK',
                    'message': f'Connected to WHM {version}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.message_post(body=_("<b>❌ WHM Connection Failed</b><br/>%s") % str(e))
            raise UserError(_("WHM connection failed: %s") % str(e))

    # --------------------------------------------------
    # CPANEL AUTO LOGIN
    # --------------------------------------------------

    def get_cpanel_autologin_url(self):
        """Generate a one-time cPanel session URL"""
        self.ensure_one()
        if not self.cpanel_username:
            raise UserError(_("No cPanel username set."))

        result = self._whm_call("create_user_session", {
            "user": self.cpanel_username,
            "service": "cpaneld",
        })

        data = result.get("data", {})
        url = data.get("url")

        if not url:
            _logger.error("create_user_session returned no URL: %s", result)
            raise UserError(_("Could not generate cPanel login URL. Please try again."))

        _logger.info("cPanel auto-login URL generated for %s", self.cpanel_username)
        return url

    # --------------------------------------------------
    # EMAIL TEMPLATES
    # --------------------------------------------------

    def _send_hosting_welcome_email(self, username, password, domain, package):
        """Send hosting login details to customer"""
        try:
            template = self.env.ref(
                "whm_hosting.email_hosting_welcome",
                raise_if_not_found=False,
            )
            if template:
                template.sudo().send_mail(
                    self.id,
                    force_send=True,
                    email_values={
                        'email_to': self.partner_id.email,
                        'email_from': self.server_id.from_email or 'noreply@whmhosting.com',
                    }
                )
                _logger.info("Hosting welcome email sent to %s", self.partner_id.email)
            else:
                _logger.warning("Hosting welcome email template not found")
        except Exception as e:
            _logger.error("Failed to send hosting welcome email: %s", e)

    # --------------------------------------------------
    # CRON JOBS
    # --------------------------------------------------

    @api.model
    def cron_provision_pending_hosting(self):
        """Provision pending hosting accounts"""
        pending = self.search([("state", "=", "pending")])
        _logger.info("WHM Cron: %d pending hosting accounts to provision", len(pending))
        for account in pending:
            try:
                account._provision_cpanel()
            except Exception as e:
                error_msg = str(e)
                _logger.error("WHM cron provisioning failed for %s: %s", account.name, error_msg)
                try:
                    account.write({"state": "error", "last_error": error_msg})
                    account.message_post(body=_(
                        "<b>Provisioning Failed (Cron)</b><br/>%s"
                    ) % error_msg)
                    self.env.cr.commit()
                except Exception:
                    pass

    @api.model
    def cron_sync_hosting_usage(self):
        """Sync usage for all active accounts"""
        active = self.search([("state", "=", "active")])
        _logger.info("WHM Cron: syncing usage for %d accounts", len(active))
        active.action_sync_usage()

    @api.model
    def cron_check_due_accounts(self):
        """Check for accounts due for renewal"""
        today = fields.Date.today()
        due_soon = self.search([
            ("state", "in", ["active", "suspended"]),
            ("next_due_date", "<=", today),
            ("auto_renew", "=", True),
        ])
        _logger.info("WHM Cron: %d accounts due for renewal", len(due_soon))
        # Integration with billing system would go here
